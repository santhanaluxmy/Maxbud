"""Family Pack contract: owner plus four, private ledgers, shared income/expenses."""
from datetime import timedelta
from decimal import Decimal
import unittest
from sqlalchemy import func, select
from app.models.family import Family, FamilyMembership, Subscription
from app.models.finance import Account, Transaction
from app.models.user import now_utc
from test_beta import BetaTests


class FamilyPackTests(BetaTests):
    def test_only_family_pack_unlocks_shared_writes_including_legacy_accounts(self):
        sub = self.db.scalar(select(Subscription).where(Subscription.user_id == self.owner['user']['id']))
        for plan in ['free', 'premium', 'trial', 'premium_individual']:
            with self.subTest(plan=plan):
                sub.plan = plan; sub.status = 'active'; sub.source = None if plan in ['free', 'premium'] else 'demo'
                sub.expires_at = now_utc() + timedelta(days=30)
                self.db.commit()
                rights = self.get('/subscriptions').json()
                self.assertFalse(rights['household_allowed'])
                self.assertEqual(rights['limits']['family_members'], 0)
                self.assertFalse(self.get('/family').json()['can_edit_shared'])
                requests = [
                    ('/family', {'name': 'Not allowed'}),
                    ('/family/wallets', {'name': 'Not allowed'}),
                    ('/family/budgets', {'category': 'Food', 'monthly_limit': '10'}),
                    ('/family/income', {'account_id': 1, 'category': 'Rent', 'amount': '10', 'request_id': plan}),
                    ('/family/expenses', {'account_id': 1, 'category': 'Food', 'amount': '1', 'request_id': plan}),
                    ('/goals?scope=family', {'name': 'Not allowed', 'target_amount': '100'}),
                    ('/family/invitations', {'email': 'invite@example.com', 'can_view_shared': True, 'can_add_shared': True}),
                ]
                for path, body in requests:
                    response = self.post(path, body)
                    self.assertEqual(response.status_code, 403, response.text)
                # Personal finance stays available on active personal plans.
                response = self.post('/accounts', {'name': plan + ' private', 'kind': 'cash'})
                self.assertEqual(response.status_code, 201, response.text)

    def test_owner_can_grant_exactly_four_other_people_access(self):
        owner, member, _ = self.household()
        for index in range(3):
            person = self.trial('extra' + str(index))
            invite = self.post('/family/invitations', {'email': person['user']['email'], 'can_view_shared': True, 'can_add_shared': True}, owner)
            self.assertEqual(invite.status_code, 201, invite.text)
            accepted = self.post('/family/invitations/respond', {'token': invite.json()['token'], 'accept': True}, person)
            self.assertEqual(accepted.status_code, 200, accepted.text)
        overview = self.get('/family', owner).json()
        self.assertEqual((overview['total_active_members'], overview['max_members'], overview['available_slots']), (5, 5, 0))
        denied = self.post('/family/invitations', {'email': 'sixth@example.com', 'can_view_shared': True, 'can_add_shared': True}, owner)
        self.assertEqual(denied.status_code, 409, denied.text)
        self.assertTrue(self.get('/subscriptions', member).json()['household_allowed'])
        self.assertEqual(self.get('/subscriptions', member).json()['billing_plan'], 'trial')

    def test_shared_income_expense_budget_and_reports_never_pool_private_money(self):
        owner, member, _ = self.household()
        personal = self.account(owner, '500')
        member_personal = self.account(member, '300')
        self.post('/transactions', {'account_id': personal['id'], 'kind': 'income', 'category': 'Salary', 'amount': '9000', 'description': 'PRIVATE SALARY NOTE'}, owner)
        wallet = self.post('/family/wallets', {'name': 'Household wallet'}, owner).json()['id']
        budget = self.post('/family/budgets', {'category': 'Food', 'monthly_limit': '200'}, owner)
        self.assertEqual(budget.status_code, 201, budget.text)
        payload = {'account_id': wallet, 'category': 'Shared earnings', 'amount': '1000.10', 'description': 'Common rental income', 'request_id': 'income-once'}
        for _ in range(2):
            response = self.post('/family/income', payload, member)
            self.assertEqual(response.status_code, 201, response.text)
        spent = self.post('/family/expenses', {'account_id': wallet, 'category': 'Food', 'amount': '180.05', 'request_id': 'expense-once'}, owner)
        self.assertEqual(spent.status_code, 201, spent.text)
        report = self.get('/dashboard?scope=family', member)
        self.assertEqual(report.status_code, 200, report.text)
        summary = report.json()
        for field, expected in [('monthly_income', '1000.10'), ('monthly_expenses', '180.05'), ('monthly_net_cash_flow', '820.05'), ('total_balance', '820.05')]:
            self.assertEqual(Decimal(summary[field]), Decimal(expected))
        self.assertEqual(Decimal(summary['budgets'][0]['spent']), Decimal('180.05'))
        self.assertEqual(Decimal(summary['six_month_trend'][-1]['income']), Decimal('1000.10'))
        self.assertNotIn('PRIVATE SALARY NOTE', report.text)
        self.assertNotIn('9000', report.text)
        own = self.get('/dashboard', owner).json()
        self.assertEqual(Decimal(own['monthly_income']), 9000)
        self.assertEqual(Decimal(own['monthly_expenses']), 0)
        self.assertEqual(Decimal(self.get('/accounts', owner).json()['items'][0]['current_balance']), 9500)
        self.assertEqual(Decimal(self.get('/accounts', member).json()['items'][0]['current_balance']), 300)
        self.assertEqual(self.get('/transactions', member).json(), [])
        history = self.get('/family/income', member).json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['recorded_by_id'], member['user']['id'])
        self.assertNotIn('account_id', history[0])
        self.assertEqual(self.get('/accounts/' + str(personal['id']), member).status_code, 404)
        self.assertEqual(self.get('/accounts/' + str(member_personal['id']), owner).status_code, 404)

    def test_personal_wallet_funding_is_never_shared_income(self):
        owner, member, _ = self.household()
        account = self.account(owner, '500')
        wallet = self.post('/family/wallets', {'name': 'Wallet'}, owner).json()['id']
        response = self.post(f'/family/wallets/{wallet}/contribute', {'account_id': account['id'], 'amount': '100', 'request_id': 'funding'}, owner)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.post('/family/income', {'account_id': wallet, 'category': 'Common earnings', 'amount': '50', 'request_id': 'income'}, member).status_code, 201)
        self.assertEqual(self.post('/family/expenses', {'account_id': wallet, 'category': 'Food', 'amount': '25', 'request_id': 'spend'}, member).status_code, 201)
        summary = self.get('/dashboard?scope=family', member).json()
        self.assertEqual(tuple(Decimal(summary[k]) for k in ['monthly_income', 'monthly_expenses', 'monthly_wallet_funding', 'monthly_net_cash_flow', 'monthly_wallet_net_movement']), (50, 25, 100, 25, 125))

    def test_income_requires_own_household_wallet_and_safe_retry_details(self):
        owner, member, _ = self.household()
        wallet = self.post('/family/wallets', {'name': 'Wallet'}, owner).json()['id']
        private = self.account(member, '50')
        body = {'account_id': wallet, 'category': 'Common', 'amount': '10', 'request_id': 'same'}
        self.assertEqual(self.post('/family/income', body, member).status_code, 201)
        self.assertEqual(self.post('/family/income', body | {'amount': '11'}, member).status_code, 409)
        self.assertEqual(self.post('/family/income', body | {'account_id': private['id'], 'request_id': 'private'}, member).status_code, 404)
        self.assertEqual(self.post('/family/income', body | {'request_id': 'forged', 'user_id': owner['user']['id']}, member).status_code, 422)
        self.assertEqual(self.post('/family/income', body | {'amount': '-1', 'request_id': 'negative'}, member).status_code, 422)
        archived = self.post(f'/family/wallets/{wallet}/archive', {'archived': True}, owner)
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(self.post('/family/income', body | {'request_id': 'archived'}, member).status_code, 409)
        self.assertEqual(len(self.get('/family/income', member).json()), 1)
        self.assertEqual(self.get('/family/income', self.other).json(), [])

    def test_owner_permissions_apply_to_income_expenses_budgets_and_goals(self):
        owner, member, _ = self.household()
        wallet = self.post('/family/wallets', {'name': 'Wallet'}, owner).json()['id']
        uid = member['user']['id']
        def permissions(view, write):
            response = self.client.patch(f'/family/members/{uid}/permissions', json={'can_view_shared': view, 'can_add_shared': write}, headers=self.headers(owner))
            self.assertEqual(response.status_code, 200, response.text)
        permissions(True, False)
        self.assertEqual(self.get('/family/income', member).status_code, 200)
        self.assertEqual(self.post('/family/income', {'account_id': wallet, 'category': 'Income', 'amount': '10', 'request_id': 'denied'}, member).status_code, 403)
        self.assertEqual(self.post('/family/budgets', {'category': 'Food', 'monthly_limit': '10'}, member).status_code, 403)
        permissions(False, False)
        for path in ['/family/income', '/family/expenses', '/family/wallets', '/goals?scope=family', '/dashboard?scope=family']:
            self.assertEqual(self.get(path, member).status_code, 403, path)
        self.assertEqual(self.get('/accounts', member).status_code, 200)

    def test_expired_or_downgraded_pack_preserves_history_and_personal_accounts(self):
        owner, member, _ = self.household()
        wallet = self.post('/family/wallets', {'name': 'Wallet'}, owner).json()['id']
        payload = {'account_id': wallet, 'category': 'Common', 'amount': '10', 'request_id': 'original'}
        self.assertEqual(self.post('/family/income', payload, member).status_code, 201)
        sub = self.db.scalar(select(Subscription).where(Subscription.user_id == owner['user']['id']))
        for plan, status, expires in [('family_pack', 'active', now_utc() - timedelta(seconds=1)), ('premium_individual', 'active', now_utc() + timedelta(days=30)), ('family_pack', 'suspended', now_utc() + timedelta(days=30))]:
            sub.plan = plan; sub.status = status; sub.expires_at = expires
            self.db.commit()
            self.assertFalse(self.get('/family', owner).json()['can_edit_shared'])
            self.assertEqual(self.post('/family/income', payload | {'request_id': 'blocked-' + plan + status}, member).status_code, 403)
            self.assertEqual(len(self.get('/family/income', member).json()), 1)
            self.assertEqual(self.post('/accounts', {'name': 'Still private', 'kind': 'cash'}, member).status_code, 201)
        self.assertEqual(self.db.scalar(select(func.count(Transaction.id)).where(Transaction.family_id.is_not(None))), 1)

    def test_removed_member_loses_shared_access_but_keeps_personal_account(self):
        owner, member, _ = self.household()
        account = self.account(member, '300')
        response = self.client.delete(f"/family/members/{member['user']['id']}", headers=self.headers(owner))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get('/family/income', member).status_code, 404)
        self.assertEqual(self.get('/accounts/' + str(account['id']), member).status_code, 200)
        self.assertFalse(self.get('/subscriptions', member).json()['household_allowed'])

    def test_closed_household_does_not_sponsor_personal_access(self):
        owner, member, _ = self.household()
        family = self.db.scalar(select(Family).where(Family.owner_user_id == owner['user']['id']))
        family.is_active = False
        self.db.commit()
        rights = self.get('/subscriptions', member).json()
        self.assertIsNone(rights['sponsored_by'])
        self.assertEqual(rights['plan'], 'trial')

    def test_oversized_legacy_household_keeps_history_but_must_reduce_members(self):
        self.enable_family_pack()
        family = self.db.scalar(select(Family).where(Family.owner_user_id == self.owner['user']['id']))
        people = []
        # Simulate historical memberships; current invitation APIs never allow
        # creating this over-capacity state.
        for index in range(5):
            person = self.trial('historical' + str(index))
            people.append(person)
            self.db.add(FamilyMembership(family_id=family.id, user_id=person['user']['id'], status='active', can_view_shared=True, can_add_shared=True))
            self.db.commit()
        response = self.get('/family')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['max_members'], 5)
        self.assertEqual(response.json()['total_active_members'], 6)
        self.assertFalse(response.json()['can_edit_shared'])
        self.assertEqual(self.post('/family/wallets', {'name': 'Blocked'}).status_code, 409)
        self.assertEqual(self.get('/family/income').status_code, 200)
        self.assertEqual(self.remove(people[-1]['user']['id']).status_code, 200)
        self.assertTrue(self.get('/family').json()['can_edit_shared'])
        self.assertEqual(self.post('/family/wallets', {'name': 'Allowed'}).status_code, 201)
        self.assertEqual(self.db.scalar(select(func.count(FamilyMembership.id)).where(FamilyMembership.family_id == family.id)), 6)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(FamilyPackTests(name) for name in FamilyPackTests.__dict__ if name.startswith('test_'))
