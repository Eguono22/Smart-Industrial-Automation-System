"""No real email: test queue behavior, customer visibility and mocked SMTP delivery."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from flask import Flask
from app.auth import create_user, install_auth
from app.models.assets import AssetRegistry, RegistryError
from app.notifications import (notifications_bp, queue_overdue, list_notices,
    retry_notice, deliver_pending, smtp_config, send_email)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.registry = AssetRegistry(os.path.join(self.tmp.name, 'sias.sqlite3'))
        customer = self.registry.save('customers', dict(name='Owner', industry='water'))
        self.customer_id = customer['id']
        site = self.registry.save('sites', dict(name='Plant', customer_id=customer['id']))
        self.asset = self.registry.save('assets', dict(name='Pump', site_id=site['id'], asset_type='Pump'))
        with patch('app.auth.generate_password_hash', return_value='test-only-not-a-real-hash'):
            self.tech = create_user(self.registry, dict(username='tech', name='Technician', role='technician', customer_id=customer['id'], email='tech@example.test', password='test-only-password'))
        self.admin = dict(id=999, role='admin', customer_id=None)
        self.yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

    def create_order(self, **overrides):
        return self.registry.save_work_order(dict(asset_id=self.asset['id'], title='Inspect pump', due_date=self.yesterday, assignee_id=self.tech['id'], **overrides))

    def notices(self):
        return list_notices(self.registry, self.admin)

    def test_assignment_queued_atomically_and_no_duplicate_on_status_change(self):
        order = self.create_order()
        self.assertEqual(len(self.notices()), 1)
        self.assertEqual(self.notices()[0]['status'], 'pending')
        self.registry.save_work_order({'status': 'in_progress'}, order['id'])
        self.assertEqual(len(self.notices()), 1)
        self.assertEqual(len(list_notices(AssetRegistry(self.registry.path), self.tech)), 1)

    def test_overdue_is_deduplicated_and_due_today_excluded(self):
        self.create_order()
        self.assertEqual(queue_overdue(self.registry), 1)
        self.assertEqual(queue_overdue(self.registry), 0)
        self.registry.save_work_order(dict(asset_id=self.asset['id'], title='Today', due_date=datetime.now(timezone.utc).date().isoformat(), assignee_id=self.tech['id']))
        self.assertEqual(queue_overdue(self.registry), 0)
        self.assertEqual(len([n for n in self.notices() if n['kind'] == 'overdue']), 1)

    def test_delivery_is_claimed_once_and_uses_current_email(self):
        self.create_order()
        with self.registry.connect() as db:
            db.execute("UPDATE users SET email='updated@example.test' WHERE id=?", (self.tech['id'],))
        sender = Mock()
        self.assertEqual(deliver_pending(self.registry, {}, sender=sender), dict(sent=1, failed=0, skipped=0))
        self.assertEqual(sender.call_args.args[1], 'updated@example.test')
        self.assertEqual(deliver_pending(self.registry, {}, sender=sender)['sent'], 0)
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(self.notices()[0]['attempts'], 1)
        self.assertIsNotNone(self.notices()[0]['sent_at'])

    def test_failed_delivery_can_be_retried_without_exposing_provider_errors(self):
        self.create_order()
        result = deliver_pending(self.registry, {}, sender=Mock(side_effect=RuntimeError('secret SMTP credential')))
        self.assertEqual(result['failed'], 1)
        notice = self.notices()[0]
        self.assertNotIn('secret SMTP credential', notice['last_error'])
        retry_notice(self.registry, notice['id'], self.admin)
        self.assertEqual(deliver_pending(self.registry, {}, sender=Mock())['sent'], 1)
        self.assertEqual(self.notices()[0]['attempts'], 2)
        with self.assertRaises(RegistryError):
            retry_notice(self.registry, notice['id'], self.admin)

    def test_disabled_reassigned_and_closed_tasks_are_not_sent(self):
        order = self.create_order()
        self.registry.save_work_order({'status': 'cancelled'}, order['id'])
        sender = Mock()
        self.assertEqual(deliver_pending(self.registry, {}, sender=sender)['skipped'], 1)
        sender.assert_not_called()
        order = self.create_order()
        self.registry.save_work_order({'assignee_id': None}, order['id'])
        self.assertEqual(deliver_pending(self.registry, {}, sender=sender)['skipped'], 1)
        self.create_order()
        with self.registry.connect() as db:
            db.execute('UPDATE users SET active=0 WHERE id=?', (self.tech['id'],))
        self.assertEqual(deliver_pending(self.registry, {}, sender=sender)['skipped'], 1)
        sender.assert_not_called()

    def test_notifications_do_not_follow_account_to_another_customer(self):
        order = self.create_order()
        self.assertEqual(len(list_notices(self.registry, self.tech)), 1)
        self.registry.save_work_order({'assignee_id': None}, order['id'])
        other = self.registry.save('customers', dict(name='Other', industry='water'))
        moved = dict(self.tech, customer_id=other['id'])
        self.assertEqual(list_notices(self.registry, moved), [])
        with self.assertRaises(RegistryError):
            retry_notice(self.registry, self.notices()[0]['id'], moved)

    def test_email_validation_and_template_access(self):
        for email in ['bad', 'x@example.test\nBcc: attacker@example.test', 'x@y, z@y', None]:
            with self.subTest(email=email), self.assertRaises(RegistryError):
                create_user(self.registry, {'email': email}, self.tech['id'])
        app = Flask(__name__, template_folder=os.path.abspath('app/templates'))
        app.config.update(TESTING=True, SIAS_DATABASE_PATH=self.registry.path)
        app.register_blueprint(notifications_bp)
        with patch('app.auth.generate_password_hash', return_value='test-only-hash'):
            install_auth(app)
        self.assertEqual(app.test_client().get('/api/notifications').status_code, 401)
        with app.test_request_context('/notifications'):
            from flask import render_template
            html = render_template('notifications.html', current_user=self.tech)
            self.assertIn('notice-rows', html)

    def test_smtp_transport_and_config(self):
        with self.assertRaises(ValueError):
            smtp_config({})
        config = smtp_config(dict(SIAS_SMTP_HOST='smtp.example.test', SIAS_SMTP_FROM='sias@example.test'))
        with patch('app.notifications.smtplib.SMTP') as transport:
            send_email(config, 'tech@example.test', 'Task assigned', 'Inspect pump')
            smtp = transport.return_value.__enter__.return_value
            smtp.starttls.assert_called_once()
            smtp.send_message.assert_called_once()
            self.assertEqual(smtp.send_message.call_args.args[0]['To'], 'tech@example.test')
        for env in [dict(SIAS_SMTP_SECURITY='invalid'), dict(SIAS_SMTP_FROM='bad'), dict(SIAS_SMTP_PORT='0')]:
            with self.assertRaises(ValueError):
                smtp_config(dict(SIAS_SMTP_HOST='smtp.example.test', SIAS_SMTP_FROM='sias@example.test', **env) if 'SIAS_SMTP_FROM' not in env else dict(SIAS_SMTP_HOST='smtp.example.test', **env))
