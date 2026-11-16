"""Create a consistent SQLite backup while SIAS is running."""
import argparse
import os
from pathlib import Path
import sqlite3


def backup(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source == destination:
        raise ValueError('Backup destination must differ from the live database')
    # Exclusive creation protects existing backups and restricts account data access.
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as live:
            with sqlite3.connect(destination) as snapshot:
                live.backup(snapshot)
                if snapshot.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup integrity check failed')
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', help='New backup filename; parent directory must exist')
    parser.add_argument('--source', default=os.environ.get('SIAS_DATABASE_PATH', 'instance/sias.sqlite3'))
    args = parser.parse_args()
    print(backup(args.source, args.destination))
