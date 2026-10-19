"""Durable work-order notices and an explicitly invoked SMTP delivery worker."""
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage

from flask import Blueprint, g, jsonify, render_template
from app.models.assets import AssetRegistry, RegistryError

notifications_bp = Blueprint('notifications', __name__)


def queue_notice(db, order, user_id, kind, event_key, now):
    subject = f"SIAS: {'Work order assigned' if kind == 'assignment' else 'Work order overdue'} #{order['id']}"
    body = (f"{subject}\n\nTask: {order['title']}\nPriority: {order['priority']}\n"
            f"Due date (UTC): {order['due_date']}\n\nSign in to SIAS Hub and open Work orders to review this task.")
    db.execute('''INSERT OR IGNORE INTO notifications
        (work_order_id, user_id, event_key, kind, subject, body, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)''', (order['id'], user_id, event_key, kind, subject, body, now))


def queue_overdue(registry):
    now = datetime.now(timezone.utc)
    with registry.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        before = db.total_changes
        rows = db.execute("SELECT * FROM work_orders WHERE status IN ('open', 'in_progress') AND due_date < ? AND assignee_id IS NOT NULL", (now.date().isoformat(),)).fetchall()
        for order in rows:
            queue_notice(db, order, order['assignee_id'], 'overdue',
                         f"overdue:{order['id']}:{order['assignee_id']}:{order['due_date']}", now.isoformat())
        return db.total_changes - before


def list_notices(registry, actor):
    with registry.connect() as db:
        rows = db.execute('''SELECT n.*, u.name AS recipient_name, u.email AS recipient_email, s.customer_id AS customer_id
            FROM notifications n JOIN users u ON u.id=n.user_id
            JOIN work_orders w ON w.id=n.work_order_id
            JOIN assets a ON a.id=w.asset_id JOIN sites s ON s.id=a.site_id ORDER BY n.id DESC''')
        return [dict(row) for row in rows if actor['role'] == 'admin' or (row['user_id'] == actor['id'] and row['customer_id'] == actor['customer_id'])]


def retry_notice(registry, record_id, actor):
    if actor['role'] != 'admin':
        raise RegistryError('Administrator access required', 403)
    with registry.connect() as db:
        row = db.execute('SELECT * FROM notifications WHERE id=?', (record_id,)).fetchone()
        if not row:
            raise RegistryError('Notification not found', 404)
        if row['status'] not in ('failed', 'skipped'):
            raise RegistryError('Only failed or skipped notifications can be retried', 409)
        db.execute("UPDATE notifications SET status='pending', last_error='' WHERE id=?", (record_id,))


def smtp_config(environ=None):
    env = os.environ if environ is None else environ
    host, sender = env.get('SIAS_SMTP_HOST', ''), env.get('SIAS_SMTP_FROM', '')
    security = env.get('SIAS_SMTP_SECURITY', 'starttls')
    if not host or not sender or '\n' in sender or '\r' in sender:
        raise ValueError('Set SIAS_SMTP_HOST and a valid SIAS_SMTP_FROM before sending')
    if security not in ('starttls', 'ssl', 'plain'):
        raise ValueError('SIAS_SMTP_SECURITY must be starttls, ssl or plain')
    from email.headerregistry import Address
    try:
        address = Address(addr_spec=sender)
        if not address.username or not address.domain or address.addr_spec != sender:
            raise ValueError()
    except (ValueError, IndexError):
        raise ValueError('SIAS_SMTP_FROM must be a single mailbox address') from None
    if bool(env.get('SIAS_SMTP_USERNAME')) != bool(env.get('SIAS_SMTP_PASSWORD')):
        raise ValueError('Set both SIAS_SMTP_USERNAME and SIAS_SMTP_PASSWORD, or neither')
    port = int(env.get('SIAS_SMTP_PORT', '465' if security == 'ssl' else '587'))
    if not 1 <= port <= 65535:
        raise ValueError('SIAS_SMTP_PORT must be between 1 and 65535')
    return dict(host=host, sender=sender, port=port,
                security=security, username=env.get('SIAS_SMTP_USERNAME', ''), password=env.get('SIAS_SMTP_PASSWORD', ''))


def send_email(config, recipient, subject, body):
    message = EmailMessage()
    message['From'], message['To'], message['Subject'] = config['sender'], recipient, subject
    message.set_content(body)
    context = ssl.create_default_context()
    factory = smtplib.SMTP_SSL if config['security'] == 'ssl' else smtplib.SMTP
    options = dict(host=config['host'], port=config['port'], timeout=30)
    if config['security'] == 'ssl':
        options['context'] = context
    with factory(**options) as smtp:
        if config['security'] == 'starttls':
            smtp.starttls(context=context)
        if config['username']:
            smtp.login(config['username'], config['password'])
        smtp.send_message(message)


def deliver_pending(registry, config, limit=50, sender=send_email):
    """Claim each notice once. SMTP-accepted mail can still fail to reach an inbox."""
    counts = dict(sent=0, failed=0, skipped=0)
    # A fixed batch avoids retrying errors in a tight loop.
    with registry.connect() as db:
        ids = [row['id'] for row in db.execute("SELECT id FROM notifications WHERE status='pending' ORDER BY id LIMIT ?", (limit,))]
    for record_id in ids:
        with registry.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            notice = db.execute("SELECT * FROM notifications WHERE id=? AND status='pending'", (record_id,)).fetchone()
            if not notice:
                continue
            user = db.execute('SELECT * FROM users WHERE id=?', (notice['user_id'],)).fetchone()
            order = db.execute('''SELECT w.*, s.customer_id FROM work_orders w
                JOIN assets a ON a.id=w.asset_id JOIN sites s ON s.id=a.site_id WHERE w.id=?''', (notice['work_order_id'],)).fetchone()
            reason = None
            if not user or not user['active'] or not user['email']:
                reason = 'Recipient disabled or missing email'
            elif not order or user['role'] != 'technician' or user['customer_id'] != order['customer_id'] or order['assignee_id'] != user['id'] or order['status'] not in ('open', 'in_progress'):
                reason = 'Task no longer active or assigned to this technician'
            elif notice['kind'] == 'overdue' and (order['due_date'] >= datetime.now(timezone.utc).date().isoformat() or notice['event_key'] != f"overdue:{order['id']}:{user['id']}:{order['due_date']}"):
                reason = 'Task no longer overdue on the original due date'
            if reason:
                db.execute("UPDATE notifications SET status='skipped', last_error=? WHERE id=?", (reason, record_id))
                counts['skipped'] += 1
                continue
            # Rebuild content from current task fields to avoid sending stale details.
            subject = notice['subject']
            body = (f"{subject}\n\nTask: {order['title']}\nPriority: {order['priority']}\n"
                    f"Due date (UTC): {order['due_date']}\n\nSign in to SIAS Hub and open Work orders to review this task.")
            db.execute("UPDATE notifications SET status='processing', attempts=attempts+1, body=? WHERE id=?", (body, record_id))
            recipient = user['email']
        try:
            sender(config, recipient, subject, body)
        except Exception:
            # Provider exception strings may contain addresses or credentials; keep UI errors generic.
            with registry.connect() as db:
                db.execute("UPDATE notifications SET status='failed', last_error='SMTP delivery failed; check server configuration and provider logs' WHERE id=?", (record_id,))
            counts['failed'] += 1
        else:
            with registry.connect() as db:
                db.execute("UPDATE notifications SET status='sent', sent_at=?, sent_to=?, last_error='' WHERE id=?", (datetime.now(timezone.utc).isoformat(), recipient, record_id))
            counts['sent'] += 1
    return counts


@notifications_bp.errorhandler(RegistryError)
def notification_error(error):
    return jsonify(ok=False, error=str(error)), error.status


@notifications_bp.route('/notifications')
def notifications_page():
    return render_template('notifications.html')


@notifications_bp.route('/api/notifications')
def notifications_list():
    from flask import current_app
    return jsonify(ok=True, notifications=list_notices(AssetRegistry(current_app.config['SIAS_DATABASE_PATH']), g.user))


@notifications_bp.route('/api/notifications/<int:record_id>/retry', methods=['POST'])
def notifications_retry(record_id):
    from flask import current_app
    retry_notice(AssetRegistry(current_app.config['SIAS_DATABASE_PATH']), record_id, g.user)
    return jsonify(ok=True)
