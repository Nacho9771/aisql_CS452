"""Offline tests: SQL boundaries, database integrity, and honest pipeline behavior."""
import hashlib
from pathlib import Path
import unittest
import sqlite3
from db_bot import (ROOT, GymBot, SQLiteGymDatabase, estimate_cost, validate_sql)
from prompting import build_prompt
from init_db import seed, sqlite_schema


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        # Use a controlled fixture so changing the user's demo data doesn't invalidate
        # tests about ties, empty locations, and other deliberately constructed cases.
        self.db = SQLiteGymDatabase.__new__(SQLiteGymDatabase)
        self.db.name = ':memory:'
        self.db.connection = sqlite3.connect(':memory:')
        self.db.connection.executescript(sqlite_schema())
        seed(self.db.connection)
        self.db.tables = [row[0] for row in self.db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        self.db.connection.execute('PRAGMA query_only = ON')

    def tearDown(self):
        self.db.close()

    def test_seed_integrity(self):
        self.assertEqual(self.db.connection.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(len(self.db.tables), 15)
        _, result = self.db.query('SELECT COUNT(*) FROM member')
        self.assertEqual(result['rows'], [(60,)])

    def test_readonly_file(self):
        with self.assertRaises(Exception):
            self.db.connection.execute('DELETE FROM member')
        actual = SQLiteGymDatabase(ROOT / 'gym.db')
        try:
            with self.assertRaises(sqlite3.OperationalError):
                actual.connection.execute('DELETE FROM member')
        finally:
            actual.close()

    def test_sql_boundaries(self):
        bad = [
            'DELETE FROM member', 'SELECT * FROM member; DROP TABLE member',
            'SELECT * FROM sqlite_master', 'SELECT * FROM other.member',
            "SELECT load_extension('evil')", 'SELECT SLEEP(100)',
            'SELECT * FROM member FOR UPDATE', 'SELECT @secret',
            "SELECT * INTO OUTFILE '/tmp/out' FROM member", 'SELECT /* hidden */ * FROM member',
            'WITH RECURSIVE x AS (SELECT 1 UNION ALL SELECT 1 FROM x) SELECT * FROM x',
        ]
        for sql in bad:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                validate_sql(sql, self.db.tables)

    def test_valid_join_cte_and_limit(self):
        _, result = self.db.query('WITH counts AS (SELECT home_location, COUNT(*) AS n FROM member GROUP BY home_location) SELECT SUM(n) FROM counts')
        self.assertEqual(result['rows'], [(60,)])
        bounded = validate_sql('SELECT * FROM member LIMIT -1', self.db.tables)
        self.assertIn('LIMIT 201', bounded)

    def test_tied_birthdays(self):
        _, result = self.db.query("WITH x AS (SELECT strftime('%m-%d', DOB) AS birthday, COUNT(*) AS n FROM person WHERE DOB IS NOT NULL GROUP BY birthday) SELECT birthday, n FROM x WHERE n = (SELECT MAX(n) FROM x) ORDER BY birthday")
        self.assertEqual(result['rows'], [('01-20', 10), ('07-04', 10)])

    def test_empty_gym_appears_in_left_join(self):
        _, result = self.db.query('SELECT g.name, COUNT(m.member_id) FROM gym_location g LEFT JOIN member m ON m.home_location = g.location_id GROUP BY g.location_id, g.name ORDER BY g.name')
        self.assertIn(('Springville Annex', 0), result['rows'])

    def test_fake_model_pipeline_and_refusal(self):
        class FakeModel:
            model = 'gpt-4o-mini'
            def plan(self, prompt):
                return {'status': 'query', 'sql': 'SELECT COUNT(*) AS members FROM member', 'explanation': 'All members.'}, {'input_tokens': 100, 'output_tokens': 20}
            def answer(self, question, explanation, sql, result):
                assert result['rows'] == [(60,)]
                return 'There are 60 members.', {'input_tokens': 50, 'output_tokens': 10}
        record = GymBot(self.db, FakeModel(), '2026-10-12').ask('How many members?')
        self.assertEqual(record['status'], 'answered')
        self.assertEqual(record['answer'], 'There are 60 members.')
        self.assertEqual(len(record['usage']), 2)
        class MissingHistory(FakeModel):
            def plan(self, prompt):
                return {'status': 'unsupported', 'sql': None, 'explanation': 'No upgrade history is stored.'}, {}
            def answer(self, *args):
                raise AssertionError('A missing-data plan must not execute/answer from fabricated results')
        record = GymBot(self.db, MissingHistory()).ask('Who upgraded?')
        self.assertEqual(record['status'], 'unsupported')
        self.assertIsNone(record['result'])


class PromptTests(unittest.TestCase):
    def test_prompt_strategies(self):
        zero = build_prompt('schema', {}, 'question', 'zero_shot', '2026-10-12')
        single = build_prompt('schema', {}, 'question', 'single_domain', '2026-10-12')
        cross = build_prompt('schema', {}, 'question', 'cross_domain', '2026-10-12')
        self.assertNotIn('Demonstrations from', zero)
        self.assertIn('Demonstrations from the TARGET', single)
        self.assertIn('CREATE TABLE branch', cross)
        self.assertNotIn('CREATE TABLE branch', single)

    def test_cost_estimate(self):
        self.assertEqual(estimate_cost('gpt-4o-mini', [{'input_tokens': 1000000, 'output_tokens': 1000000}]), 0.75)
        self.assertIsNone(estimate_cost('unknown-model', []))


if __name__ == '__main__':
    unittest.main()
