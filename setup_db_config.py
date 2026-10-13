"""Save MySQL connection settings locally without displaying the password."""
import getpass
import json
from pathlib import Path

path = Path(__file__).resolve().parent / 'db_config.json'
if path.exists():
    raise SystemExit('db_config.json already exists. Edit it locally if settings need to change.')
host = input('MySQL host [127.0.0.1]: ').strip() or '127.0.0.1'
port = int(input('MySQL port [3306]: ').strip() or '3306')
user = input('MySQL username: ').strip()
if not user:
    raise SystemExit('A MySQL username is required.')
database = input('Database name [gym_management]: ').strip() or 'gym_management'
password = getpass.getpass('MySQL password (hidden): ')
path.write_text(json.dumps({'host': host, 'port': port, 'user': user,
                           'password': password, 'database': database}, indent=2), encoding='utf-8')
print('Saved db_config.json locally. Keep this file out of Git and shared reports.')
