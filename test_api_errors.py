"""Offline API error tests: distinguish billing/rates and never echo a secret."""
import contextlib
import io
import json
import unittest
from urllib.error import HTTPError
from db_bot import OpenAIClient, api_error_message, estimate_cost, print_record
import db_bot
from pathlib import Path
from unittest.mock import Mock, patch


class APIErrorTests(unittest.TestCase):
    def message(self, code, kind='insufficient_quota', retry_after=None):
        return api_error_message(429, json.dumps({'error': {'code': code, 'type': kind}}), retry_after)

    def test_empty_credit_balance(self):
        self.assertIn('credit balance is empty', self.message('credit_balance_exhausted'))

    def test_project_spending_limit(self):
        self.assertIn('project has reached its spending limit', self.message('project_spend_limit_exceeded'))

    def test_organization_limits(self):
        self.assertIn('organization has reached its spending limit', self.message('organization_spend_limit_exceeded'))
        self.assertIn('assigned usage limit', self.message('organization_usage_limit_exceeded'))

    def test_legacy_quota(self):
        self.assertIn('quota is unavailable', self.message('insufficient_quota'))
        self.assertIn('organization/project limits', self.message(None))

    def test_rate_limit_retry_after(self):
        self.assertIn('Wait at least 12 seconds', self.message('slow_down', 'rate_limit_error', '12'))

    def test_unrecognized_body_does_not_echo_secret(self):
        body = json.dumps({'error': {'message': 'Your key is fake-secret', 'code': 'fake-secret'}})
        self.assertNotIn('fake-secret', api_error_message(429, body))
        self.assertIn('HTTP 429', api_error_message(429, b'<html>unknown response</html>'))

    def test_client_maps_http_error(self):
        class FakeOpener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 429, 'error', {},
                                io.BytesIO(b'{"error":{"code":"credit_balance_exhausted","type":"insufficient_quota"}}'))
        client = OpenAIClient.__new__(OpenAIClient)
        client.key, client.model, client.opener = 'fake-secret', 'gpt-4o-mini', FakeOpener()
        with self.assertRaisesRegex(RuntimeError, 'credit balance is empty'):
            client.create('Test', 'Test')

    def test_failed_request_has_no_cost_estimate(self):
        self.assertIsNone(estimate_cost('gpt-4o-mini', []))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            print_record({'status': 'error', 'answer': 'OpenAI API access blocked',
                          'generated_sql': None, 'estimated_cost_usd': None})
        self.assertIn('Error:', output.getvalue())
        self.assertNotIn('Estimated API cost', output.getvalue())

    def test_interactive_cli_stops_after_api_failure(self):
        database = Mock()
        record = {'status': 'error', 'answer': 'OpenAI API access blocked',
                  'generated_sql': None, 'estimated_cost_usd': None}
        bot = Mock()
        bot.ask.return_value = record
        with patch.object(db_bot.sys, 'argv', ['db_bot.py']), \
             patch.object(db_bot, 'SQLiteGymDatabase', return_value=database), \
             patch.object(db_bot, 'OpenAIClient'), \
             patch.object(db_bot, 'GymBot', return_value=bot), \
             patch.object(db_bot, 'save_record', return_value=Path('fake-run.json')), \
             patch('builtins.input', return_value='A question') as question_input, \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                db_bot.main()
            self.assertEqual(stopped.exception.code, 1)
            question_input.assert_called_once()
            bot.ask.assert_called_once()
            database.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
