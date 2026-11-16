import sqlite3

import pytest

from scripts.backup_database import backup


def test_backup_preserves_committed_data_without_overwriting(tmp_path):
    source, destination = tmp_path / 'live.db', tmp_path / 'backup.db'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE records (value TEXT)')
        db.execute("INSERT INTO records VALUES ('saved')")
    backup(source, destination)
    with sqlite3.connect(destination) as db:
        assert db.execute('SELECT value FROM records').fetchone() == ('saved',)
    with pytest.raises(FileExistsError):
        backup(source, destination)
    with pytest.raises(ValueError):
        backup(source, source)


def test_missing_source_does_not_leave_empty_backup(tmp_path):
    destination = tmp_path / 'backup.db'
    with pytest.raises(sqlite3.OperationalError):
        backup(tmp_path / 'missing.db', destination)
    assert not destination.exists()
