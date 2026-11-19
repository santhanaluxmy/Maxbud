"""UI-flow integration contracts using isolated SQLite and mocked extraction."""
import json
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select
import test_family
from app.core.config import get_settings
from app.models.ai import MerchantRule
from app.models.finance import IncomeSource


class UiPolishTests(unittest.TestCase):
    for _name in ['tearDown', 'close_mysql', 'email', 'payload', 'register', 'headers', 'get']:
        locals()[_name] = getattr(test_family.FamilyTests, _name)

    def setUp(self):
        test_family.FamilyTests.setUp(self)
        scratch = tempfile.TemporaryDirectory(prefix='maxbud-ui-receipts-')
        self.addCleanup(scratch.cleanup)
        setting = patch.object(get_settings(), 'RECEIPT_STORAGE_DIR', scratch.name)
        setting.start()
        self.addCleanup(setting.stop)

    def post(self, path, body):
        return self.client.post(path, json=body, headers=self.headers(self.owner))

    def test_four_step_setup_skips_income_and_budget_allocation_leaves_balances_intact(self):
        self.assertEqual(self.post('/onboarding/about-you', {'full_name': 'UI Owner', 'currency': 'LKR'}).status_code, 200)
        self.assertEqual(self.post('/onboarding/accounts', {'accounts': [
            {'name': 'Cash', 'kind': 'cash', 'opening_balance': '1000.10'},
            {'name': 'Bank', 'kind': 'bank', 'opening_balance': '500.20'},
        ]}).status_code, 200)
        before = self.get('/accounts').json()
        self.assertEqual(self.get('/onboarding/status').json()['current_step'], 4)
        self.assertEqual(self.post('/onboarding/accounts', {'accounts': [{'name': 'Duplicate', 'kind': 'cash'}]}).status_code, 409)
        self.assertEqual(self.post('/onboarding/budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '2000'}]}).status_code, 200)
        self.assertEqual(self.get('/accounts').json(), before)
        self.assertEqual(self.post('/onboarding/goals', {'goals': []}).status_code, 200)
        self.assertTrue(self.get('/onboarding/status').json()['onboarding_completed'])
        self.assertEqual(self.get('/accounts').json(), before)
        self.assertEqual(list(self.db.scalars(select(IncomeSource).where(IncomeSource.user_id == self.owner['user']['id']))), [])

    def test_legacy_income_step_and_saved_income_remain_compatible(self):
        self.assertEqual(self.post('/onboarding/about-you', {'full_name': 'Legacy Owner'}).status_code, 200)
        self.assertEqual(self.post('/onboarding/income', {'sources': [{'name': 'Existing Salary', 'amount': '80000'}]}).status_code, 200)
        self.assertEqual(self.get('/onboarding/status').json()['current_step'], 3)
        self.assertEqual(self.post('/onboarding/accounts', {'accounts': [{'name': 'Existing Cash', 'kind': 'cash', 'opening_balance': '500'}]}).status_code, 200)
        income = self.db.scalar(select(IncomeSource).where(IncomeSource.user_id == self.owner['user']['id']))
        self.assertEqual(income.name, 'Existing Salary')
        self.assertEqual(str(income.amount), '80000.00')
        self.assertEqual(self.get('/accounts').json()['items'][0]['current_balance'], '500.00')

    def test_merchant_suggestions_are_private_and_scans_save_only_once_on_confirmation(self):
        self.db.add_all([
            MerchantRule(user_id=self.owner['user']['id'], merchant='known store', category='Food'),
            MerchantRule(user_id=self.other['user']['id'], merchant='private store', category='Other'),
        ])
        self.db.commit()
        self.assertEqual(self.get('/ai/merchants').json(), [{'merchant': 'known store', 'category': 'Food'}])
        self.assertEqual(self.client.get('/ai/merchants').status_code, 401)
        self.assertEqual(self.post('/onboarding/about-you', {'full_name': 'Scan Owner'}).status_code, 200)
        self.assertEqual(self.post('/onboarding/accounts', {'accounts': [{'name': 'Cash', 'kind': 'cash', 'opening_balance': '1000'}]}).status_code, 200)
        self.assertEqual(self.post('/onboarding/budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '500'}]}).status_code, 200)
        account = self.get('/accounts').json()['items'][0]
        image = BytesIO()
        Image.new('RGB', (40, 40), 'white').save(image, format='PNG')
        extracted = {'merchant': 'New Store', 'date': '2026-11-19', 'total': 25, 'currency': None, 'category': 'Food', 'items': [{'name': 'Rice', 'amount': 25}]}
        with patch('app.routers.ai.complete', return_value=json.dumps(extracted)):
            response = self.client.post('/ai/receipts', files={'file': ('receipt.png', image.getvalue(), 'image/png')}, headers=self.headers(self.owner))
        self.assertEqual(response.status_code, 201, response.text)
        receipt = response.json()
        self.assertEqual(self.get('/transactions').json(), [])
        self.assertEqual(self.get('/accounts').json()['items'][0]['current_balance'], '1000.00')
        reviewed = {**receipt['data'], 'currency': 'LKR', 'merchant': 'Reviewed Store', 'account_id': account['id']}
        invalid = self.post(f"/ai/receipts/{receipt['id']}/confirm", {**reviewed, 'category': 'Unknown category'})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.get('/transactions').json(), [])
        first = self.post(f"/ai/receipts/{receipt['id']}/confirm", reviewed)
        retry = self.post(f"/ai/receipts/{receipt['id']}/confirm", reviewed)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['transaction_id'], retry.json()['transaction_id'])
        self.assertEqual(len(self.get('/transactions').json()), 1)
        self.assertEqual(self.get('/accounts').json()['items'][0]['current_balance'], '975.00')
        self.assertIn({'merchant': 'reviewed store', 'category': 'Food'}, self.get('/ai/merchants').json())
