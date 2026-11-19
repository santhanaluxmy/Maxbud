"""Savings accounting against disposable SQLite; never uses genuine MySQL data."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
import unittest

from sqlalchemy import func, select

import test_family
from app.models.finance import Account, AccountTransfer, Goal, GoalContribution, Transaction


class SavingsTransferTests(unittest.TestCase):
    # Reuse the isolated/auth fixture without inheriting unrelated family tests.
    tearDown = test_family.FamilyTests.tearDown
    email = test_family.FamilyTests.email
    payload = test_family.FamilyTests.payload
    register = test_family.FamilyTests.register
    headers = test_family.FamilyTests.headers
    get = test_family.FamilyTests.get

    def setUp(self):
        if test_family.MYSQL:
            raise RuntimeError("Savings tests require isolated SQLite, not MySQL")
        test_family.FamilyTests.setUp(self)

    def post(self, path, payload=None, person=None):
        return self.client.post(path, json=payload, headers=self.headers(person or self.owner))

    def account(self, amount='100', person=None):
        response = self.post('/accounts', {'name': 'Savings source', 'kind': 'bank', 'opening_balance': amount}, person)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def goal(self, saved='20', target='500'):
        response = self.post('/goals', {'name': 'Emergency fund', 'target_amount': target, 'saved_amount': saved})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()['id']

    def balance(self, account):
        return Decimal(self.get(f'/accounts/{account}').json()['current_balance'])

    def fund(self, goal, account, amount='30', key='fund-once'):
        return self.post(f'/goals/{goal}/contribute', {'account_id': account, 'amount': amount, 'request_id': key})

    def history(self):
        response = self.get('/goals/transfers')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def reverse(self, goal, contribution, person=None):
        return self.post(f'/goals/{goal}/contributions/{contribution}/reverse', person=person)

    def test_transfer_keeps_assets_income_expenses_budgets_and_cash_flow_consistent(self):
        account, goal = self.account(), self.goal()
        self.post('/budgets', {'category': 'Food', 'monthly_limit': '40'})
        before = self.get('/dashboard?include_cash_flow=true').json()
        response = self.fund(goal, account)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(Decimal(response.json()['saved_amount']), 50)
        self.assertEqual(Decimal(response.json()['account_backed_amount']), 30)
        self.assertEqual(Decimal(response.json()['legacy_allocated_amount']), 20)
        self.assertEqual(self.balance(account), 70)
        after = self.get('/dashboard?include_cash_flow=true').json()
        for field in ['total_balance', 'monthly_income', 'monthly_expenses', 'monthly_net_cash_flow']:
            self.assertEqual(after[field], before[field], field)
        for field in ['income', 'expense', 'closing_balance']:
            self.assertEqual(after['cash_flow'][field], before['cash_flow'][field], field)
        self.assertEqual(after['budgets'], before['budgets'])
        self.assertEqual(Decimal(after['safe_to_spend_estimate']), Decimal(before['safe_to_spend_estimate']) - 30)
        self.assertEqual(Decimal(self.get('/accounts').json()['total_balance']), 100)
        entries = self.db.scalars(select(Transaction)).all()
        self.assertEqual({entry.kind for entry in entries}, {'transfer_in', 'transfer_out'})
        self.assertEqual(len(entries), 2)
        self.assertEqual(len({entry.transfer_id for entry in entries}), 1)
        row = self.history()[0]
        self.assertEqual((row['source_account_id'], row['goal_id'], row['goal_name']), (account, goal, 'Emergency fund'))
        self.assertEqual(row['txn_date'], date.today().isoformat())
        self.assertEqual(self.get('/transactions').json(), [])
        self.assertEqual(len(self.get('/transactions?kind=transfer_out').json()), 1)
        self.assertEqual(self.get('/goals/transfers', self.other).json(), [])

    def test_replay_and_request_conflicts_never_debit_twice(self):
        account, other_account, goal = self.account(), self.account(), self.goal()
        for _ in range(2):
            self.assertEqual(self.fund(goal, account).status_code, 200)
        for source, amount in [(other_account, '30'), (account, '31')]:
            self.assertEqual(self.fund(goal, source, amount).status_code, 409)
        self.assertEqual(self.balance(account), 70)
        self.assertEqual(self.balance(other_account), 100)
        self.assertEqual(self.db.scalar(select(func.count(AccountTransfer.id))), 1)
        self.assertEqual(self.db.scalar(select(func.count(GoalContribution.id))), 1)

    def test_rejects_overdraft_nonpositive_missing_and_unauthorized_sources(self):
        account, goal = self.account(), self.goal()
        foreign = self.account(person=self.other)
        for amount, status in [('101', 409), ('0', 422), ('-1', 422), ('0.001', 422)]:
            self.assertEqual(self.fund(goal, account, amount).status_code, status)
        self.assertEqual(self.fund(goal, foreign).status_code, 404)
        self.assertEqual(self.fund(goal, 999999).status_code, 404)
        self.assertEqual(self.post(f'/goals/{goal}/contribute', {'amount': '10', 'account_id': account}).status_code, 422)
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(self.history(), [])
        self.assertEqual(Decimal(self.get('/goals').json()[0]['saved_amount']), 20)

    def test_archived_currency_family_and_system_accounts_are_not_sources(self):
        account, goal = self.account(), self.goal()
        row = self.db.get(Account, account)
        row.is_archived = True
        self.db.commit()
        self.assertEqual(self.fund(goal, account).status_code, 409)
        row.is_archived = False
        row.currency = 'USD'
        self.db.commit()
        self.assertEqual(self.fund(goal, account).status_code, 422)
        row.currency = 'LKR'
        row.family_id = self.db.scalar(select(test_family.Family.id).where(test_family.Family.owner_user_id == self.owner['user']['id']))
        self.db.commit()
        self.assertEqual(self.fund(goal, account).status_code, 404)
        row.family_id = None
        self.db.commit()
        self.assertEqual(self.fund(goal, account).status_code, 200)
        reserve = self.db.scalar(select(Account).where(Account.kind == 'goal_savings'))
        self.assertEqual(self.fund(goal, reserve.id, key='cannot-spend-reserve').status_code, 404)
        self.assertEqual(self.client.patch(f'/accounts/{reserve.id}', json={'opening_balance': '999'}, headers=self.headers(self.owner)).status_code, 404)
        self.assertEqual(self.post(f'/accounts/{reserve.id}/archive', {'archived': False}).status_code, 404)
        self.assertEqual(self.post('/transactions', {'account_id': reserve.id, 'kind': 'expense', 'category': 'Food', 'amount': '1'}).status_code, 404)

    def test_reversal_refunds_once_and_preserves_original_and_legacy_allocation(self):
        account, goal = self.account(), self.goal()
        self.assertEqual(self.fund(goal, account).status_code, 200)
        row = self.history()[0]
        self.assertEqual(self.reverse(goal, row['contribution_id'], self.other).status_code, 404)
        self.assertEqual(self.reverse(goal, row['contribution_id']).status_code, 200)
        self.assertEqual(self.reverse(goal, row['contribution_id']).status_code, 409)
        self.assertEqual(self.balance(account), 100)
        saved = self.get('/goals').json()[0]
        self.assertEqual((Decimal(saved['saved_amount']), Decimal(saved['account_backed_amount']), Decimal(saved['legacy_allocated_amount'])), (20, 0, 20))
        self.assertEqual(self.history()[0]['status'], 'reversed')
        self.assertEqual(self.db.scalar(select(func.count(AccountTransfer.id))), 2)
        self.assertEqual(self.db.scalar(select(func.count(Transaction.id))), 4)
        # Retrying the original contribution after its reversal is a replay.
        self.assertEqual(self.fund(goal, account).status_code, 200)
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(Decimal(self.get('/accounts').json()['total_balance']), 100)
        self.assertEqual(self.get('/transactions').json(), [])

    def test_completed_and_archived_goals_refund_to_archived_accounts(self):
        account, goal = self.account(), self.goal(saved='0', target='30')
        self.assertEqual(self.fund(goal, account).json()['status'], 'completed')
        row = self.history()[0]
        self.db.get(Account, account).is_archived = True
        self.db.commit()
        self.assertEqual(self.reverse(goal, row['contribution_id']).json()['status'], 'active')
        self.db.get(Account, account).is_archived = False
        self.db.commit()
        self.assertEqual(self.fund(goal, account, key='second').status_code, 200)
        self.client.patch(f'/goals/{goal}', json={'status': 'archived'}, headers=self.headers(self.owner))
        self.assertEqual(self.reverse(goal, self.history()[0]['contribution_id']).json()['status'], 'archived')
        self.assertEqual(self.balance(account), 100)

    def test_legacy_rows_remain_unlinked_and_cannot_be_reversed_as_transfers(self):
        account, goal = self.account(), self.goal()
        old = GoalContribution(current_goal_id=goal, user_id=self.owner['user']['id'], request_id='legacy', amount=Decimal('20'))
        self.db.add(old)
        self.db.commit()
        self.assertEqual(self.history(), [])
        self.assertEqual(self.reverse(goal, old.id).status_code, 404)
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(self.fund(goal, account, '20', key='legacy').status_code, 409)
        self.assertEqual(self.fund(goal, account).status_code, 200)
        self.db.refresh(old)
        self.assertIsNone(old.reversed_at)
        self.assertEqual(Decimal(self.get('/goals').json()[0]['legacy_allocated_amount']), 20)
        result = self.client.put(f'/goals/{goal}', headers=self.headers(self.owner), json={
            'name': 'Edited', 'target_amount': '500', 'saved_amount': '0'})
        self.assertEqual(result.status_code, 422)

    def test_failure_after_ledger_write_rolls_back_every_part_then_retry_succeeds(self):
        account, goal = self.account(), self.goal()
        from app.services.personal_savings import post_transfer
        def fail_after_write(*args, **kwargs):
            post_transfer(*args, **kwargs)
            raise RuntimeError('isolated failure after posting')
        with patch('app.services.personal_savings.post_transfer', side_effect=fail_after_write):
            with self.assertRaises(RuntimeError):
                self.fund(goal, account)
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(Decimal(self.get('/goals').json()[0]['saved_amount']), 20)
        for model in [AccountTransfer, Transaction, GoalContribution]:
            self.assertEqual(self.db.scalar(select(func.count(model.id))), 0)
        self.assertEqual(self.db.scalar(select(func.count(Account.id)).where(Account.kind == 'goal_savings')), 0)
        self.assertEqual(self.fund(goal, account).status_code, 200)
        contribution = self.history()[0]['contribution_id']
        with patch.object(self.db, 'commit', side_effect=RuntimeError('isolated commit failure')):
            with self.assertRaises(RuntimeError):
                self.reverse(goal, contribution)
        self.assertEqual(self.balance(account), 70)
        self.assertEqual(self.history()[0]['status'], 'completed')
        self.assertEqual(Decimal(self.get('/goals').json()[0]['saved_amount']), 50)
        self.assertEqual(self.db.scalar(select(func.count(AccountTransfer.id))), 1)
        self.assertEqual(self.reverse(goal, contribution).status_code, 200)

    def test_two_goals_share_one_reserve_and_reversals_remain_independent(self):
        account, first, second = self.account(), self.goal(), self.goal()
        self.assertEqual(self.fund(first, account).status_code, 200)
        self.assertEqual(self.fund(second, account, '70', 'second').status_code, 200)
        self.assertEqual(self.balance(account), 0)
        self.assertEqual(self.fund(first, account, '1', 'overdraft').status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count(Account.id)).where(Account.kind == 'goal_savings')), 1)
        self.assertEqual(self.reverse(second, self.history()[0]['contribution_id']).status_code, 200)
        self.assertEqual(self.balance(account), 70)
        amounts = {row['id']: Decimal(row['account_backed_amount']) for row in self.get('/goals').json()}
        self.assertEqual(amounts, {first: Decimal('30'), second: Decimal('0')})

    def test_target_limit_linked_entry_protection_and_source_corrections(self):
        account, goal = self.account(), self.goal(target='40')
        self.assertEqual(self.fund(goal, account).status_code, 422)
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(self.fund(goal, account, '10').status_code, 200)
        transaction = self.db.scalar(select(Transaction).where(Transaction.kind == 'transfer_out'))
        self.assertEqual(self.client.delete(f'/transactions/{transaction.id}', headers=self.headers(self.owner)).status_code, 409)
        self.assertEqual(self.client.put(f'/transactions/{transaction.id}', headers=self.headers(self.owner), json={
            'account_id': account, 'kind': 'expense', 'category': 'Food', 'amount': '1'}).status_code, 409)
        self.assertEqual(self.client.patch(f'/accounts/{account}', json={'opening_balance': '0'}, headers=self.headers(self.owner)).status_code, 422)
        self.assertEqual(self.balance(account), 90)
        result = self.client.put(f'/goals/{goal}', headers=self.headers(self.owner), json={
            'name': 'Renamed goal', 'target_amount': '50', 'saved_amount': '30'})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(self.history()[0]['goal_name'], 'Renamed goal')
