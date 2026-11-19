"""Core finance regressions; disposable SQLite unless the explicit test fixture is selected."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
import unittest

from sqlalchemy import func, select

import test_family
from app.models.ai import AIScan
from app.models.finance import Account, GoalContribution, Transaction
from app.models.reminder import ReminderPayment


class CoreFinanceTests(test_family.FamilyTests):
    def post(self, path, body, person=None):
        return self.client.post(path, json=body, headers=self.headers(person or self.owner))

    def put(self, path, body, person=None):
        return self.client.put(path, json=body, headers=self.headers(person or self.owner))

    def delete(self, path, person=None):
        return self.client.delete(path, headers=self.headers(person or self.owner))

    def account(self, amount='100', name='Cash'):
        response = self.post('/accounts', {'name': name, 'kind': 'cash', 'opening_balance': amount})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def transaction(self, account, kind, amount, category='Food'):
        body = {'account_id': account, 'kind': kind, 'amount': amount, 'category': category}
        response = self.post('/transactions', body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json(), body

    def balance(self, account):
        return Decimal(self.get(f'/accounts/{account}').json()['current_balance'])

    def goal(self, saved='0', target='100', scope='me'):
        response = self.post('/goals?scope=' + scope, {
            'name': 'Emergency', 'target_amount': target, 'saved_amount': saved,
        })
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def test_personal_contribution_replay_preserves_baseline_and_reserves_once(self):
        account = self.account()
        goal = self.goal(saved='20')
        payload = {'amount': '10', 'request_id': 'allocation-one', 'account_id': account}
        for _ in range(2):
            response = self.post(f'/goals/{goal}/contribute', payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(Decimal(response.json()['saved_amount']), 30)
        ledger = self.db.scalars(select(GoalContribution).where(GoalContribution.current_goal_id == goal)).all()
        self.assertEqual(len(ledger), 1)
        self.assertEqual((ledger[0].user_id, ledger[0].amount), (self.owner['user']['id'], Decimal('10')))
        dashboard = self.get('/dashboard').json()
        self.assertEqual(Decimal(dashboard['total_savings_allocated']), 30)
        self.assertEqual(Decimal(dashboard['shared_savings_allocated']), 0)
        self.assertEqual(Decimal(dashboard['safe_to_spend_estimate']), 70)
        self.assertEqual(self.balance(account), 90)
        self.assertEqual(self.get('/transactions').json(), [])

    def test_contribution_replay_after_completion_and_archive(self):
        goal = self.goal(target='10')
        payload = {'amount': '10', 'request_id': 'complete-once', 'account_id': self.account()}
        for _ in range(2):
            response = self.post(f'/goals/{goal}/contribute', payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'completed')
        self.assertEqual(self.client.patch(f'/goals/{goal}', json={'status': 'archived'}, headers=self.headers(self.owner)).status_code, 200)
        response = self.post(f'/goals/{goal}/contribute', payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'archived')
        self.assertEqual(Decimal(response.json()['saved_amount']), 10)
        self.assertEqual(self.post(f'/goals/{goal}/contribute', payload | {'request_id': 'another'}).status_code, 409)

    def test_contribution_key_conflicts_and_cross_user_isolation(self):
        first, second = self.goal(), self.goal()
        payload = {'amount': '10', 'request_id': 'one-key', 'account_id': self.account()}
        self.assertEqual(self.post(f'/goals/{first}/contribute', payload).status_code, 200)
        self.assertEqual(self.post(f'/goals/{first}/contribute', payload | {'amount': '11'}).status_code, 409)
        self.assertEqual(self.post(f'/goals/{second}/contribute', payload).status_code, 409)
        self.assertEqual(self.post(f'/goals/{first}/contribute', payload, self.other).status_code, 404)
        amounts = {g['id']: Decimal(g['saved_amount']) for g in self.get('/goals').json()}
        self.assertEqual((amounts[first], amounts[second]), (10, 0))

    def test_personal_and_shared_contribution_keys_cannot_conflict(self):
        personal = self.goal()
        self.enable_family_pack()
        shared = self.goal(scope='family')
        payload = {'amount': '10', 'request_id': 'cross-scope', 'account_id': self.account()}
        self.assertEqual(self.post(f'/goals/{personal}/contribute', payload).status_code, 200)
        self.assertEqual(self.post(f'/goals/{shared}/contribute', payload).status_code, 409)
        self.assertEqual(Decimal(self.get('/goals?scope=family').json()[0]['saved_amount']), 0)

    def test_new_personal_contributions_require_account_and_retry_key(self):
        goal = self.goal(saved='5')
        account = self.account()
        for payload in [{'amount': '10'}, {'amount': '10', 'account_id': account},
                        {'amount': '10', 'request_id': 'missing-account'}]:
            self.assertEqual(self.post(f'/goals/{goal}/contribute', payload).status_code, 422)
        self.assertEqual(Decimal(self.get('/goals').json()[0]['saved_amount']), 5)
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(self.db.scalar(select(func.count(GoalContribution.id))), 0)

    def test_failed_contribution_commit_rolls_back_amount_and_retry_key(self):
        goal = self.goal(saved='5')
        payload = {'amount': '10', 'request_id': 'retry-after-failure', 'account_id': self.account()}
        with patch.object(self.db, 'commit', side_effect=RuntimeError('synthetic commit failure')):
            with self.assertRaises(RuntimeError):
                self.post(f'/goals/{goal}/contribute', payload)
        self.assertEqual(Decimal(self.get('/goals').json()[0]['saved_amount']), 5)
        self.assertEqual(self.db.scalar(select(func.count(GoalContribution.id))), 0)
        response = self.post(f'/goals/{goal}/contribute', payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(Decimal(response.json()['saved_amount']), 15)

    def test_deleting_spent_income_is_rejected_without_changing_ledger(self):
        account = self.account('0')
        income, _ = self.transaction(account, 'income', '100', 'Salary')
        self.transaction(account, 'expense', '80')
        response = self.delete(f"/transactions/{income['id']}")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.balance(account), 20)
        self.assertEqual(self.get(f"/transactions/{income['id']}").status_code, 200)

    def test_reducing_or_moving_spent_income_rolls_back_both_accounts(self):
        source, destination = self.account('0'), self.account('0', 'Bank')
        income, body = self.transaction(source, 'income', '100', 'Salary')
        self.transaction(source, 'expense', '80')
        for changes in [{'amount': '10'}, {'account_id': destination}, {'kind': 'expense', 'amount': '1'}]:
            with self.subTest(changes=changes):
                response = self.put(f"/transactions/{income['id']}", body | changes)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual((self.balance(source), self.balance(destination)), (20, 0))
        allowed = self.put(f"/transactions/{income['id']}", body | {'amount': '80'})
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(self.balance(source), 0)

    def test_valid_income_move_and_delete_recalculate_balances(self):
        source, destination = self.account(), self.account('0', 'Bank')
        income, body = self.transaction(source, 'income', '25', 'Salary')
        response = self.put(f"/transactions/{income['id']}", body | {'account_id': destination, 'amount': '20'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((self.balance(source), self.balance(destination)), (100, 20))
        self.assertEqual(self.delete(f"/transactions/{income['id']}").status_code, 200)
        self.assertEqual(self.balance(destination), 0)

    def test_opening_balance_reduction_cannot_overdraw(self):
        account = self.account()
        self.transaction(account, 'expense', '80')
        response = self.client.patch(f'/accounts/{account}', json={'opening_balance': '10', 'name': 'Changed'}, headers=self.headers(self.owner))
        self.assertEqual(response.status_code, 422, response.text)
        row = self.get(f'/accounts/{account}').json()
        self.assertEqual((row['name'], Decimal(row['opening_balance']), self.balance(account)), ('Cash', 100, 20))
        allowed = self.client.patch(f'/accounts/{account}', json={'opening_balance': '80'}, headers=self.headers(self.owner))
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual(self.balance(account), 0)

    def test_existing_negative_balance_can_be_improved_without_rewriting_history(self):
        account = self.account()
        # Historical fixture intentionally bypasses API rules; never genuine data.
        self.db.add(Transaction(user_id=self.owner['user']['id'], account_id=account, kind='expense', category='Food', amount=Decimal('120'), txn_date=date.today()))
        self.db.commit()
        for body, status, expected in [({'name': 'Legacy cash'}, 200, -20), ({'opening_balance': '90'}, 422, -20), ({'opening_balance': '110'}, 200, -10)]:
            response = self.client.patch(f'/accounts/{account}', json=body, headers=self.headers(self.owner))
            self.assertEqual(response.status_code, status, response.text)
            self.assertEqual(self.balance(account), expected)

    def test_reminder_linked_transaction_cannot_be_edited_or_deleted(self):
        account = self.account()
        due = date.today().isoformat()
        reminder = self.post('/reminders', {'name': 'Rent', 'category': 'Rent', 'amount': '10', 'account_id': account, 'due_date': due}).json()['id']
        paid = self.post(f'/reminders/{reminder}/pay', {'due_date': due})
        self.assertEqual(paid.status_code, 200, paid.text)
        txn_id = paid.json()['transaction_id']
        body = {'account_id': account, 'kind': 'expense', 'category': 'Rent', 'amount': '20'}
        self.assertEqual(self.put(f'/transactions/{txn_id}', body).status_code, 409)
        self.assertEqual(self.delete(f'/transactions/{txn_id}').status_code, 409)
        replay = self.post(f'/reminders/{reminder}/pay', {'due_date': due})
        self.assertTrue(replay.json()['already_paid'])
        self.assertEqual(replay.json()['transaction_id'], txn_id)
        self.assertEqual(self.balance(account), 90)
        self.assertEqual(self.db.scalar(select(func.count(ReminderPayment.id))), 1)
        self.assertEqual(self.delete(f'/transactions/{txn_id}', self.other).status_code, 404)

    def test_receipt_linked_transaction_cannot_be_edited_or_deleted(self):
        account = self.account()
        txn, body = self.transaction(account, 'expense', '10')
        self.db.add(AIScan(user_id=self.owner['user']['id'], status='confirmed', transaction_id=txn['id'], details={}))
        self.db.commit()
        self.assertEqual(self.put(f"/transactions/{txn['id']}", body | {'amount': '20'}).status_code, 409)
        self.assertEqual(self.delete(f"/transactions/{txn['id']}").status_code, 409)
        self.assertEqual(self.balance(account), 90)
        self.assertEqual(self.get(f"/transactions/{txn['id']}").status_code, 200)

    def test_unlinked_expense_edit_delete_updates_budget_dashboard_report(self):
        account = self.account()
        self.assertEqual(self.post('/budgets', {'category': 'Food', 'monthly_limit': '50'}).status_code, 201)
        txn, body = self.transaction(account, 'expense', '10')
        response = self.put(f"/transactions/{txn['id']}", body | {'amount': '25'})
        self.assertEqual(response.status_code, 200, response.text)
        dashboard = self.get('/dashboard?include_cash_flow=true').json()
        self.assertEqual((Decimal(dashboard['monthly_expenses']), Decimal(dashboard['cash_flow']['expense']), self.balance(account)), (25, 25, 75))
        self.assertEqual(Decimal(dashboard['budgets'][0]['spent']), 25)
        self.assertEqual(self.delete(f"/transactions/{txn['id']}").status_code, 200)
        dashboard = self.get('/dashboard?include_cash_flow=true').json()
        self.assertEqual((Decimal(dashboard['monthly_expenses']), Decimal(dashboard['cash_flow']['expense']), self.balance(account)), (0, 0, 100))
        self.assertEqual(Decimal(dashboard['budgets'][0]['spent']), 0)

    def test_profile_and_registration_respect_existing_database_name_limit(self):
        response = self.client.post('/auth/register', json=self.payload('long-name') | {'full_name': 'N' * 101})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.put('/settings/profile', {'full_name': 'N' * 101}).status_code, 422)
        self.assertEqual(self.put('/settings/profile', {'full_name': 'N' * 100}).status_code, 200)

    def test_onboarding_rejects_income_names_larger_than_existing_mysql_column(self):
        self.assertEqual(self.post('/onboarding/about-you', {'full_name': 'N' * 101}).status_code, 422)
        self.assertEqual(self.post('/onboarding/about-you', {'full_name': 'Flow Owner'}).status_code, 200)
        response = self.post('/onboarding/income', {'sources': [{'name': 'I' * 101, 'amount': '1000'}]})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.get('/onboarding/status').json()['current_step'], 2)
        self.assertEqual(self.post('/onboarding/income', {'sources': [{'name': 'I' * 100, 'amount': '1000'}]}).status_code, 200)

    def test_main_feature_flow_from_onboarding_through_report(self):
        steps = [
            ('about-you', {'full_name': 'Flow Owner', 'currency': 'LKR'}),
            ('income', {'sources': [{'name': 'Salary', 'amount': '1000'}]}),
            ('accounts', {'accounts': [{'name': 'Cash', 'kind': 'cash', 'opening_balance': '100'}]}),
            ('budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '100'}]}),
            ('goals', {'goals': [{'name': 'Emergency', 'target_amount': '200', 'saved_amount': '0'}]}),
        ]
        for step, body in steps:
            response = self.post('/onboarding/' + step, body)
            self.assertEqual(response.status_code, 200, response.text)
        account = self.get('/accounts').json()['items'][0]['id']
        bank = self.account('0', 'Bank')
        self.transaction(account, 'income', '1000', 'Salary')
        self.transaction(account, 'expense', '40')
        import uuid
        transfer = self.post('/transfers', {'from_account_id': account, 'to_account_id': bank, 'amount': '100', 'client_request_id': str(uuid.uuid4())})
        self.assertEqual(transfer.status_code, 201, transfer.text)
        goal = self.get('/goals').json()[0]['id']
        payload = {'amount': '25', 'request_id': 'flow-contribution', 'account_id': account}
        for _ in range(2):
            self.assertEqual(self.post(f'/goals/{goal}/contribute', payload).status_code, 200)
        due = date.today().isoformat()
        reminder = self.post('/reminders', {'name': 'Rent', 'category': 'Rent', 'amount': '50', 'account_id': account, 'due_date': due}).json()['id']
        for _ in range(2):
            self.assertEqual(self.post(f'/reminders/{reminder}/pay', {'due_date': due}).status_code, 200)
        dashboard = self.get('/dashboard?include_cash_flow=true').json()
        self.assertEqual((self.balance(account), self.balance(bank)), (885, 100))
        self.assertEqual((Decimal(dashboard['monthly_income']), Decimal(dashboard['monthly_expenses'])), (1000, 90))
        self.assertEqual(Decimal(dashboard['total_savings_allocated']), 25)
        self.assertEqual(Decimal(dashboard['safe_to_spend_estimate']), 925)
        self.assertEqual(Decimal(dashboard['cash_flow']['closing_balance']), 1010)
        self.assertEqual(Decimal(dashboard['budgets'][0]['spent']), 40)
        self.assertTrue(self.get('/onboarding/status').json()['onboarding_completed'])


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(CoreFinanceTests(name) for name in CoreFinanceTests.__dict__ if name.startswith('test_'))
