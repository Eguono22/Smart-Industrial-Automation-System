"""Create the first admin without loading the machine simulator: python scripts/manage_users.py."""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.auth import create_user
from app.models.assets import AssetRegistry, RegistryError

if __name__ == '__main__':
    path = os.environ.get('SIAS_DATABASE_PATH', str(Path(__file__).resolve().parents[1] / 'instance' / 'sias.sqlite3'))
    username = input('Administrator username: ').strip()
    name = input('Display name: ').strip()
    password = getpass.getpass('Password (at least 12 characters): ')
    if password != getpass.getpass('Confirm password: '):
        sys.exit('Passwords do not match.')
    try:
        user = create_user(AssetRegistry(path), dict(username=username, name=name, password=password, role='admin'))
        print('Administrator created:', user['username'])
    except RegistryError as error:
        sys.exit(str(error))
