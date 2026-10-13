"""Create a reproducible SQLite gym database with entirely fictional demonstration data.

This never overwrites an existing database. MySQL DDL remains in gym_setup.sql.
"""
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
if (ROOT / '.deps').is_dir():
    sys.path.insert(0, str(ROOT / '.deps'))


def sqlite_schema():
    sql = (ROOT / 'gym_setup.sql').read_text(encoding='utf-8-sig')
    sql = re.sub(r'CREATE DATABASE.*?;', '', sql, flags=re.S | re.I)
    sql = re.sub(r'USE\s+\w+\s*;', '', sql, flags=re.I)
    member_fk = re.search(r'ALTER TABLE member\s+ADD (CONSTRAINT.*?);', sql, flags=re.S | re.I)
    if member_fk is None:
        raise RuntimeError('Expected member-to-membership foreign key is missing from MySQL DDL.')
    constraint = member_fk.group(1).strip()
    sql = sql[:member_fk.start()] + sql[member_fk.end():]
    member_table = re.search(r'CREATE TABLE member\s*\(.*?\n\);', sql, flags=re.S | re.I)
    if member_table is None:
        raise RuntimeError('Expected member table is missing.')
    block = member_table.group(0).replace('\n);', ',\n ' + constraint + '\n);')
    sql = sql[:member_table.start()] + block + sql[member_table.end():]
    sql = re.sub(r'BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql, flags=re.I)
    sql = re.sub(r'(BIGINT|SMALLINT|MEDIUMINT) UNSIGNED', 'INTEGER', sql, flags=re.I)
    sql = re.sub(r'UNIQUE KEY\s+(\w+)\s*\(([^)]+)\)', r'CONSTRAINT \1 UNIQUE(\2)', sql, flags=re.I)
    sql = re.sub(r'\b(?:VARCHAR|CHAR)\(\d+\)', 'TEXT', sql, flags=re.I)
    sql = re.sub(r'\bDECIMAL\(\d+,\s*\d+\)', 'NUMERIC', sql, flags=re.I)
    # SQL types are uppercase in the supplied DDL. Preserve the lowercase `time` column.
    sql = re.sub(r'\b(?:DATETIME|TIMESTAMP|DATE|TIME)\b', 'TEXT', sql)
    sql = re.sub(r'\bBOOLEAN\b', 'INTEGER', sql, flags=re.I)
    return 'PRAGMA foreign_keys = ON;\n' + sql.strip() + '\n'


def seed(db):
    def insert(table, **values):
        columns = ', '.join('`' + column + '`' for column in values)
        placeholders = ', '.join('?' for _ in values)
        return db.execute(f'INSERT INTO `{table}` ({columns}) VALUES ({placeholders})', tuple(values.values())).lastrowid

    locations = ['Provo Central', 'Orem North', 'Lehi Strength', 'Spanish Fork Fitness', 'Springville Annex']
    for index, name in enumerate(locations, 1):
        address = insert('address', street=f'{index * 100} Demo Avenue', city=name.split()[0], state='UT', zip='84000')
        insert('gym_location', location_id=index, address_id=address, name=name,
               phone=f'801-555-01{index:02}', size='medium', is_active=1, open_date='2025-01-01')
    households = [insert('address', street=f'{2000 + n} Fictional Lane', city='Provo', state='UT', zip='84600')
                  for n in range(42)]
    plans = [('Basic', 1, 25), ('Plus', 2, 40), ('Premium', 3, 60), ('Family', 3, 75), ('Annual', 4, 30)]
    for index, (name, access, cost) in enumerate(plans, 1):
        insert('subscription', subscription_id=index, subscription_type=name, status='active',
               current_period_end='2026-12-31 23:59:59', cost_monthly=cost, annual_fee=20, cancellation_fee=10)
        insert('membership', membership_id=index, subscription_id=index, plan_name=name, access_level=access, invited_at=None)
    first_names = ['Alex', 'Jordan', 'Taylor', 'Morgan', 'Casey', 'Riley', 'Jamie', 'Avery', 'Parker', 'Drew']
    for person_id in range(1, 61):
        address_id = households[(person_id - 1) // 2] if person_id <= 36 else households[18 + person_id - 37]
        if person_id <= 10:
            birthday = f'{1980 + person_id % 20}-01-20'
        elif person_id <= 20:
            birthday = f'{1980 + person_id % 20}-07-04'
        elif person_id >= 59:
            birthday = None
        else:
            birthday = f'{1980 + person_id % 20}-{1 + person_id % 12:02}-{1 + person_id % 27:02}'
            if birthday[5:] in ('01-20', '07-04'):
                birthday = birthday[:8] + '05'
        insert('person', person_id=person_id, address_id=address_id,
               first_name=first_names[(person_id - 1) % 10], last_name=f'Demo{person_id:02}',
               DOB=birthday, email=f'member{person_id:02}@example.test', phone=f'801-555-{1000 + person_id}',
               is_deleted=int(person_id == 60))
        insert('person_address', person_id=person_id, address_id=address_id)
        gym_id = 1 + ((person_id - 1) // 2) % 4
        plan_id = 1 + (person_id - 1) % 5
        insert('member', member_id=person_id, person_id=person_id, subscription_id=plan_id,
               home_location=gym_id, membership_type=plan_id, created_date='2026-01-01 12:00:00',
               start_date='2026-01-01', end_date='2026-09-30' if person_id % 13 == 0 else None,
               is_inactive=int(person_id % 11 == 0), is_banned=int(person_id % 17 == 0))
    for employee_id in range(1, 13):
        hourly = employee_id % 3 != 0
        active = employee_id != 12
        insert('employee', employee_id=employee_id, person_id=48 + employee_id,
               employee_type='front desk' if hourly else 'manager', hire_date='2025-06-01',
               termination_date=None if active else '2026-09-01', employment_status='active' if active else 'terminated',
               is_hourly=int(hourly), hours_worked=80 if hourly else None)
        insert('employee_account', employee_id=employee_id, employment_type='hourly' if hourly else 'salary',
               pay_rate=18 + employee_id if hourly else 4800 + employee_id * 100,
               pay_frequency='hourly' if hourly else 'monthly', payroll_date='2026-10-15',
               YTD_salary=10000 + employee_id * 1000, bank_routing_number=None, SSN=None, available_PTO=24)
        first_gym = 1 + (employee_id - 1) % 4
        insert('employee_location', employee_id=employee_id, location_id=first_gym)
        if employee_id % 2 == 0:
            insert('employee_location', employee_id=employee_id, location_id=1 + first_gym % 4)
    equipment_ids = []
    for gym_id in range(1, 5):
        for item in range(1, 7):
            equipment_ids.append(insert('equipment', location_id=gym_id,
                name=['Squat rack', 'Bench press', 'Treadmill', 'Rowing machine', 'Cable machine', 'Leg press'][item - 1],
                item_number=item, brand='Rogue' if item <= 3 else 'Concept2' if item == 4 else 'Life Fitness',
                status='out of service' if item == 6 and gym_id % 2 == 0 else 'operational'))
    for gym_id in range(1, 6):
        for day in range(7):
            closed = gym_id == 5 and day == 0
            insert('hours', location_id=gym_id, day_of_week=day, open_time=None if closed else '06:00:00',
                   close_time=None if closed else '22:00:00', is_closed=int(closed))
    maintenance_ids = []
    for index in range(1, 9):
        gym_id = 1 + (index - 1) % 4
        equipment_id = equipment_ids[(gym_id - 1) * 6 + 5]
        maintenance_ids.append(insert('maintenance', employee_id=index, location_id=gym_id,
            equipment_id=equipment_id, reported_date=f'2026-10-{index:02}',
            notes=f'Fictional demonstration maintenance ticket {index}', is_resolved=int(index % 3 == 0)))
    for member_id in range(1, 61):
        home = 1 + ((member_id - 1) // 2) % 4
        for visit in range(member_id % 7):
            day = 1 + (member_id + visit * 3) % 12
            gym_id = home if visit % 2 == 0 else 1 + home % 4
            insert('check_in', location_id=gym_id, member_id=member_id,
                   time=f'2026-10-{day:02} {6 + visit:02}:00:00', is_clear=1, entry_method='app QR')
        plan_id = 1 + (member_id - 1) % 5
        for month in (9, 10):
            insert('transaction', location_id=home, member_id=member_id,
                   transaction_date=f'2026-{month:02}-01 09:00:00', amount=plans[plan_id - 1][2],
                   is_deposit=0, subscription_id=plan_id)
    # All rows are synthetic; no real financial or government identifiers are seeded.
    db.commit()


def seed_from_sql(db, path):
    import sqlglot
    from sqlglot import exp
    statements = sqlglot.parse(path.read_text(encoding='utf-8-sig'), read='mysql')
    converted = []
    for statement in statements:
        if statement is None or isinstance(statement, (exp.Use, exp.Transaction, exp.Commit, exp.Semicolon)):
            continue
        if not isinstance(statement, exp.Insert) or not isinstance(statement.expression, exp.Values):
            raise RuntimeError('The dummy data file may only contain literal INSERT statements and transaction wrappers.')
        converted.append(statement.sql(dialect='sqlite', comments=False) + ';')
    if not converted:
        raise RuntimeError('No data INSERT statements were found.')
    script = 'PRAGMA foreign_keys = ON;\nBEGIN TRANSACTION;\n' + '\n'.join(converted) + '\nCOMMIT;\n'
    db.executescript(script)
    (ROOT / 'gym_dummy_data_sqlite.sql').write_text(script, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=ROOT / 'gym.db')
    parser.add_argument('--schema-only', action='store_true', help='Write SQLite DDL without creating a DB.')
    parser.add_argument('--demo-fixture', action='store_true', help='Use the small controlled test dataset instead of the original dummy data.')
    args = parser.parse_args()
    schema = sqlite_schema()
    (ROOT / 'gym_setup_sqlite.sql').write_text(schema, encoding='utf-8')
    if args.schema_only:
        print('Wrote gym_setup_sqlite.sql from the original MySQL DDL.')
        return
    if args.database.exists():
        raise SystemExit('Database already exists. It has not been replaced.')
    args.database.parent.mkdir(parents=True, exist_ok=True)
    # Validate the whole schema and seed in memory before writing the database file.
    with sqlite3.connect(':memory:') as connection:
        connection.executescript(schema)
        data_path = ROOT / 'gym_dummy_data.sql'
        if data_path.exists() and not args.demo_fixture:
            seed_from_sql(connection, data_path)
        else:
            seed(connection)
        violations = connection.execute('PRAGMA foreign_key_check').fetchall()
        if violations:
            raise RuntimeError(f'Foreign key check failed: {violations}')
        tables = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        with sqlite3.connect(args.database) as destination:
            connection.backup(destination)
        counts = {table: connection.execute(f'SELECT COUNT(*) FROM `{table}`').fetchone()[0]
                  for table in ('person', 'member', 'gym_location', 'employee')}
        print(f'Created {args.database.name}: {tables} tables; row counts: {counts}')


if __name__ == '__main__':
    main()
