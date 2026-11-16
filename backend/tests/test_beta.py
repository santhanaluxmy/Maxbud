"""New contract tests: trials, demo billing, explicit household finance and Groq boundaries."""
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select, func
import test_family
from app.core.config import get_settings
from app.models.family import Family, FamilyMembership, Subscription
from app.models.finance import Category, Transaction
from app.models.platform import DemoCheckout, ExpenseShare, FamilyInvitation, PlatformEvent
from app.models.user import User, now_utc
from app.services.subscriptions import add_months


class BetaTests(test_family.FamilyTests):
    def setUp(self):
        super().setUp()
        setting=patch.object(get_settings(),'DEMO_PAYMENTS_ENABLED',True)
        setting.start();self.addCleanup(setting.stop)
        import tempfile
        directory=tempfile.TemporaryDirectory(prefix='maxbud-beta-receipts-')
        self.addCleanup(directory.cleanup)
        storage=patch.object(get_settings(),'RECEIPT_STORAGE_DIR',directory.name)
        storage.start();self.addCleanup(storage.stop)

    def post(self,path,body=None,person=None):
        return self.client.post(path,json=body,headers=self.headers(person or self.owner))

    def trial(self,name):
        response=self.client.post('/auth/register',json=self.payload(name))
        self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def upgrade(self,person,plan='family_pack',outcome='success',key='checkout'):
        response=self.post('/subscriptions/checkout',{'plan':plan,'billing_cycle':'monthly','request_id':key},person)
        self.assertEqual(response.status_code,201,response.text)
        completed=self.post('/subscriptions/checkout/'+response.json()['id']+'/simulate',{'outcome':outcome},person)
        self.assertEqual(completed.status_code,200,completed.text)
        return response.json(),completed.json()

    def household(self):
        owner=self.trial('sponsor');member=self.trial('invitee')
        self.upgrade(owner)
        response=self.post('/family',{'name':'Test household'},owner)
        self.assertEqual(response.status_code,201,response.text)
        invite=self.post('/family/invitations',{'email':self.email('invitee'),'can_view_shared':True,'can_add_shared':True},owner)
        self.assertEqual(invite.status_code,201,invite.text)
        response=self.post('/family/invitations/respond',{'token':invite.json()['token'],'accept':True},member)
        self.assertEqual(response.status_code,200,response.text)
        return owner,member,invite.json()

    def account(self,person,balance='50000'):
        result=self.post('/accounts',{'name':'Private cash','kind':'cash','opening_balance':balance},person)
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def test_new_registration_trial_calendar_expiry_and_export(self):
        self.assertEqual(add_months(datetime(2026,1,31,12),3),datetime(2026,4,30,12))
        self.assertEqual(add_months(datetime(2024,2,29),3),datetime(2024,5,29))
        person=self.trial('new-trial')
        rights=self.get('/subscriptions',person).json()
        self.assertEqual((rights['plan'],rights['status']),('trial','trialing'))
        self.assertIsNotNone(rights['trial_started_at']);self.assertIsNotNone(rights['trial_ends_at'])
        self.assertEqual(self.get('/family',person).status_code,404)
        self.assertEqual(self.post('/family',{'name':'Forbidden'},person).status_code,403)
        account=self.account(person,'100')
        original_end=rights['trial_ends_at']
        self.client.post('/auth/login',json={'email':self.email('new-trial'),'password':'SecurePassword1!'})
        self.assertEqual(self.get('/subscriptions',person).json()['trial_ends_at'],original_end)
        sub=self.db.scalar(select(Subscription).where(Subscription.user_id==person['user']['id']))
        sub.expires_at=now_utc()-timedelta(seconds=1);sub.trial_ends_at=sub.expires_at;self.db.commit()
        self.assertFalse(self.get('/subscriptions',person).json()['can_edit'])
        self.assertEqual(self.post('/accounts',{'name':'New','kind':'cash'},person).status_code,403)
        self.assertEqual(self.client.patch(f"/accounts/{account['id']}",json={'name':'Changed'},headers=self.headers(person)).status_code,403)
        self.assertEqual(self.get('/accounts',person).status_code,200)
        export=self.get('/settings/export',person)
        self.assertEqual(export.status_code,200,export.text)
        self.assertEqual(export.json()['accounts'][0]['opening_balance'],'100.00')
        self.assertNotIn('password',export.text);self.assertNotIn('image_path',export.text)

    def test_demo_checkout_trust_failures_replays_cancellation_and_renewal(self):
        person=self.trial('demo')
        body={'plan':'premium_individual','billing_cycle':'monthly','request_id':'failed'}
        forged=self.post('/subscriptions/checkout',body|{'expires_at':'2099-01-01','amount':0},person)
        self.assertEqual(forged.status_code,422)
        session,result=self.upgrade(person,'premium_individual','failure','failed')
        self.assertEqual(result['subscription']['plan'],'trial')
        self.assertEqual(self.post('/subscriptions/checkout/'+session['id']+'/simulate',{'outcome':'success'},person).json()['checkout_status'],'failed')
        session,result=self.upgrade(person,'premium_individual','success','paid')
        first_end=result['subscription']['expires_at']
        replay=self.post('/subscriptions/checkout/'+session['id']+'/simulate',{'outcome':'success'},person)
        self.assertEqual(replay.json()['subscription']['expires_at'],first_end)
        self.assertEqual(self.post('/subscriptions/checkout/'+session['id']+'/simulate',{'outcome':'success'},self.other).status_code,404)
        canceled=self.post('/subscriptions/cancel',person=person)
        self.assertTrue(canceled.json()['can_edit']);self.assertTrue(canceled.json()['cancel_at_period_end'])
        _,renewed=self.upgrade(person,'premium_individual','success','renew')
        self.assertGreater(renewed['subscription']['expires_at'],first_end)
        self.assertFalse(renewed['subscription']['cancel_at_period_end'])
        with patch.object(get_settings(),'DEMO_PAYMENTS_ENABLED',False):
            self.assertEqual(self.post('/subscriptions/checkout',body|{'request_id':'disabled'},person).status_code,403)
        with patch.object(get_settings(),'ENVIRONMENT','production'):
            self.assertEqual(self.post('/subscriptions/checkout',body|{'request_id':'prod'},person).status_code,403)

    def test_invitation_security_sponsorship_and_revocation(self):
        owner,member,invite=self.household()
        stored=self.db.get(FamilyInvitation,invite['id'])
        self.assertNotEqual(stored.token_hash,invite['token'])
        self.assertEqual(self.post('/family/invitations/respond',{'token':invite['token'],'accept':True},self.other).status_code,403)
        self.assertEqual(self.post('/family/invitations/respond',{'token':invite['token'],'accept':True},member).status_code,200)
        self.assertEqual(self.get('/subscriptions',member).json()['plan'],'premium_individual')
        self.assertEqual(self.get('/subscriptions',member).json()['billing_plan'],'trial')
        self.assertEqual(self.get('/dashboard?scope=family',member).status_code,200)
        self.assertEqual(self.post('/family/invitations',{'email':'no@example.com','can_view_shared':True,'can_add_shared':True},member).status_code,403)
        self.assertEqual(self.post('/family/members',self.payload('password-member'),owner).status_code,403)
        member_id=member['user']['id']
        changed=self.client.patch(f'/family/members/{member_id}/permissions',json={'can_view_shared':False,'can_add_shared':False},headers=self.headers(owner))
        self.assertEqual(changed.status_code,200)
        self.assertEqual(self.get('/dashboard?scope=family',member).status_code,403)
        self.assertEqual(self.get('/accounts',member).status_code,200)
        self.assertEqual(self.post('/family/leave',person=member).status_code,200)
        self.assertEqual(self.post('/family/invitations/respond',{'token':invite['token'],'accept':True},member).status_code,409)
        self.assertEqual(self.get('/family',member).status_code,404)
        self.assertEqual(self.get('/subscriptions',member).json()['plan'],'trial')

    def test_invite_expiry_duplicate_and_capacity(self):
        owner=self.trial('capacity');self.upgrade(owner)
        self.assertEqual(self.post('/family',{'name':'Seats'},owner).status_code,201)
        first=None
        for index in range(5):
            result=self.post('/family/invitations',{'email':self.email('seat'+str(index)),'can_view_shared':True,'can_add_shared':True},owner)
            self.assertEqual(result.status_code,201,result.text)
            if first is None:first=result.json()
        self.assertEqual(self.post('/family/invitations',{'email':self.email('seat0'),'can_view_shared':True,'can_add_shared':True},owner).status_code,409)
        self.assertEqual(self.get('/family',owner).json()['available_slots'],0)
        self.assertEqual(self.get('/family',owner).json()['reserved_slots'],5)
        self.assertEqual(self.post('/family/invitations',{'email':self.email('extra'),'can_view_shared':True,'can_add_shared':True},owner).status_code,409)
        recipient=self.trial('seat0')
        stored=self.db.get(FamilyInvitation,first['id']);stored.expires_at=now_utc()-timedelta(seconds=1);self.db.commit()
        self.assertEqual(self.post('/family/invitations/respond',{'token':first['token'],'accept':True},recipient).status_code,409)
        self.assertEqual(self.post('/family/invitations',{'email':self.email('extra'),'can_view_shared':True,'can_add_shared':True},owner).status_code,201)

    def test_shared_wallet_funding_expenses_budgets_and_private_isolation(self):
        owner,member,_=self.household()
        own=self.account(owner);other=self.account(member)
        wallet=self.post('/family/wallets',{'name':'Household wallet'},owner).json()
        for person,account,amount,key in [(owner,own,'20000','owner-fund'),(member,other,'30000','member-fund')]:
            body={'account_id':account['id'],'amount':amount,'request_id':key}
            response=self.post(f"/family/wallets/{wallet['id']}/contribute",body,person)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(self.post(f"/family/wallets/{wallet['id']}/contribute",body,person).status_code,200)
        self.assertEqual(Decimal(self.get('/family/wallets',member).json()[0]['balance']),50000)
        self.assertEqual(Decimal(self.get('/accounts',owner).json()['items'][0]['current_balance']),30000)
        self.assertEqual(Decimal(self.get('/accounts',member).json()['items'][0]['current_balance']),20000)
        self.assertEqual(self.get(f"/accounts/{wallet['id']}",owner).status_code,404)
        self.assertEqual(self.get(f"/accounts/{own['id']}",member).status_code,404)
        self.assertEqual(self.post('/budgets',{'category':'Food','monthly_limit':'100'},owner).status_code,201)
        self.assertEqual(self.post('/family/budgets',{'category':'Food','monthly_limit':'10000'},owner).status_code,201)
        body={'account_id':wallet['id'],'category':'Food','amount':'8000','request_id':'groceries'}
        response=self.post('/family/expenses',body,member)
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(self.post('/family/expenses',body,member).status_code,201)
        report=self.get('/dashboard?scope=family',member).json()
        self.assertEqual(Decimal(report['total_balance']),42000)
        self.assertEqual(Decimal(report['monthly_expenses']),8000)
        self.assertEqual(Decimal(report['monthly_income']),0)
        self.assertEqual(Decimal(report['monthly_wallet_funding']),50000)
        self.assertEqual(report['budgets'][0]['used_percent'],80)
        self.assertEqual(self.get('/budgets',owner).json()[0]['spent'],'0.00')
        # A private salary and its note must never appear in a shared report.
        self.post('/transactions',{'account_id':own['id'],'kind':'income','category':'Salary','amount':'150000','description':'PRIVATE SALARY'},owner)
        shared=self.get('/dashboard?scope=family',member)
        self.assertNotIn('PRIVATE SALARY',shared.text)
        self.assertNotIn('150000',shared.text)
        self.assertEqual(self.get('/dashboard',owner).json()['monthly_income'],'150000.00')
        self.assertEqual(self.get('/dashboard',member).json()['monthly_income'],'0.00')
        self.assertEqual(self.get('/family/wallets',self.other).status_code,200)
        # Another legacy owner sees only their own empty household, never this wallet.
        self.assertEqual(self.get('/family/wallets',self.other).json(),[])
        self.assertEqual(self.post(f"/family/wallets/{wallet['id']}/contribute",{'account_id':own['id'],'amount':'1','request_id':'foreign'},self.other).status_code,404)

    def test_equal_split_partial_reimbursement_does_not_duplicate_expense(self):
        owner,member,_=self.household();own=self.account(owner,'20000');paid=self.account(member,'20000')
        body={'account_id':paid['id'],'category':'Electricity','amount':'12000','request_id':'electricity','split_mode':'equal','splits':[{'user_id':owner['user']['id']},{'user_id':member['user']['id']}]}
        response=self.post('/family/expenses',body,member)
        self.assertEqual(response.status_code,201,response.text)
        debts=self.get('/family/reimbursements',owner).json()
        self.assertEqual(len(debts),1);debt=debts[0]
        self.assertEqual((debt['debtor_id'],debt['creditor_id']),(owner['user']['id'],member['user']['id']))
        self.assertEqual(Decimal(debt['remaining']),6000)
        settlement={'account_id':own['id'],'amount':'2000','request_id':'partial'}
        self.assertEqual(self.post(f"/family/reimbursements/{debt['share_id']}/settle",settlement,member).status_code,403)
        first=self.post(f"/family/reimbursements/{debt['share_id']}/settle",settlement,owner)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.post(f"/family/reimbursements/{debt['share_id']}/settle",settlement,owner).json()['id'],first.json()['id'])
        self.assertEqual(Decimal(self.get('/family/reimbursements',owner).json()[0]['remaining']),4000)
        self.assertEqual(Decimal(self.get('/accounts',owner).json()['items'][0]['current_balance']),18000)
        self.assertEqual(Decimal(self.get('/accounts',member).json()['items'][0]['current_balance']),10000)
        self.assertEqual(Decimal(self.get('/dashboard?scope=family',owner).json()['monthly_expenses']),12000)
        self.assertEqual(len(self.get('/family/expenses',owner).json()),1)
        self.assertEqual(self.post(f"/family/reimbursements/{debt['share_id']}/settle",settlement|{'amount':'4001','request_id':'overpay'},owner).status_code,422)

    def test_percentage_and_custom_splits_are_decimal_exact(self):
        owner,member,_=self.household();account=self.account(owner)
        ids=[owner['user']['id'],member['user']['id']]
        for mode,values,key in [('percentage',['60','40'],'percentage'),('custom',['60.01','40.00'],'custom')]:
            body={'account_id':account['id'],'category':'Bills','amount':'100.01','request_id':key,'split_mode':mode,'splits':[{'user_id':uid,'value':value} for uid,value in zip(ids,values)]}
            response=self.post('/family/expenses',body,owner)
            self.assertEqual(response.status_code,201,response.text)
            shares=self.db.scalars(select(ExpenseShare).where(ExpenseShare.transaction_id==response.json()['id'])).all()
            self.assertEqual(sum((row.amount for row in shares),Decimal(0)),Decimal('100.01'))
        invalid=self.post('/family/expenses',{'account_id':account['id'],'category':'Bills','amount':'100','request_id':'bad','split_mode':'percentage','splits':[{'user_id':ids[0],'value':'99'}]},owner)
        self.assertEqual(invalid.status_code,422)

    def test_family_expiry_preserves_records_and_own_paid_member_subscription(self):
        owner,member,_=self.household()
        self.upgrade(member,'premium_individual',key='own-paid')
        own_sub=self.db.scalar(select(Subscription).where(Subscription.user_id==member['user']['id']))
        self.assertEqual(own_sub.plan,'premium_individual')
        goal=self.post('/goals?scope=family',{'name':'Land','target_amount':'1000'},owner).json()
        self.assertEqual(self.post(f"/goals/{goal['id']}/contribute",{'amount':'300','request_id':'own'},owner).status_code,200)
        self.assertEqual(self.post(f"/goals/{goal['id']}/contribute",{'amount':'200','request_id':'member'},member).status_code,200)
        sub=self.db.scalar(select(Subscription).where(Subscription.user_id==owner['user']['id']))
        sub.expires_at=now_utc()-timedelta(seconds=1);self.db.commit()
        self.assertEqual(self.post('/family/wallets',{'name':'Blocked'},owner).status_code,403)
        self.assertEqual(self.post(f"/goals/{goal['id']}/contribute",{'amount':'1','request_id':'expired'},member).status_code,403)
        self.assertEqual(Decimal(self.get('/goals?scope=family',member).json()[0]['saved_amount']),500)
        self.assertEqual(self.get('/subscriptions',member).json()['plan'],'premium_individual')
        self.assertEqual(self.db.get(Subscription,own_sub.id).plan,'premium_individual')

    def test_shared_permission_revocation_covers_goals(self):
        owner,member,_=self.household()
        goal=self.post('/goals?scope=family',{'name':'Permission goal','target_amount':'100'},owner).json()
        changed=self.client.patch(f"/family/members/{member['user']['id']}/permissions",json={'can_view_shared':True,'can_add_shared':False},headers=self.headers(owner))
        self.assertEqual(changed.status_code,200)
        self.assertEqual(self.get('/goals?scope=family',member).status_code,200)
        self.assertEqual(self.post(f"/goals/{goal['id']}/contribute",{'amount':'1','request_id':'denied'},member).status_code,403)
        self.client.patch(f"/family/members/{member['user']['id']}/permissions",json={'can_view_shared':False,'can_add_shared':False},headers=self.headers(owner))
        self.assertEqual(self.get('/goals?scope=family',member).status_code,403)

    def test_shared_bill_payment_month_report_and_retry_conflict(self):
        owner,member,_=self.household();account=self.account(owner)
        wallet=self.post('/family/wallets',{'name':'Bills wallet'},owner).json()
        self.post(f"/family/wallets/{wallet['id']}/contribute",{'account_id':account['id'],'amount':'20000','request_id':'billfund'},owner)
        today=now_utc().date().isoformat()
        bill=self.post('/family/bills',{'name':'Shared rent','category':'Rent','amount':'1000','account_id':wallet['id'],'due_date':today,'recurrence':'monthly'},owner)
        self.assertEqual(bill.status_code,201,bill.text)
        first=self.post(f"/family/bills/{bill.json()['id']}/pay",{'due_date':today},member)
        self.assertEqual(first.status_code,200,first.text)
        retry=self.post(f"/family/bills/{bill.json()['id']}/pay",{'due_date':today},member)
        self.assertEqual(retry.json()['transaction_id'],first.json()['transaction_id'])
        self.assertEqual(Decimal(self.get('/family/wallets',owner).json()[0]['balance']),19000)
        self.assertEqual(Decimal(self.get('/dashboard?scope=family&year=2025&month=1',owner).json()['monthly_expenses']),0)
        self.assertEqual(self.get('/dashboard?scope=family&month=13',owner).status_code,422)
        self.assertEqual(len(self.get('/family/expenses',owner).json()),1)

    def test_yearly_checkout_expiry_and_family_downgrade_keeps_history(self):
        owner,member,_=self.household()
        self.post('/family/wallets',{'name':'Preserved wallet'},owner)
        checkout=self.post('/subscriptions/checkout',{'plan':'premium_individual','billing_cycle':'yearly','request_id':'annual'},owner).json()
        row=self.db.get(DemoCheckout,checkout['id']);row.expires_at=now_utc()-timedelta(seconds=1);self.db.commit()
        self.assertEqual(self.post(f"/subscriptions/checkout/{row.id}/simulate",{'outcome':'success'},owner).status_code,409)
        self.assertEqual(self.get('/subscriptions',owner).json()['plan'],'family_pack')
        checkout=self.post('/subscriptions/checkout',{'plan':'premium_individual','billing_cycle':'yearly','request_id':'annual-valid'},owner).json()
        response=self.post(f"/subscriptions/checkout/{checkout['id']}/simulate",{'outcome':'success'},owner)
        self.assertEqual(response.status_code,200,response.text)
        end=datetime.fromisoformat(response.json()['subscription']['expires_at'])
        self.assertEqual(end.year,now_utc().year+1)
        self.assertEqual(self.post('/family/wallets',{'name':'Blocked'},owner).status_code,403)
        self.assertEqual(self.get('/family/wallets',member).json()[0]['name'],'Preserved wallet')
        self.assertEqual(self.get('/subscriptions',member).json()['plan'],'trial')

    def image(self):
        output=BytesIO();Image.new('RGB',(40,40),'white').save(output,format='PNG');return output.getvalue()

    def test_receipt_missing_total_review_categories_confirmation_and_usage(self):
        person=self.trial('scanner');account=self.account(person,'100')
        self.post('/budgets',{'category':'Food','monthly_limit':'50'},person)
        output='{"merchant":"Tamil Shop","date":"2026-11-15","total":null,"currency":"Rs.","category":"Food","items":[{"name":"Rice","quantity":2,"unit_price":10.25,"amount":20.50}]}'
        with patch('app.routers.ai.complete',return_value=output):
            result=self.client.post('/ai/receipts',headers=self.headers(person),files={'file':('receipt.png',self.image(),'image/png')})
        self.assertEqual(result.status_code,201,result.text);scan=result.json()
        self.assertIsNone(scan['data']['total']);self.assertIsNone(scan['data']['printed_total'])
        self.assertIsNone(scan['data']['currency'])
        self.assertEqual(Decimal(scan['data']['calculated_subtotal']),Decimal('20.50'))
        self.assertEqual(self.get('/transactions',person).json(),[])
        body=scan['data']|{'total':'25.00','currency':'LKR','account_id':account['id']}
        self.assertEqual(self.post(f"/ai/receipts/{scan['id']}/confirm",body|{'category':'Invented'},person).status_code,422)
        confirmed=self.post(f"/ai/receipts/{scan['id']}/confirm",body,person)
        self.assertEqual(confirmed.status_code,200,confirmed.text)
        self.assertEqual(self.post(f"/ai/receipts/{scan['id']}/confirm",body,person).json()['transaction_id'],confirmed.json()['transaction_id'])
        self.assertEqual(len(self.get('/transactions',person).json()),1)
        self.assertEqual(self.get('/budgets',person).json()[0]['spent'],'25.00')
        self.assertEqual(self.get('/accounts',person).json()['items'][0]['current_balance'],'75.00')
        self.assertEqual(self.get('/ai/usage',person).json()['used']['receipt_scans'],1)
        self.assertEqual(self.post(f"/ai/receipts/{scan['id']}/confirm",body,self.other).status_code,404)

    def test_provider_failures_and_authorized_advisor_context(self):
        from fastapi import HTTPException
        person=self.trial('advisor');other=self.trial('private')
        own=self.account(person,'100');secret=self.account(other,'999999')
        self.post('/transactions',{'account_id':secret['id'],'kind':'income','category':'Salary','amount':'888888'},other)
        self.post('/budgets',{'category':'Food','monthly_limit':'50'},person)
        with patch('app.routers.ai.complete',return_value='not JSON'):
            result=self.client.post('/ai/receipts',headers=self.headers(person),files={'file':('receipt.png',self.image(),'image/png')})
        self.assertEqual(result.status_code,502)
        self.assertEqual(self.get('/ai/usage',person).json()['used']['receipt_scans'],0)
        with patch('app.routers.ai.complete',side_effect=HTTPException(503,'Provider limit')):
            self.assertEqual(self.post('/ai/advisor',{'question':'Help','request_id':'failed'},person).status_code,503)
        with patch('app.routers.ai.complete',return_value='Review your recorded budget.') as provider:
            result=self.post('/ai/advisor',{'question':'Can I spend 5000?','request_id':'ok'},person)
            self.assertEqual(result.status_code,200,result.text)
            prompt=provider.call_args.args[0][0]['text']
            self.assertNotIn('888888',prompt);self.assertNotIn('999999',prompt)
            self.assertNotIn('access_token',prompt);self.assertNotIn('password',prompt)
            self.assertIn('100.00',prompt)
        self.assertEqual(self.get('/ai/usage',person).json()['used']['advisor_messages'],1)
        self.assertEqual(self.post('/ai/advisor',{'question':'Different','request_id':'ok'},person).status_code,409)
        self.assertEqual(self.get('/ai/advisor',other).json(),[])
        self.assertEqual(self.db.scalar(select(func.count(PlatformEvent.id)).where(PlatformEvent.user_id==person['user']['id'],PlatformEvent.kind=='ai_failure')),2)

    def test_admin_metadata_security_demo_labels_and_audit(self):
        self.assertEqual(self.get('/admin/overview',self.owner).status_code,403)
        admin=self.db.get(User,self.other['user']['id']);admin.role='admin';self.db.commit()
        person=self.trial('admin-demo');self.upgrade(person,'premium_individual')
        overview=self.get('/admin/overview',self.other)
        self.assertEqual(overview.status_code,200,overview.text)
        self.assertEqual(overview.json()['verified_real_revenue_lkr'],'0.00')
        self.assertEqual(overview.json()['revenue_type'],'SIMULATED / DEMO REVENUE')
        for path in ['/admin/users','/admin/subscriptions','/admin/billing','/admin/ai-usage','/admin/activity','/admin/settings']:
            result=self.get(path,self.other);self.assertEqual(result.status_code,200,result.text)
            self.assertNotIn('password_hash',result.text);self.assertNotIn('GROQ_API_KEY',result.text)
            self.assertEqual(self.get(path,person).status_code,403)
        response=self.client.patch(f"/admin/users/{person['user']['id']}",json={'is_active':False},headers=self.headers(self.other))
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.get('/accounts',person).status_code,401)
        self.assertIn('admin_user_suspended',self.get('/admin/activity',self.other).text)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(BetaTests(name) for name in BetaTests.__dict__ if name.startswith('test_'))
