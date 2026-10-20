"""Session authentication, CSRF protection and account administration."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.assets import AssetRegistry, RegistryError

bp = Blueprint('auth', __name__)
ROLES = ('admin', 'manager', 'technician', 'viewer')


def store():
    return AssetRegistry(current_app.config['SIAS_DATABASE_PATH'])


def public_user(row):
    return {key: row[key] for key in ('id', 'username', 'name', 'role', 'customer_id', 'active', 'email')}


def create_user(registry, data, record_id=None):
    if not isinstance(data, dict) or set(data) - {'username', 'name', 'password', 'role', 'customer_id', 'active', 'email'}:
        raise RegistryError('Invalid account fields')
    with registry.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT * FROM users WHERE id=?', (record_id,)).fetchone() if record_id else None
        if record_id and old is None:
            raise RegistryError('Account not found', 404)
        values = dict(old) if old else {'active': True, 'customer_id': None, 'email': ''}
        values.update(data)
        for field in ('username', 'name', 'role'):
            if not isinstance(values.get(field), str) or not values[field].strip() or len(values[field]) > 200:
                raise RegistryError(f'{field} is required and must be at most 200 characters')
            values[field] = values[field].strip()
        email = values.get('email', '')
        from email.headerregistry import Address
        try:
            if not isinstance(email, str) or len(email) > 254 or any(ch in email for ch in '\r\n'):
                raise ValueError()
            email = email.strip()
            if email:
                parsed = Address(addr_spec=email)
                if not parsed.username or not parsed.domain or parsed.addr_spec != email:
                    raise ValueError()
        except (ValueError, IndexError):
            raise RegistryError('Provide a valid email address or leave it blank') from None
        values['email'] = email
        values['username'] = values['username'].lower()
        if values['role'] not in ROLES or type(values['active']) not in (bool, int) or values['active'] not in (0, 1):
            raise RegistryError('Invalid role or active setting')
        if values['role'] == 'admin':
            values['customer_id'] = None
        elif type(values['customer_id']) is not int or not db.execute('SELECT id FROM customers WHERE id=?', (values['customer_id'],)).fetchone():
            raise RegistryError('Non-admin accounts require an existing customer')
        if old and old['customer_id'] != values['customer_id']:
            if db.execute('SELECT id FROM work_orders WHERE assignee_id=? LIMIT 1', (record_id,)).fetchone():
                raise RegistryError('Reassign this account’s work orders before changing its customer', 409)
        password = data.get('password')
        if password is not None or old is None:
            if not isinstance(password, str) or not 12 <= len(password) <= 256:
                raise RegistryError('Password must contain 12 to 256 characters')
            values['password_hash'] = generate_password_hash(password, method='pbkdf2:sha256:1000000')
        if old and old['role'] == 'admin' and old['active'] and (values['role'] != 'admin' or not values['active']):
            if db.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0] <= 1:
                raise RegistryError('At least one active administrator is required', 409)
        duplicate = db.execute('SELECT id FROM users WHERE username=? AND id != ?', (values['username'], record_id or 0)).fetchone()
        if duplicate:
            raise RegistryError('Username already exists', 409)
        fields = ('username', 'name', 'password_hash', 'role', 'customer_id', 'active', 'email')
        if old:
            db.execute(f"UPDATE users SET {', '.join(f'{key}=?' for key in fields)} WHERE id=?", (*[values[key] for key in fields], record_id))
            db.execute('DELETE FROM auth_sessions WHERE user_id=?', (record_id,))
        else:
            record_id = db.execute(f"INSERT INTO users ({', '.join(fields)}) VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(values[key] for key in fields)).lastrowid
        return public_user(db.execute('SELECT * FROM users WHERE id=?', (record_id,)).fetchone())


def authenticated_user(token=None):
    token = token if token is not None else session.get('sid')
    if not token:
        return None
    with store().connect() as db:
        row = db.execute("""SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id=u.id
            WHERE s.token_hash=? AND s.expires_at>? AND u.active=1""",
            (hashlib.sha256(token.encode()).hexdigest(), datetime.now(timezone.utc).isoformat())).fetchone()
        return public_user(row) if row else None


def install_auth(app):
    registry = AssetRegistry(app.config['SIAS_DATABASE_PATH'])
    with registry.connect() as db:
        db.execute("INSERT OR IGNORE INTO auth_settings (key, value) VALUES ('session_secret', ?)", (secrets.token_hex(32),))
        secret = db.execute("SELECT value FROM auth_settings WHERE key='session_secret'").fetchone()[0]
    if not app.config.get('SECRET_KEY') or app.config['SECRET_KEY'] in ('sias-dev-secret', 'change-me'):
        app.config['SECRET_KEY'] = secret
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
    app.config['DUMMY_PASSWORD_HASH'] = generate_password_hash(secrets.token_urlsafe(24), method='pbkdf2:sha256:1000000')
    app.register_blueprint(bp)

    @app.before_request
    def authenticate():
        g.user = None
        # This one endpoint accepts only an asset-scoped bearer credential.
        # The endpoint verifies it atomically with storing readings; no cookie access.
        if request.endpoint == 'telemetry.ingest' and request.method == 'POST':
            return None
        g.user = authenticated_user()
        public = request.path in ('/', '/login', '/api/auth/me', '/api/auth/login', '/api/hub/catalog', '/health', '/ready') or request.path.startswith('/static/')
        if not public:
            if not g.user:
                if request.path.startswith(('/api/', '/socket.io/')) or request.path == '/metrics':
                    return jsonify(ok=False, error='Login required'), 401
                return redirect('/login')
            tenant_routes = request.path in ('/assets', '/work-orders', '/notifications', '/telemetry', '/operations', '/industry-hub') or request.path.startswith(('/api/registry', '/api/work-orders', '/api/auth', '/api/notifications', '/api/telemetry', '/operations/'))
            if not tenant_routes and g.user['role'] != 'admin':
                return jsonify(ok=False, error='Administrator access required'), 403
        if request.method in ('POST', 'PATCH', 'PUT', 'DELETE'):
            expected = session.get('csrf')
            if not expected or not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), expected):
                return jsonify(ok=False, error='Invalid CSRF token. Refresh and try again.'), 403

    @app.after_request
    def private_responses(response):
        if g.get('user') or request.path.startswith('/api/auth') or request.path == '/login':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.context_processor
    def auth_context():
        return {'current_user': g.get('user'), 'csrf_token': csrf_token()}


def csrf_token():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_urlsafe(32)
    return session['csrf']


@bp.errorhandler(RegistryError)
def account_error(error):
    return jsonify(ok=False, error=str(error)), error.status


@bp.route('/login')
def login_page():
    return render_template('login.html')


@bp.route('/api/auth/me')
def me():
    return jsonify(ok=True, user=g.user, csrf_token=csrf_token())


@bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('username'), str) or not isinstance(data.get('password'), str):
        raise RegistryError('Username and password are required')
    username = data['username'].strip().lower()
    if len(username) > 200 or len(data['password']) > 256:
        raise RegistryError('Invalid credentials', 401)
    now = datetime.now(timezone.utc)
    identity = hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
    with store().connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM login_attempts WHERE attempted_at < ?', ((now - timedelta(minutes=15)).isoformat(),))
        if db.execute('SELECT count(*) FROM login_attempts WHERE identity=?', (identity,)).fetchone()[0] >= 10:
            return jsonify(ok=False, error='Too many login attempts. Try again in 15 minutes.'), 429
        user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        # A real hash check also runs for unknown users.
        valid = check_password_hash(user['password_hash'] if user else current_app.config['DUMMY_PASSWORD_HASH'], data['password'])
        if not user or not valid or not user['active']:
            db.execute('INSERT INTO login_attempts (identity, attempted_at) VALUES (?, ?)', (identity, now.isoformat()))
            return jsonify(ok=False, error='Invalid credentials'), 401
        db.execute('DELETE FROM auth_sessions WHERE expires_at<=?', (now.isoformat(),))
        if session.get('sid'):
            db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (hashlib.sha256(session['sid'].encode()).hexdigest(),))
        session.clear()
        session['sid'] = secrets.token_urlsafe(32)
        db.execute('INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)',
                   (hashlib.sha256(session['sid'].encode()).hexdigest(), user['id'], (now + timedelta(hours=8)).isoformat()))
    return jsonify(ok=True, user=public_user(user), csrf_token=csrf_token())


@bp.route('/api/auth/logout', methods=['POST'])
def logout():
    with store().connect() as db:
        db.execute('DELETE FROM auth_sessions WHERE token_hash=?', (hashlib.sha256(session.get('sid', '').encode()).hexdigest(),))
    session.clear()
    return jsonify(ok=True)


@bp.route('/api/auth/users', methods=['GET', 'POST'])
@bp.route('/api/auth/users/<int:record_id>', methods=['PATCH'])
def accounts(record_id=None):
    if not g.user or g.user['role'] != 'admin':
        raise RegistryError('Administrator access required', 403)
    if request.method != 'GET':
        return jsonify(ok=True, user=create_user(store(), request.get_json(silent=True), record_id)), 201 if record_id is None else 200
    with store().connect() as db:
        return jsonify(ok=True, users=[public_user(row) for row in db.execute('SELECT * FROM users ORDER BY username')])


@bp.route('/api/auth/technicians')
def technicians():
    with store().connect() as db:
        rows = db.execute("SELECT id, name, customer_id FROM users WHERE role='technician' AND active=1 ORDER BY name")
        return jsonify(ok=True, technicians=[dict(row) for row in rows if g.user['role'] == 'admin' or row['customer_id'] == g.user['customer_id']])


@bp.route('/users')
def users_page():
    if g.user['role'] != 'admin':
        raise RegistryError('Administrator access required', 403)
    return render_template('users.html')
