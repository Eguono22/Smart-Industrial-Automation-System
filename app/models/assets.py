"""SQLite asset registry with enforced customer/site ownership."""
import os
import json
from datetime import date, datetime, timezone
import sqlite3
from contextlib import contextmanager

from app.models.hub import INDUSTRIES

FIELDS = {
    'customers': ('name', 'industry'),
    'sites': ('name', 'customer_id', 'location'),
    'assets': ('name', 'site_id', 'asset_type', 'serial_number', 'criticality', 'status'),
}
STATUSES = ('operational', 'maintenance', 'offline', 'unknown')
CRITICALITIES = ('low', 'medium', 'high', 'critical')


class RegistryError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


class AssetRegistry:
    def __init__(self, path):
        self.path = os.fspath(path)

    @contextmanager
    def connect(self):
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        try:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, industry TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
                    location TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE RESTRICT,
                    asset_type TEXT NOT NULL, serial_number TEXT NOT NULL DEFAULT '',
                    criticality TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    password_hash TEXT NOT NULL, role TEXT NOT NULL,
                    customer_id INTEGER REFERENCES customers(id) ON DELETE RESTRICT, active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS auth_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS login_attempts (identity TEXT NOT NULL, attempted_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS auth_session_users ON auth_sessions(user_id);
                CREATE INDEX IF NOT EXISTS login_attempt_identity ON login_attempts(identity, attempted_at);
                CREATE TABLE IF NOT EXISTS work_orders (
                    id INTEGER PRIMARY KEY,
                    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
                    title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'medium', assignee TEXT NOT NULL DEFAULT '',
                    due_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
                    completion_notes TEXT NOT NULL DEFAULT '', completed_at TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS work_order_history (
                    id INTEGER PRIMARY KEY,
                    work_order_id INTEGER NOT NULL REFERENCES work_orders(id) ON DELETE RESTRICT,
                    changed_at TEXT NOT NULL, snapshot TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS work_orders_asset ON work_orders(asset_id);
                CREATE INDEX IF NOT EXISTS work_order_events ON work_order_history(work_order_id);
                CREATE INDEX IF NOT EXISTS sites_customer ON sites(customer_id);
                CREATE INDEX IF NOT EXISTS assets_site ON assets(site_id);
            ''')
            connection.execute('BEGIN IMMEDIATE')
            # Additive migrations preserve existing records and pre-account history.
            for table, column, definition in [
                ('work_orders', 'assignee_id', 'INTEGER REFERENCES users(id)'),
                ('work_order_history', 'actor_id', 'INTEGER REFERENCES users(id)'),
                ('work_order_history', 'actor_name', 'TEXT'),
            ]:
                columns = {row['name'] for row in connection.execute(f'PRAGMA table_info({table})')}
                if column not in columns:
                    connection.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
            connection.commit()
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def authorize(db, kind, record_id, actor):
        if actor is None or actor['role'] == 'admin':
            return
        queries = {
            'customers': 'SELECT id AS customer_id FROM customers WHERE id=?',
            'sites': 'SELECT customer_id FROM sites WHERE id=?',
            'assets': 'SELECT s.customer_id FROM assets a JOIN sites s ON s.id=a.site_id WHERE a.id=?',
            'work_orders': 'SELECT s.customer_id FROM work_orders w JOIN assets a ON a.id=w.asset_id JOIN sites s ON s.id=a.site_id WHERE w.id=?',
        }
        row = db.execute(queries[kind], (record_id,)).fetchone()
        if not row or row['customer_id'] != actor['customer_id']:
            raise RegistryError('Record not found', 404)

    @staticmethod
    def require_role(actor, *roles):
        if actor is not None and actor['role'] not in roles:
            raise RegistryError('Your role cannot perform this action', 403)

    def snapshot(self, actor=None):
        with self.connect() as db:
            result = {kind: [dict(row) for row in db.execute(f'SELECT * FROM {kind} ORDER BY name COLLATE NOCASE, id')]
                      for kind in FIELDS}
            if actor is not None and actor['role'] != 'admin':
                result['customers'] = [r for r in result['customers'] if r['id'] == actor['customer_id']]
                result['sites'] = [r for r in result['sites'] if r['customer_id'] == actor['customer_id']]
                sites = {r['id'] for r in result['sites']}
                result['assets'] = [r for r in result['assets'] if r['site_id'] in sites]
            return result

    def save(self, kind, data, record_id=None, actor=None):
        if kind not in FIELDS:
            raise RegistryError('Unknown registry type', 404)
        self.require_role(actor, *(['admin'] if kind == 'customers' else ['admin', 'manager']))
        if not isinstance(data, dict):
            raise RegistryError('A JSON object is required')
        if set(data) - set(FIELDS[kind]):
            raise RegistryError('Unknown fields in request')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if record_id is not None:
                self.authorize(db, kind, record_id, actor)
            previous = None
            if record_id is not None:
                previous = db.execute(f'SELECT * FROM {kind} WHERE id = ?', (record_id,)).fetchone()
                if previous is None:
                    raise RegistryError('Record not found', 404)
            values = dict(previous) if previous else {}
            values.update(data)
            defaults = {'location': '', 'serial_number': '', 'criticality': 'medium', 'status': 'unknown'}
            clean = {}
            for field in FIELDS[kind]:
                value = values.get(field, defaults.get(field))
                if field.endswith('_id'):
                    if type(value) is not int or value < 1:
                        raise RegistryError(f'{field} must be a positive integer')
                else:
                    if not isinstance(value, str) or len(value.strip()) > 200:
                        raise RegistryError(f'{field} must be text of at most 200 characters')
                    value = value.strip()
                    if not value and field not in ('location', 'serial_number'):
                        raise RegistryError(f'{field} is required')
                clean[field] = value
            if kind == 'customers' and clean['industry'] not in {item['id'] for item in INDUSTRIES}:
                raise RegistryError('Choose a valid industry')
            if kind == 'assets':
                if clean['status'] not in STATUSES or clean['criticality'] not in CRITICALITIES:
                    raise RegistryError('Choose a valid asset status and criticality')
            parent = {'sites': ('customers', 'customer_id'), 'assets': ('sites', 'site_id')}.get(kind)
            if parent and not db.execute(f'SELECT id FROM {parent[0]} WHERE id = ?', (clean[parent[1]],)).fetchone():
                raise RegistryError('Parent record not found', 400)
            if parent:
                self.authorize(db, parent[0], clean[parent[1]], actor)
            if previous and kind == 'assets' and previous['site_id'] != clean['site_id']:
                old_owner = db.execute('SELECT customer_id FROM sites WHERE id=?', (previous['site_id'],)).fetchone()[0]
                new_owner = db.execute('SELECT customer_id FROM sites WHERE id=?', (clean['site_id'],)).fetchone()[0]
                if old_owner != new_owner and db.execute('SELECT id FROM work_orders WHERE asset_id=? LIMIT 1', (record_id,)).fetchone():
                    raise RegistryError('Assets with maintenance history cannot move between customers', 409)
            fields = FIELDS[kind]
            if record_id is None:
                placeholders = ', '.join('?' for _ in fields)
                cursor = db.execute(f'INSERT INTO {kind} ({", ".join(fields)}) VALUES ({placeholders})', tuple(clean[f] for f in fields))
                record_id = cursor.lastrowid
            else:
                # Moving an occupied site would silently transfer its assets to another customer.
                if kind == 'sites' and previous['customer_id'] != clean['customer_id']:
                    if db.execute('SELECT id FROM assets WHERE site_id = ? LIMIT 1', (record_id,)).fetchone():
                        raise RegistryError('Move the site assets before changing its customer', 409)
                assignments = ', '.join(f'{field} = ?' for field in fields)
                db.execute(f'UPDATE {kind} SET {assignments} WHERE id = ?', (*[clean[f] for f in fields], record_id))
            return dict(db.execute(f'SELECT * FROM {kind} WHERE id = ?', (record_id,)).fetchone())

    def delete(self, kind, record_id, actor=None):
        if kind not in FIELDS:
            raise RegistryError('Unknown registry type', 404)
        self.require_role(actor, *(['admin'] if kind == 'customers' else ['admin', 'manager']))
        try:
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.authorize(db, kind, record_id, actor)
                cursor = db.execute(f'DELETE FROM {kind} WHERE id = ?', (record_id,))
                if not cursor.rowcount:
                    raise RegistryError('Record not found', 404)
        except sqlite3.IntegrityError:
            raise RegistryError('Remove or reassign dependent records first', 409) from None


    @staticmethod
    def _work_order(row):
        record = dict(row)
        record['overdue'] = record['status'] in ('open', 'in_progress') and record['due_date'] < datetime.now(timezone.utc).date().isoformat()
        return record

    def work_orders(self, actor=None):
        with self.connect() as db:
            rows = db.execute("""SELECT w.*, a.name AS asset_name, s.name AS site_name,
                c.name AS customer_name, c.id AS customer_id FROM work_orders w
                JOIN assets a ON a.id = w.asset_id JOIN sites s ON s.id = a.site_id
                JOIN customers c ON c.id = s.customer_id
                ORDER BY w.due_date, w.id""")
            return [self._work_order(row) for row in rows if actor is None or actor['role'] == 'admin' or row['customer_id'] == actor['customer_id']]

    def work_order_detail(self, record_id, actor=None):
        with self.connect() as db:
            self.authorize(db, 'work_orders', record_id, actor)
            row = db.execute('SELECT * FROM work_orders WHERE id = ?', (record_id,)).fetchone()
            if row is None:
                raise RegistryError('Work order not found', 404)
            record = self._work_order(row)
            record['history'] = [dict(id=event['id'], changed_at=event['changed_at'],
                                      snapshot=json.loads(event['snapshot']), actor_id=event['actor_id'], actor_name=event['actor_name'])
                                 for event in db.execute('SELECT * FROM work_order_history WHERE work_order_id = ? ORDER BY id', (record_id,))]
            return record

    def save_work_order(self, data, record_id=None, actor=None):
        fields = ('asset_id', 'title', 'description', 'priority', 'assignee', 'due_date', 'status', 'completion_notes', 'assignee_id')
        if not isinstance(data, dict) or set(data) - set(fields):
            raise RegistryError('Provide a JSON object containing supported work order fields')
        self.require_role(actor, 'admin', 'manager', 'technician')
        if actor is not None and actor['role'] == 'technician' and (record_id is None or set(data) - {'status', 'completion_notes'}):
            raise RegistryError('Technicians may update only status and completion notes on assigned tasks', 403)
        if actor is not None and 'assignee' in data:
            raise RegistryError('Assign a registered technician using assignee_id')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if record_id is not None:
                self.authorize(db, 'work_orders', record_id, actor)
            previous = None
            if record_id is not None:
                previous = db.execute('SELECT * FROM work_orders WHERE id = ?', (record_id,)).fetchone()
                if previous is None:
                    raise RegistryError('Work order not found', 404)
            values = dict(previous) if previous else dict(description='', priority='medium', assignee='', status='open', completion_notes='')
            values.update(data)
            if actor is not None and actor['role'] == 'technician' and previous['assignee_id'] != actor['id']:
                raise RegistryError('You may update only tasks assigned to you', 403)
            clean = {}
            for field in fields:
                value = values.get(field)
                if field == 'assignee_id':
                    if value is not None and (type(value) is not int or value < 1):
                        raise RegistryError('assignee_id must be a positive integer or null')
                elif field == 'asset_id':
                    if type(value) is not int or value < 1:
                        raise RegistryError('asset_id must be a positive integer')
                else:
                    limit = 4000 if field in ('description', 'completion_notes') else 200
                    if not isinstance(value, str) or len(value.strip()) > limit:
                        raise RegistryError(f'{field} must be text of at most {limit} characters')
                    value = value.strip()
                    if not value and field not in ('description', 'assignee', 'completion_notes'):
                        raise RegistryError(f'{field} is required')
                clean[field] = value
            if previous and clean['asset_id'] != previous['asset_id']:
                raise RegistryError('An existing work order must remain linked to its original asset', 409)
            if not db.execute('SELECT id FROM assets WHERE id = ?', (clean['asset_id'],)).fetchone():
                raise RegistryError('Asset not found')
            self.authorize(db, 'assets', clean['asset_id'], actor)
            if clean['assignee_id'] is not None:
                technician = db.execute("SELECT * FROM users WHERE id=? AND role='technician' AND active=1", (clean['assignee_id'],)).fetchone()
                owner = db.execute('SELECT s.customer_id FROM assets a JOIN sites s ON s.id=a.site_id WHERE a.id=?', (clean['asset_id'],)).fetchone()[0]
                if not technician or technician['customer_id'] != owner:
                    # Allow an unchanged inactive assignee while closing an older task.
                    if not previous or clean['assignee_id'] != previous['assignee_id'] or 'assignee_id' in data:
                        raise RegistryError('Choose an active technician for this asset customer')
                clean['assignee'] = technician['name'] if technician else previous['assignee']
            elif 'assignee_id' in data:
                clean['assignee'] = ''
            if clean['priority'] not in ('low', 'medium', 'high', 'critical'):
                raise RegistryError('Choose a valid priority')
            if clean['status'] not in ('open', 'in_progress', 'completed', 'cancelled'):
                raise RegistryError('Choose a valid work order status')
            try:
                parsed = date.fromisoformat(clean['due_date'])
                if parsed.isoformat() != clean['due_date']:
                    raise ValueError()
            except ValueError:
                raise RegistryError('due_date must be a valid date in YYYY-MM-DD format') from None
            if clean['status'] == 'completed' and not clean['completion_notes']:
                raise RegistryError('Completion notes are required to complete a work order')
            if previous and all(clean[field] == previous[field] for field in fields):
                return self._work_order(previous)
            now = datetime.now(timezone.utc).isoformat()
            completed_at = (previous['completed_at'] if previous and previous['status'] == 'completed' else now) if clean['status'] == 'completed' else None
            if previous:
                assignments = ', '.join(f'{field} = ?' for field in fields)
                db.execute(f'UPDATE work_orders SET {assignments}, completed_at = ?, updated_at = ? WHERE id = ?',
                           (*[clean[field] for field in fields], completed_at, now, record_id))
            else:
                cursor = db.execute(f"INSERT INTO work_orders ({', '.join(fields)}, completed_at, created_at, updated_at) VALUES ({', '.join('?' for _ in range(len(fields) + 3))})",
                                    (*[clean[field] for field in fields], completed_at, now, now))
                record_id = cursor.lastrowid
            row = dict(db.execute('SELECT * FROM work_orders WHERE id = ?', (record_id,)).fetchone())
            db.execute('INSERT INTO work_order_history (work_order_id, changed_at, snapshot, actor_id, actor_name) VALUES (?, ?, ?, ?, ?)',
                       (record_id, now, json.dumps(row), actor['id'] if actor else None, actor['name'] if actor else None))
            return self._work_order(row)
