"""Natural-language questions -> generated SQL -> database results -> grounded answer.

Run `python db_bot.py --help`. No API keys or passwords are printed or logged.
"""
import argparse
from datetime import date, datetime
from decimal import Decimal
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from prompting import ANSWER_PROMPT, PLAN_TOOL, STRATEGIES, SYSTEM_PROMPT, build_prompt

ROOT = Path(__file__).resolve().parent
if (ROOT / '.deps').is_dir():
    sys.path.insert(0, str(ROOT / '.deps'))
DEFAULT_MODEL = 'gpt-4o-mini'
MAX_ROWS = 200
CONTENT_COLUMNS = {
    'gym_location': ['name'], 'subscription': ['subscription_type', 'status'],
    'membership': ['plan_name'], 'equipment': ['name', 'brand', 'status'],
    'employee': ['employee_type', 'employment_status'], 'check_in': ['entry_method'],
}


def json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    raise TypeError(f'Cannot serialize {type(value).__name__}')


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        raise RuntimeError(f'Missing {Path(path).name}. See README.md for setup.') from None
    except (ValueError, UnicodeError):
        raise RuntimeError(f'{Path(path).name} must contain a valid JSON object.') from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_error_message(status, body, retry_after=None):
    """Map documented error codes without echoing response text or credentials."""
    try:
        details = json.loads(body).get('error', {})
        code, kind = details.get('code'), details.get('type')
    except (ValueError, UnicodeError, AttributeError):
        code = kind = None
    messages = {
        'credit_balance_exhausted': 'Your OpenAI API credit balance is empty. Add API credits at https://platform.openai.com/settings/organization/billing/overview, then restart the app.',
        'insufficient_quota': 'Your OpenAI API quota is unavailable. Check API billing credits and project limits, then restart the app.',
        'project_spend_limit_exceeded': 'Your OpenAI project has reached its spending limit. Check the project limits in the API dashboard.',
        'organization_spend_limit_exceeded': 'Your OpenAI organization has reached its spending limit. Check organization limits in the API dashboard.',
        'organization_usage_limit_exceeded': 'Your OpenAI organization has reached its assigned usage limit. Check the API dashboard or contact OpenAI support.',
    }
    if code in messages:
        return 'OpenAI API access blocked: ' + messages[code]
    if code in ('rate_limit_exceeded', 'slow_down') or kind == 'rate_limit_error':
        wait = f' Wait at least {retry_after} seconds.' if retry_after and str(retry_after).isdigit() else ' Wait before trying again.'
        return 'OpenAI API rate limit reached.' + wait
    if kind == 'insufficient_quota':
        return 'OpenAI API access blocked: Check API billing credits and organization/project limits, then restart the app.'
    hints = {401: 'Check your API key.', 429: 'Check API billing credits or rate limits.',
             403: 'The account cannot use this model.', 400: 'Check the API request/model configuration.'}
    return f'OpenAI HTTP {status}. {hints.get(status, "Request failed.")}'


class OpenAIClient:
    def __init__(self, config_path, model=DEFAULT_MODEL):
        config = load_json(config_path) if Path(config_path).exists() else {}
        self.key = os.getenv('OPENAI_API_KEY') or config.get('openaiKey')
        if not isinstance(self.key, str) or not self.key.strip():
            raise RuntimeError('Set OPENAI_API_KEY or the existing config.json openaiKey field.')
        self.model = model
        self.opener = build_opener(NoRedirect())

    def create(self, instructions, input_text, tools=None):
        payload = {'model': self.model, 'instructions': instructions,
                   'input': input_text, 'store': False, 'max_output_tokens': 1600}
        if tools:
            payload.update(tools=tools, tool_choice={'type': 'function', 'name': 'plan_database_query'},
                           parallel_tool_calls=False)
        request = Request('https://api.openai.com/v1/responses',
                          data=json.dumps(payload).encode('utf-8'),
                          headers={'Authorization': 'Bearer ' + self.key,
                                   'Content-Type': 'application/json'}, method='POST')
        try:
            with self.opener.open(request, timeout=60) as response:
                result = json.load(response)
        except HTTPError as error:
            raise RuntimeError(api_error_message(error.code, error.read(), error.headers.get('Retry-After'))) from None
        except (URLError, TimeoutError, OSError):
            raise RuntimeError('OpenAI request failed. Check your network connection.') from None
        if result.get('status') != 'completed':
            raise RuntimeError('The model response was incomplete; no SQL was executed.')
        return result

    def plan(self, prompt):
        result = self.create(SYSTEM_PROMPT, prompt, [PLAN_TOOL])
        calls = [item for item in result.get('output', []) if item.get('type') == 'function_call']
        if len(calls) != 1 or calls[0].get('name') != 'plan_database_query':
            raise RuntimeError('The model did not return the expected SQL plan.')
        plan = json.loads(calls[0]['arguments'])
        if plan.get('status') not in ('query', 'clarify', 'unsupported') or not isinstance(plan.get('explanation'), str):
            raise RuntimeError('The SQL plan was invalid.')
        if plan['status'] == 'query' and not isinstance(plan.get('sql'), str):
            raise RuntimeError('A query plan must include SQL.')
        if plan['status'] != 'query' and plan.get('sql') is not None:
            raise RuntimeError('A non-query plan must not include SQL.')
        return plan, result.get('usage', {})

    def answer(self, question, explanation, sql, query_result):
        result = self.create(ANSWER_PROMPT, json.dumps({
            'question': question, 'sql_explanation': explanation, 'executed_sql': sql,
            'query_result': query_result,
        }, default=json_value))
        texts = [part['text'] for item in result.get('output', []) if item.get('type') == 'message'
                 for part in item.get('content', []) if part.get('type') == 'output_text']
        if not texts:
            raise RuntimeError('The model did not return a plain-language answer.')
        return '\n'.join(texts), result.get('usage', {})


def quote_identifier(name):
    return '`' + name.replace('`', '``') + '`'


def validate_sql(sql, allowed_tables, database_name='', dialect='sqlite'):
    import sqlglot
    from sqlglot import exp
    from sqlglot.errors import ParseError

    # MySQL executable comments can hide operations from other parsers.
    if '/*' in sql or '*/' in sql:
        raise ValueError('SQL comments are not accepted.')
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except ParseError:
        raise ValueError('Generated SQL could not be parsed.') from None
    if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise ValueError('Only one SELECT query is allowed.')
    tree = statements[0]
    prohibited = {'Insert', 'Update', 'Delete', 'Create', 'Drop', 'Alter', 'Merge', 'Command',
                  'Into', 'Lock', 'Set', 'Use', 'Transaction', 'Commit', 'Rollback',
                  'Grant', 'Revoke', 'Parameter', 'SessionParameter', 'PropertyEQ'}
    dangerous_functions = {'SLEEP', 'BENCHMARK', 'LOAD_FILE', 'GET_LOCK', 'RELEASE_LOCK',
                           'IS_FREE_LOCK', 'IS_USED_LOCK', 'LAST_INSERT_ID',
                           'LOAD_EXTENSION', 'READFILE', 'WRITEFILE'}
    safe_anonymous = {'DATE_FORMAT', 'TIMESTAMPDIFF', 'DATEDIFF', 'IFNULL', 'IF',
                      'GROUP_CONCAT', 'FORMAT', 'DAYOFWEEK', 'WEEKDAY', 'MONTHNAME', 'DAYNAME'}
    for node in tree.walk():
        if type(node).__name__ in prohibited:
            raise ValueError('Query contains an operation that is not allowed.')
        if isinstance(node, exp.With) and node.args.get('recursive'):
            raise ValueError('Recursive queries are not supported.')
        if isinstance(node, exp.Func):
            name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
            if name in dangerous_functions or (isinstance(node, exp.Anonymous) and name not in safe_anonymous):
                raise ValueError(f'Function {name} is not allowed.')
    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    allowed = {table.lower() for table in allowed_tables}
    for table in tree.find_all(exp.Table):
        if table.catalog or (table.db and table.db.lower() != database_name.lower()):
            raise ValueError('Queries may only access the configured gym database.')
        if table.name.lower() not in allowed | cte_names:
            raise ValueError(f'Table {table.name} is not in the gym schema.')
    # Bound the result before reading it; aggregates still compute over the full input.
    # Keep a smaller model-proposed literal limit, otherwise use MAX_ROWS + 1.
    limit = tree.args.get('limit')
    existing = limit.expression if limit else None
    if not isinstance(existing, exp.Literal) or not existing.is_int or int(existing.this) > MAX_ROWS + 1:
        tree = tree.limit(MAX_ROWS + 1)
    return tree.sql(dialect=dialect, comments=False)


class SQLiteGymDatabase:
    dialect = 'sqlite'

    def __init__(self, path):
        import sqlite3
        path = Path(path).resolve()
        if not path.exists():
            raise RuntimeError('Run python init_db.py to create the SQLite database first.')
        self.name = path.name
        # URI read-only mode makes generated queries unable to change the DB file.
        self.connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        self.connection.execute('PRAGMA query_only = ON')
        self.tables = [row[0] for row in self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    def context(self):
        schema = '\n\n'.join(row[0] + ';' for row in self.connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"))
        samples = {}
        for table, columns in CONTENT_COLUMNS.items():
            if table not in self.tables:
                continue
            samples[table] = {}
            for column in columns:
                sql = f'SELECT DISTINCT {quote_identifier(column)} FROM {quote_identifier(table)} WHERE {quote_identifier(column)} IS NOT NULL LIMIT 5'
                samples[table][column] = [row[0] for row in self.connection.execute(sql)]
        return schema, samples

    def query(self, sql):
        import sqlite3
        executed_sql = validate_sql(sql, self.tables, dialect=self.dialect)
        deadline = time.monotonic() + 5
        self.connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        try:
            cursor = self.connection.execute(executed_sql)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(MAX_ROWS + 1)
            cursor.close()
            return executed_sql, {'columns': columns, 'rows': rows[:MAX_ROWS], 'truncated': len(rows) > MAX_ROWS}
        except sqlite3.Error as error:
            raise RuntimeError(f'SQLite rejected the generated query: {error}') from None
        finally:
            self.connection.set_progress_handler(None, 0)

    def close(self):
        self.connection.close()


class GymDatabase:
    dialect = 'mysql'
    def __init__(self, config_path):
        try:
            import mysql.connector
        except ImportError:
            raise RuntimeError('Install requirements.txt before connecting to MySQL.') from None
        config = load_json(config_path)
        self.name = config.get('database', 'gym_management')
        try:
            self.connection = mysql.connector.connect(
                host=config.get('host', '127.0.0.1'), port=int(config.get('port', 3306)),
                user=config['user'], password=config.get('password', ''), database=self.name,
                autocommit=True, connection_timeout=10, allow_local_infile=False,
            )
            with self.connection.cursor() as cursor:
                cursor.execute('SET SESSION MAX_EXECUTION_TIME = 5000')
                cursor.execute('SHOW TABLES')
                self.tables = [row[0] for row in cursor.fetchall()]
            if not self.tables:
                raise RuntimeError('The configured database has no tables.')
        except mysql.connector.Error as error:
            raise RuntimeError(f'MySQL connection failed (error {error.errno}). Check db_config.json and the running server.') from None

    def context(self):
        schema, samples = [], {}
        with self.connection.cursor() as cursor:
            for table in sorted(self.tables):
                cursor.execute('SHOW CREATE TABLE ' + quote_identifier(table))
                schema.append(cursor.fetchone()[1] + ';')
            for table, columns in CONTENT_COLUMNS.items():
                if table not in self.tables:
                    continue
                samples[table] = {}
                for column in columns:
                    cursor.execute(f'SELECT DISTINCT {quote_identifier(column)} FROM {quote_identifier(table)} WHERE {quote_identifier(column)} IS NOT NULL LIMIT 5')
                    samples[table][column] = [row[0] for row in cursor.fetchall()]
        return '\n\n'.join(schema), samples

    def query(self, sql):
        import mysql.connector
        executed_sql = validate_sql(sql, self.tables, self.name, dialect=self.dialect)
        try:
            self.connection.start_transaction(readonly=True)
            with self.connection.cursor() as cursor:
                cursor.execute(executed_sql)
                columns = list(cursor.column_names)
                rows = cursor.fetchmany(MAX_ROWS + 1)
                # Drain any unread rows before ending the read-only transaction.
                cursor.fetchall()
            return executed_sql, {'columns': columns, 'rows': rows[:MAX_ROWS],
                                  'truncated': len(rows) > MAX_ROWS}
        except mysql.connector.Error as error:
            raise RuntimeError(f'MySQL rejected the generated query (error {error.errno}): {error.msg}') from None
        finally:
            self.connection.rollback()

    def close(self):
        self.connection.close()


def estimate_cost(model, usages):
    if not usages or model not in ('gpt-4o-mini', 'gpt-4o-mini-2024-07-18'):
        return None
    total = 0
    for usage in usages:
        cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
        total += ((usage.get('input_tokens', 0) - cached) * 0.15 + cached * 0.075
                  + usage.get('output_tokens', 0) * 0.60) / 1_000_000
    return round(total, 8)


class GymBot:
    def __init__(self, db, client, today=None):
        self.db, self.client = db, client
        self.today = today or date.today().isoformat()
        self.schema, self.samples = db.context()

    def ask(self, question, strategy='zero_shot'):
        start = time.monotonic()
        record = {'question': question, 'strategy': strategy, 'model': self.client.model,
                  'current_date': self.today, 'run_at': datetime.now().astimezone().isoformat(),
                  'generated_sql': None, 'executed_sql': None, 'result': None, 'usage': []}
        try:
            plan, usage = self.client.plan(build_prompt(self.schema, self.samples, question, strategy, self.today, self.db.dialect))
            record.update(status=plan['status'], explanation=plan['explanation'], generated_sql=plan['sql'])
            record['usage'].append(usage)
            if plan['status'] == 'query':
                sql, rows = self.db.query(plan['sql'])
                record.update(executed_sql=sql, result=rows)
                answer, usage = self.client.answer(question, plan['explanation'], sql, rows)
                record['usage'].append(usage)
                record.update(answer=answer, status='answered')
            else:
                record['answer'] = plan['explanation']
        except (RuntimeError, ValueError) as error:
            record.update(status='error', answer=str(error))
        record['elapsed_seconds'] = round(time.monotonic() - start, 3)
        record['estimated_cost_usd'] = estimate_cost(self.client.model, record['usage'])
        return record


def save_record(record, directory=ROOT / 'runs'):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid4().hex[:8] + '.json')
    path.write_text(json.dumps(record, indent=2, default=json_value), encoding='utf-8')
    return path


def print_record(record):
    if record.get('generated_sql'):
        print('\nGenerated SQL:\n' + record['generated_sql'])
    label = 'Error' if record['status'] == 'error' else 'Answer'
    print(f'\n{label}: ' + record['answer'])
    if record.get('estimated_cost_usd') is not None:
        print(f'Estimated API cost: ${record["estimated_cost_usd"]:.6f}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question', '-q', help='Ask one question instead of starting the interactive prompt.')
    parser.add_argument('--strategy', choices=STRATEGIES, default='zero_shot')
    parser.add_argument('--model', default=DEFAULT_MODEL)
    parser.add_argument('--config', type=Path, default=ROOT / 'config.json')
    parser.add_argument('--db-config', type=Path, default=ROOT / 'db_config.json')
    parser.add_argument('--engine', choices=('sqlite', 'mysql'), default='sqlite')
    parser.add_argument('--database', type=Path, default=ROOT / 'gym.db', help='SQLite database file.')
    parser.add_argument('--today', help='ISO date for repeatable relative-date experiments.')
    parser.add_argument('--check-db', action='store_true', help='Check database tables and row counts without calling OpenAI.')
    args = parser.parse_args()
    db = SQLiteGymDatabase(args.database) if args.engine == 'sqlite' else GymDatabase(args.db_config)
    try:
        if args.check_db:
            print(f'Database: {db.name}')
            for table in sorted(db.tables):
                _, result = db.query('SELECT COUNT(*) AS row_count FROM ' + quote_identifier(table))
                print(f'{table}: {result["rows"][0][0]} rows')
            return
        bot = GymBot(db, OpenAIClient(args.config, args.model), args.today)
        print(f'Gym SQL assistant | {args.model} | {args.strategy}')
        print('Type a gym database question. Type exit to finish.')
        while True:
            question = args.question or input('\nQuestion: ').strip()
            if question.lower() in ('exit', 'quit'):
                break
            if not question:
                continue
            record = bot.ask(question, args.strategy)
            print_record(record)
            print('Run saved: ' + str(save_record(record)))
            if record['status'] == 'error' and record['answer'].startswith('OpenAI'):
                print('Resolve the API access issue, then restart the app. No automatic retries were sent.')
                sys.exit(1)
            if args.question:
                if record['status'] == 'error':
                    sys.exit(1)
                break
    finally:
        db.close()


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, KeyError, OSError) as error:
        print(f'Stopped: {error}', file=sys.stderr)
        sys.exit(1)
    except (EOFError, KeyboardInterrupt):
        print('\nFinished.')
