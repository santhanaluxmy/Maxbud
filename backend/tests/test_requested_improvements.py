"""Isolated SQLite tests. All provider calls are mocked unless explicitly opted in."""
from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch
from sqlalchemy import select, func
import test_family
from app.core.config import get_settings
from app.models.user import User, now_utc
from app.models.family import Subscription, Family, FamilyMembership
from app.models.access import PasswordRecovery, StripeAccount, StripeEvent
from app.models.finance import Transaction
from app.services.subscriptions import add_months, catalog


class ImprovementTests(unittest.TestCase):
    # Reuse only isolated fixture/helpers, not inherited test methods.
    for _name in ['setUp', 'tearDown', 'close_mysql', 'email', 'payload', 'register', 'headers', 'get', 'enable_family_pack']:
        locals()[_name] = getattr(test_family.FamilyTests, _name)

    def post(self, path, data, person=None):
        return self.client.post(path, json=data, headers=self.headers(person or self.owner))

    def test_prices_and_annual_preservation(self):
        with patch.object(get_settings(), 'PLAN_PRICES_JSON', '{"premium_individual":{"monthly":12,"yearly":7200},"family_pack":{"monthly":15,"yearly":9900}}'):
            plans = {p['id']: p for p in catalog()['plans']}
            self.assertEqual(plans['premium_individual']['prices'], {'monthly': '650.00', 'yearly': '7200.00'})
            self.assertEqual(plans['family_pack']['prices'], {'monthly': '900.00', 'yearly': '9900.00'})

    def test_calendar_trial_persists_through_login_and_expires_read_only(self):
        person = self.post('/auth/register', self.payload('fresh')).json()
        row = self.db.scalar(select(Subscription).where(Subscription.user_id == person['user']['id']))
        self.assertEqual(row.trial_ends_at, add_months(row.trial_started_at, 3))
        original = row.trial_started_at
        self.post('/auth/login', {'email': self.email('fresh'), 'password': 'SecurePassword1!'})
        self.assertEqual(row.trial_started_at, original)
        self.assertEqual(self.post('/auth/register', self.payload('fresh')).status_code, 409)
        row.expires_at = now_utc() - timedelta(seconds=1); self.db.commit()
        self.assertEqual(self.post('/accounts', {'name': 'No', 'kind': 'cash'}, person).status_code, 403)
        self.assertEqual(self.get('/accounts', person).status_code, 200)
        self.assertEqual(self.get('/settings/export', person).status_code, 200)

    def recovery(self):
        with patch('app.services.recovery.configured', return_value=True), patch('app.services.recovery.send_code') as email:
            response = self.post('/auth/recovery/request', {'email': self.email('owner')})
            self.assertEqual(response.status_code, 200, response.text)
            code = email.call_args.args[1]
            key = response.json()['challenge_id']
        return key, code

    def test_recovery_complete_single_use_hashing_and_old_session_revocation(self):
        before = self.db.scalar(select(func.count()).select_from(Transaction))
        key, code = self.recovery()
        row = self.db.get(PasswordRecovery, key)
        self.assertNotEqual(row.code_hash, code)
        verified = self.post('/auth/recovery/verify', {'challenge_id': key, 'code': code})
        self.assertEqual(verified.status_code, 200)
        proof = verified.json()['reset_token']
        body = {'challenge_id': key, 'reset_token': proof, 'password': 'ChangedPassword2!', 'confirm_password': 'ChangedPassword2!'}
        self.assertEqual(self.post('/auth/recovery/reset', body).status_code, 200)
        self.assertEqual(self.post('/auth/recovery/reset', body).status_code, 400)
        self.assertEqual(self.post('/auth/recovery/verify', {'challenge_id': key, 'code': code}).status_code, 400)
        self.assertEqual(self.get('/auth/me').status_code, 401)
        self.assertEqual(self.post('/auth/login', {'email': self.email('owner'), 'password': 'SecurePassword1!'}).status_code, 401)
        login = self.post('/auth/login', {'email': self.email('owner'), 'password': 'ChangedPassword2!'})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.get('/auth/me', login.json()).status_code, 200)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(Transaction)), before)

    def test_recovery_attempt_expiry_enumeration_and_missing_provider(self):
        with patch('app.services.recovery.configured', return_value=False):
            self.assertEqual(self.post('/auth/recovery/request', {'email': self.email('owner')}).status_code, 503)
        key, code = self.recovery()
        for _ in range(5):
            self.assertEqual(self.post('/auth/recovery/verify', {'challenge_id': key, 'code': '000000' if code != '000000' else '111111'}).status_code, 400)
        self.assertEqual(self.post('/auth/recovery/verify', {'challenge_id': key, 'code': code}).status_code, 400)
        key, code = self.recovery()
        self.db.get(PasswordRecovery, key).expires_at = now_utc() - timedelta(seconds=1); self.db.commit()
        self.assertEqual(self.post('/auth/recovery/verify', {'challenge_id': key, 'code': code}).status_code, 400)
        with patch('app.services.recovery.configured', return_value=True), patch('app.services.recovery.send_code') as email:
            unknown = self.post('/auth/recovery/request', {'email': 'absent@example.com'})
            self.assertEqual(unknown.status_code, 200)
            self.assertIn('eligible', unknown.json()['message'])
            email.assert_not_called()

    def test_member_expired_personal_trial_still_has_permitted_shared_access(self):
        self.enable_family_pack()
        own_family = self.db.scalar(select(Family).where(Family.owner_user_id == self.owner['user']['id']))
        other_family = self.db.scalar(select(Family).where(Family.owner_user_id == self.other['user']['id']))
        other_family.is_active = False
        self.db.add(FamilyMembership(family_id=own_family.id, user_id=self.other['user']['id'], status='active', can_view_shared=True, can_add_shared=True))
        sub = self.db.scalar(select(Subscription).where(Subscription.user_id == self.other['user']['id']))
        sub.plan = 'trial'; sub.source = 'trial'; sub.expires_at = now_utc() - timedelta(days=1)
        self.db.commit()
        rights = self.get('/subscriptions', self.other).json()
        self.assertEqual(rights['plan'], 'read_only')
        self.assertTrue(rights['household_allowed'])
        self.assertEqual(rights['limits']['advisor_messages'], 0)
        self.assertEqual(self.post('/accounts', {'name': 'Denied', 'kind': 'cash'}, self.other).status_code, 403)
        wallet = self.post('/family/wallets', {'name': 'Shared'}).json()
        self.assertEqual(self.post('/family/income', {'account_id': wallet['id'], 'amount': '100', 'category': 'Common', 'request_id': 'shared-income'}, self.other).status_code, 201)
        goal = self.post('/goals?scope=family', {'name': 'Common goal', 'target_amount': '1000'}).json()
        self.assertEqual(self.post(f"/goals/{goal['id']}/contribute", {'amount': '200', 'request_id': 'shared-goal'}, self.other).status_code, 200)
        bill = self.post('/family/bills', {'name': 'Household bill', 'category': 'Common', 'amount': '10', 'account_id': wallet['id'], 'due_date': now_utc().date().isoformat(), 'recurrence': 'none'})
        self.assertEqual(bill.status_code, 201, bill.text)
        self.assertTrue(any('Household bill' in row['message'] for row in self.get('/notifications', self.other).json()))
        activity = self.get('/family/activity', self.other)
        self.assertEqual(activity.status_code, 200, activity.text)
        self.assertEqual({row['kind'] for row in activity.json()}, {'Shared income', 'Goal allocation'})
        self.assertTrue(all('account_id' not in row for row in activity.json()))

    def stripe_state(self, status='active'):
        now = int(time.time())
        return {'id': 'sub_fixture', 'livemode': False, 'customer': 'cus_fixture', 'status': status,
                'current_period_start': now, 'current_period_end': now + 86400 * 30, 'cancel_at_period_end': False,
                'items': {'data': [{'quantity': 1, 'price': {'id': 'price_premium', 'livemode': False, 'active': True, 'currency': 'lkr', 'unit_amount': 65000, 'recurring': {'interval': 'month', 'interval_count': 1}}}]},
                'latest_invoice': {'livemode': False, 'status': 'paid', 'paid': True, 'customer': 'cus_fixture', 'subscription': 'sub_fixture'}}

    def send_event(self, key='evt_test', kind='invoice.paid'):
        raw = json.dumps({'id': key, 'livemode': False, 'type': kind, 'data': {'object': {'customer': 'cus_fixture', 'subscription': 'sub_fixture'}}}).encode()
        timestamp = str(int(time.time()))
        signed = hmac.new(b'whsec_fixture', timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return self.client.post('/billing/stripe/webhook', content=raw, headers={'Stripe-Signature': f't={timestamp},v1={signed}', 'Content-Type': 'application/json'})

    def test_stripe_verified_retry_renewal_failure_cancel_and_resume(self):
        settings = get_settings()
        with patch.multiple(settings, STRIPE_SECRET_KEY='sk_test_fixture', STRIPE_WEBHOOK_SECRET='whsec_fixture', STRIPE_PRICE_PREMIUM_MONTHLY='price_premium'):
            sub = self.db.scalar(select(Subscription).where(Subscription.user_id == self.owner['user']['id']))
            sub.source = 'trial'; self.db.add(StripeAccount(user_id=self.owner['user']['id'], customer_id='cus_fixture')); self.db.commit()
            state = self.stripe_state()
            with patch('app.services.stripe_test.call', return_value=state) as provider:
                self.assertEqual(self.send_event().status_code, 200)
                first = self.get('/subscriptions').json()['expires_at']
                self.assertTrue(self.send_event().json()['duplicate'])
                self.assertEqual(sum(call.args[1].startswith('subscriptions/') for call in provider.call_args_list), 1)
                self.assertEqual(self.get('/subscriptions').json()['plan'], 'premium_individual')
                state['latest_invoice']['paid'] = False
                state['current_period_end'] += 86400
                self.assertEqual(self.send_event('evt_unpaid_change').status_code, 200)
                self.assertEqual(self.get('/subscriptions').json()['expires_at'], first)
                state['latest_invoice']['paid'] = True
                state['current_period_end'] -= 86400
                state['cancel_at_period_end'] = True
                self.assertEqual(self.send_event('evt_cancel').status_code, 200)
                self.assertTrue(self.get('/subscriptions').json()['can_edit'])
                state['cancel_at_period_end'] = False
                state['current_period_end'] += 86400 * 30
                self.assertEqual(self.send_event('evt_renew').status_code, 200)
                self.assertGreater(self.get('/subscriptions').json()['expires_at'], first)
                state['status'] = 'past_due'
                self.assertEqual(self.send_event('evt_failed', 'invoice.payment_failed').status_code, 200)
                self.assertFalse(self.get('/subscriptions').json()['can_edit'])
                state['status'] = 'active'
                self.assertEqual(self.send_event('evt_recovered').status_code, 200)
                self.assertTrue(self.get('/subscriptions').json()['can_edit'])
            self.assertEqual(self.db.scalar(select(func.count()).select_from(StripeEvent)), 6)

    def test_stripe_rejects_forged_webhook_live_key_and_wrong_amount(self):
        from app.services.stripe_test import validate_price
        from fastapi import HTTPException
        with patch.multiple(get_settings(), STRIPE_SECRET_KEY='sk_test_fixture', STRIPE_WEBHOOK_SECRET='whsec_fixture'):
            self.assertEqual(self.client.post('/billing/stripe/webhook', content=b'{}', headers={'Stripe-Signature': 'invalid'}).status_code, 400)
            price = self.stripe_state()['items']['data'][0]['price']
            price['unit_amount'] = 64900
            with self.assertRaises(HTTPException):
                validate_price(price, 'premium_individual', 'monthly')
        with patch.object(get_settings(), 'STRIPE_SECRET_KEY', 'sk_live_forbidden'):
            self.assertEqual(self.post('/billing/stripe/checkout', {'plan': 'family_pack', 'billing_cycle': 'monthly', 'request_id': 'no-live'}).status_code, 503)

    def test_checkout_never_activates_on_redirect_and_reuses_pending_session(self):
        price = self.stripe_state()['items']['data'][0]['price']
        def provider(method, path, data=None, key=None):
            if path.startswith('prices/'):
                return price
            if path == 'customers':
                return {'id': 'cus_fixture', 'livemode': False}
            return {'id': 'cs_test_fixture', 'livemode': False, 'status': 'open', 'url': 'https://checkout.stripe.com/test-fixture'}
        with patch.multiple(get_settings(), STRIPE_SECRET_KEY='sk_test_fixture', STRIPE_WEBHOOK_SECRET='whsec_fixture', STRIPE_PRICE_PREMIUM_MONTHLY='price_premium'), patch('app.services.stripe_test.call', side_effect=provider) as mock:
            data = {'plan': 'premium_individual', 'billing_cycle': 'monthly', 'request_id': 'checkout'}
            self.assertEqual(self.post('/billing/stripe/checkout', data).status_code, 201)
            self.assertEqual(self.get('/subscriptions').json()['plan'], 'free')
            self.assertEqual(self.post('/billing/stripe/checkout', data).status_code, 201)
            self.assertEqual(sum(call.args[1] == 'checkout/sessions' for call in mock.call_args_list), 1)
