"""Subscription contract tests; disposable SQLite and mocked sandbox responses."""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select, func
import test_family
from app.core.config import get_settings
from app.models.access import StripeAccount, StripeEvent
from app.models.ai import AIScan, AIUsage, AdvisorMessage
from app.models.family import Subscription
from app.models.user import now_utc


class StripeSubscriptionTests(unittest.TestCase):
    for _name in ['tearDown', 'close_mysql', 'email', 'payload', 'register', 'headers', 'get']:
        locals()[_name] = getattr(test_family.FamilyTests, _name)

    def setUp(self):
        test_family.FamilyTests.setUp(self)
        import tempfile
        directory = tempfile.TemporaryDirectory(prefix='maxbud-stripe-receipts-')
        self.addCleanup(directory.cleanup)
        settings = patch.multiple(get_settings(), ENVIRONMENT='test', STRIPE_SECRET_KEY='sk_test_fixture',
                                 STRIPE_WEBHOOK_SECRET='whsec_fixture', STRIPE_PRICE_PREMIUM_MONTHLY='price_premium',
                                 STRIPE_PRICE_FAMILY_MONTHLY='price_family', STRIPE_PORTAL_CONFIGURATION='bpc_fixture', RECEIPT_STORAGE_DIR=directory.name)
        settings.start(); self.addCleanup(settings.stop)
        provider = patch('app.services.stripe_test.call', side_effect=self.provider)
        self.provider_mock = provider.start(); self.addCleanup(provider.stop)
        self.person = self.client.post('/auth/register', json=self.payload('subscriber')).json()
        self.state = self.stripe_state()
        self.session = {'id':'cs_test_fixture', 'livemode':False, 'status':'open', 'payment_status':'unpaid',
                        'mode':'subscription', 'customer':'cus_fixture', 'client_reference_id':str(self.person['user']['id']),
                        'subscription':None, 'url':'https://checkout.stripe.com/test-fixture'}

    def post(self, path, data=None, person=None):
        return self.client.post(path, json=data, headers=self.headers(person or self.person))

    def price(self, plan='premium_individual'):
        return {'id':'price_premium' if plan == 'premium_individual' else 'price_family', 'livemode':False,
                'active':True, 'currency':'lkr', 'unit_amount':65000 if plan == 'premium_individual' else 90000,
                'recurring':{'interval':'month','interval_count':1}}

    def stripe_state(self, plan='premium_individual'):
        now = int(time.time())
        return {'id':'sub_fixture', 'livemode':False, 'customer':'cus_fixture', 'status':'active',
                'metadata':{'maxbud_user_id':str(self.person['user']['id'])}, 'cancel_at_period_end':False,
                'items':{'data':[{'quantity':1,'price':self.price(plan),'current_period_start':now,'current_period_end':now+2592000}]},
                'latest_invoice':{'livemode':False,'paid':True,'status':'paid','customer':'cus_fixture',
                                  'parent':{'subscription_details':{'subscription':'sub_fixture'}}}}

    def provider(self, method, path, data=None, key=None):
        if path.startswith('prices/'):
            return self.price('family_pack' if path.endswith('price_family') else 'premium_individual')
        if path == 'customers': return {'id':'cus_fixture','livemode':False}
        if path.startswith('checkout/sessions'): return deepcopy(self.session)
        if path.startswith('subscriptions/'): return deepcopy(self.state)
        if path.startswith('billing_portal/configurations'):
            return {'id':'bpc_fixture','livemode':False,'active':True,'features':{'subscription_update':{'enabled':False}}}
        if path == 'billing_portal/sessions': return {'livemode':False,'url':'https://billing.stripe.com/test-fixture'}
        raise AssertionError('Unexpected Stripe endpoint: ' + path)

    def checkout(self, plan='premium_individual', cycle='monthly'):
        return self.post('/billing/stripe/checkout', {'plan':plan,'billing_cycle':cycle,'request_id':'checkout-fixture'})

    def complete(self):
        self.session.update(status='complete', payment_status='paid', subscription='sub_fixture')

    def event(self, key='evt_fixture', kind='invoice.paid', obj=None, signature=True):
        if obj is None:
            obj = {'customer':'cus_fixture','parent':{'subscription_details':{'subscription':'sub_fixture'}}}
            if kind.startswith('customer.subscription.'): obj = {'customer':'cus_fixture','id':'sub_fixture'}
        raw = json.dumps({'id':key,'livemode':False,'type':kind,'data':{'object':obj}}).encode()
        timestamp = str(int(time.time()))
        signed = hmac.new(b'whsec_fixture',timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest() if signature else 'invalid'
        return self.client.post('/billing/stripe/webhook', content=raw, headers={'Stripe-Signature':f't={timestamp},v1={signed}'})

    def rights(self): return self.get('/subscriptions',self.person).json()

    def test_trial_checkout_monthly_price_and_return_route(self):
        before = self.rights()
        self.assertEqual(before['plan'],'trial')
        result = self.checkout()
        self.assertEqual(result.status_code,201,result.text)
        call = next(c for c in self.provider_mock.call_args_list if c.args[1]=='checkout/sessions')
        self.assertEqual(call.args[2]['line_items[0][price]'],'price_premium')
        self.assertTrue(call.args[2]['success_url'].endswith('/dashboard/payment-success'))
        self.assertEqual(self.rights()['plan'],'trial')
        self.assertEqual(self.rights()['trial_ends_at'],before['trial_ends_at'])
        self.assertEqual(self.checkout().status_code,201)
        self.assertEqual(sum(c.args[1]=='checkout/sessions' for c in self.provider_mock.call_args_list),1)

    def test_verified_payment_limits_and_monthly_usage_survive_login_new_db_session(self):
        user_id = self.person['user']['id']
        self.assertEqual(self.post('/budgets', {'category':'Food','monthly_limit':'1000'}).status_code,201)
        for index in range(5):
            scan = AIScan(user_id=user_id,status='review'); self.db.add(scan); self.db.flush()
            self.db.add(AIUsage(user_id=user_id,scan_id=scan.id))
        for index in range(10):
            self.db.add(AdvisorMessage(user_id=user_id,question='Q',answer='A',request_id=str(index)))
        self.db.commit()
        for index in range(3):
            self.assertEqual(self.post('/goals',{'name':f'Goal {index}','target_amount':'100'}).status_code,201)
        self.assertEqual(self.post('/goals',{'name':'Fourth','target_amount':'100'}).status_code,403)
        self.assertEqual(self.post('/ai/advisor',{'question':'Help','request_id':'blocked'}).status_code,403)
        image = BytesIO(); Image.new('RGB',(10,10),'white').save(image,format='PNG')
        denied = self.client.post('/ai/receipts',headers=self.headers(self.person),files={'file':('receipt.png',image.getvalue(),'image/png')})
        self.assertEqual(denied.status_code,403)
        self.assertEqual(self.checkout().status_code,201)
        self.complete()
        self.assertEqual(self.event().status_code,200)
        rights = self.rights()
        self.assertEqual((rights['plan'],rights['limits']['receipt_scans'],rights['limits']['advisor_messages'],rights['limits']['active_goals']),('premium_individual',100,200,20))
        self.assertFalse(rights['household_allowed'])
        with patch('app.routers.ai.complete',return_value='Budget advice'):
            self.assertEqual(self.post('/ai/advisor',{'question':'Help','request_id':'allowed'}).status_code,200)
        with patch('app.routers.ai.complete',return_value='{"merchant":"Shop","total":100,"currency":"LKR","category":"Food","items":[]}'):
            allowed = self.client.post('/ai/receipts',headers=self.headers(self.person),files={'file':('receipt.png',image.getvalue(),'image/png')})
        self.assertEqual(allowed.status_code,201,allowed.text)
        self.assertEqual(self.post('/goals',{'name':'Fourth','target_amount':'100'}).status_code,201)
        used = self.get('/ai/usage',self.person).json()['used']
        self.assertEqual(used,{'receipt_scans':6,'advisor_messages':11})
        # Close the original ORM identity map and use a distinct DB session.
        from sqlalchemy.orm import Session
        from app.database import get_db
        from app.main import app
        with Session(self.engine,expire_on_commit=False) as fresh:
            app.dependency_overrides[get_db] = lambda:fresh
            login = self.client.post('/auth/login',json={'email':self.email('subscriber'),'password':'SecurePassword1!'}).json()
            self.assertEqual(self.get('/subscriptions',login).json()['plan'],'premium_individual')
            self.assertEqual(self.get('/ai/usage',login).json()['used'],used)
        app.dependency_overrides[get_db] = lambda:self.db
        for index in range(94):
            self.db.add(AIUsage(user_id=user_id,scan_id=allowed.json()['id']))
        for index in range(189):
            self.db.add(AdvisorMessage(user_id=user_id,question='Q',answer='A',request_id='paid-limit-'+str(index)))
        self.db.commit()
        with patch('app.routers.ai.complete') as provider:
            self.assertEqual(self.post('/ai/advisor',{'question':'At limit','request_id':'paid-blocked'}).status_code,403)
            different = BytesIO(); Image.new('RGB',(10,10),'black').save(different,format='PNG')
            blocked = self.client.post('/ai/receipts',headers=self.headers(self.person),files={'file':('different.png',different.getvalue(),'image/png')})
            self.assertEqual(blocked.status_code,403)
            provider.assert_not_called()
        for index in range(16):
            self.assertEqual(self.post('/goals',{'name':f'Paid goal {index}','target_amount':'100'}).status_code,201)
        self.assertEqual(self.post('/goals',{'name':'Twenty-first','target_amount':'100'}).status_code,403)

    def test_family_owner_activation_member_personal_privacy_and_cancellation(self):
        self.state = self.stripe_state('family_pack')
        self.assertEqual(self.checkout('family_pack').status_code,201)
        self.complete(); self.assertEqual(self.event().status_code,200)
        self.assertEqual(self.rights()['plan'],'family_pack')
        self.assertEqual(self.rights()['limits']['family_members'],6)
        self.assertEqual(self.post('/family',{'name':'Paid household'}).status_code,201)
        member = self.post('/auth/register',self.payload('invited')).json()
        invite = self.post('/family/invitations',{'email':self.email('invited'),'can_view_shared':True,'can_add_shared':True}).json()
        self.assertEqual(self.post('/family/invitations/respond',{'token':invite['token'],'accept':True},member).status_code,200)
        shared = self.post('/family/wallets',{'name':'Preserved household wallet'})
        self.assertEqual(shared.status_code,201)
        rights = self.get('/subscriptions',member).json()
        self.assertEqual((rights['plan'],rights['limits']['receipt_scans']),('trial',5))
        self.assertTrue(rights['household_allowed'])
        self.assertEqual(self.post('/billing/stripe/reconcile',person=member).json()['activation'],'pending')
        self.assertEqual(self.get('/subscriptions',self.other).json()['plan'],'free')
        self.state['status']='canceled'
        self.assertEqual(self.event('evt_ended','customer.subscription.deleted').status_code,200)
        self.assertEqual(self.post('/family/wallets',{'name':'Blocked'}).status_code,403)
        self.assertEqual(self.get('/family/wallets',member).json()[0]['name'],'Preserved household wallet')
        self.assertEqual(self.rights()['plan'],'trial')

    def test_reconcile_recovers_without_webhook_and_rejects_redirect_claims(self):
        self.assertEqual(self.checkout().status_code,201)
        self.assertEqual(self.post('/billing/stripe/reconcile?plan=premium_individual&paid=true').json()['activation'],'pending')
        self.assertEqual(self.rights()['plan'],'trial')
        self.complete()
        self.assertEqual(self.post('/billing/stripe/reconcile',person=self.other).json()['activation'],'pending')
        self.assertEqual(self.post('/billing/stripe/reconcile').json()['activation'],'active')
        self.assertEqual(self.rights()['plan'],'premium_individual')
        self.assertEqual(self.db.scalar(select(func.count(StripeEvent.id))),0)
        self.assertEqual(self.event().status_code,200)
        self.assertEqual(self.db.scalar(select(func.count(Subscription.id)).where(Subscription.user_id==self.person['user']['id'])),1)

    def test_invalid_duplicate_out_of_order_and_cross_user_events(self):
        self.checkout(); self.complete()
        self.assertEqual(self.event(signature=False).status_code,400)
        self.assertEqual(self.rights()['plan'],'trial')
        self.assertEqual(self.event().status_code,200)
        self.assertTrue(self.event().json()['duplicate'])
        self.state['status']='canceled'
        self.assertEqual(self.event('evt_delete','customer.subscription.deleted').status_code,200)
        self.assertEqual(self.event('evt_delayed_paid','invoice.paid').status_code,200)
        self.assertEqual(self.rights()['plan'],'trial')
        self.state['status']='active'; self.state['metadata']['maxbud_user_id']=str(self.other['user']['id'])
        self.assertEqual(self.event('evt_wrong_owner').status_code,409)
        self.assertEqual(self.rights()['plan'],'trial')
        self.assertEqual(self.get('/subscriptions',self.other).json()['plan'],'free')

    def test_failed_unpaid_expired_checkout_and_mismatched_customer_cannot_activate(self):
        self.checkout()
        self.assertEqual(self.post('/billing/stripe/reconcile').json()['activation'],'pending')
        self.session['status']='expired'
        self.assertEqual(self.post('/billing/stripe/reconcile').json()['activation'],'canceled')
        self.complete(); self.state['latest_invoice']['paid']=False
        self.assertEqual(self.post('/billing/stripe/reconcile').json()['activation'],'pending')
        self.assertEqual(self.rights()['plan'],'trial')
        self.state['status']='incomplete'
        self.assertEqual(self.event('evt_failed','checkout.session.async_payment_failed',{'customer':'cus_fixture','subscription':'sub_fixture'}).status_code,200)
        self.assertEqual(self.rights()['plan'],'trial')
        self.state['customer']='cus_other'
        self.assertEqual(self.post('/billing/stripe/reconcile').status_code,409)
        self.session['customer']='cus_other'
        self.assertEqual(self.post('/billing/stripe/reconcile').status_code,409)

    def test_renewal_cancel_at_period_end_failure_and_original_trial_expiry(self):
        self.checkout(); self.complete(); self.event()
        trial_end=self.rights()['trial_ends_at']
        self.state['cancel_at_period_end']=True
        self.event('evt_cancel','customer.subscription.updated')
        self.assertEqual(self.rights()['plan'],'premium_individual')
        first=self.rights()['expires_at']
        self.state['items']['data'][0]['current_period_end']+=2592000
        self.event('evt_renew')
        self.assertGreater(self.rights()['expires_at'],first)
        self.state['status']='past_due'
        self.event('evt_due','invoice.payment_failed')
        self.assertEqual(self.rights()['plan'],'trial')
        self.assertEqual(self.rights()['trial_ends_at'],trial_end)
        self.state['status']='active'; self.event('evt_recovered')
        self.assertEqual(self.rights()['plan'],'premium_individual')
        self.state['status']='canceled'; self.event('evt_end','customer.subscription.deleted')
        row=self.db.scalar(select(Subscription).where(Subscription.user_id==self.person['user']['id']))
        row.trial_ends_at=now_utc()-timedelta(days=1); self.db.commit()
        self.assertEqual(self.rights()['plan'],'read_only')
        self.assertEqual(self.post('/goals',{'name':'Blocked','target_amount':'100'}).status_code,403)
        self.assertEqual(self.get('/settings/export',self.person).status_code,200)

    def test_duplicate_purchase_yearly_rejection_and_portal(self):
        self.assertEqual(self.checkout(cycle='yearly').status_code,422)
        self.checkout(); self.complete(); self.event()
        self.assertEqual(self.checkout().status_code,409)
        self.assertEqual(self.checkout('family_pack').status_code,409)
        self.assertEqual(self.post('/billing/stripe/portal').status_code,200)
        self.assertEqual(self.post('/billing/stripe/portal',person=self.other).status_code,409)
        self.assertTrue(self.rights()['billing_portal_available'])

    def test_verified_payment_replaces_temporary_demo_entitlement(self):
        row=self.db.scalar(select(Subscription).where(Subscription.user_id==self.person['user']['id']))
        row.source='demo'; row.plan='family_pack'; row.status='active'; self.db.commit()
        self.checkout(); self.complete()
        self.assertEqual(self.event().status_code,200)
        self.assertEqual((self.rights()['source'],self.rights()['plan']),('stripe_test','premium_individual'))

    def test_missing_subscription_row_is_created_only_after_verified_payment(self):
        row=self.db.scalar(select(Subscription).where(Subscription.user_id==self.person['user']['id']))
        self.db.delete(row); self.db.commit()
        self.checkout(); self.complete()
        self.assertEqual(self.post('/billing/stripe/reconcile').json()['activation'],'active')
        self.assertEqual(self.rights()['plan'],'premium_individual')
