from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import bootstrap_admin
from app.models.assets import AssetRegistry


@pytest.fixture
def initial_admin(tmp_path, monkeypatch):
    registry = AssetRegistry(tmp_path / 'bootstrap.db')
    with registry.connect():
        pass
    monkeypatch.setenv('SIAS_INITIAL_ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('SIAS_INITIAL_ADMIN_PASSWORD_HASH', generate_password_hash(
        'generated-test-password', method='pbkdf2:sha256:1000000'))
    return registry


def test_bootstrap_is_atomic_and_creates_only_one_account(initial_admin):
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: bootstrap_admin(initial_admin), range(2)))
    assert sorted(results) == [False, True]
    with initial_admin.connect() as db:
        rows = db.execute('SELECT * FROM users').fetchall()
        assert len(rows) == 1
        assert rows[0]['username'] == 'admin' and rows[0]['role'] == 'admin'
        assert check_password_hash(rows[0]['password_hash'], 'generated-test-password')
        db.execute('DELETE FROM users')
    assert bootstrap_admin(initial_admin) is False


def test_bootstrap_preserves_existing_accounts(initial_admin):
    with initial_admin.connect() as db:
        db.execute("INSERT INTO users (username,name,password_hash,role) VALUES ('existing','Owner','unchanged','admin')")
    assert bootstrap_admin(initial_admin) is False
    with initial_admin.connect() as db:
        assert db.execute('SELECT password_hash FROM users').fetchone()[0] == 'unchanged'


def test_bootstrap_rejects_invalid_hash(initial_admin, monkeypatch):
    monkeypatch.setenv('SIAS_INITIAL_ADMIN_PASSWORD_HASH', 'plaintext-is-not-accepted')
    with pytest.raises(RuntimeError, match='Invalid initial administrator'):
        bootstrap_admin(initial_admin)
    with initial_admin.connect() as db:
        assert db.execute('SELECT count(*) FROM users').fetchone()[0] == 0
