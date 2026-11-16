"""Admin/bootstrap contracts. Only temporary SQLite or the existing rollback fixture."""
from datetime import timedelta
import secrets
import unittest
import jwt
from sqlalchemy import select,func
from app.core.config import get_settings
from app.models.user import User,AuthIdentity,now_utc
from app.models.family import Subscription
from app.models.platform import PlatformEvent,DemoCheckout
from app.models.ai import AIUsage,AdvisorMessage,AIScan
from app.models.finance import Account,Transaction
from scripts.bootstrap_admin import provision,ProvisionError
import test_family


class AdminTests(test_family.FamilyTests):
    def login(self,email,password):
        return self.client.post('/auth/login',json={'email':email,'password':password})

    def admin_account(self):
        email=self.email('operator');password=secrets.token_urlsafe(20)+'Aa1!'
        provision(self.db,email,password,create=True);self.db.commit()
        response=self.login(email,password)
        self.assertEqual(response.status_code,200,response.text)
        return response.json(),password

    def test_secure_creation_login_wrong_password_and_no_public_admin(self):
        person,password=self.admin_account()
        self.assertEqual(person['user']['role'],'admin');self.assertTrue(person['onboarding_completed'])
        self.assertEqual(self.login(self.email('operator'),'incorrect').status_code,401)
        self.assertEqual(self.get('/admin/overview',person).status_code,200)
        public=self.client.post('/auth/register',json=self.payload('public')|{'role':'admin'})
        self.assertEqual(public.status_code,201,public.text)
        self.assertEqual(public.json()['user']['role'],'user')
        self.assertEqual(self.get('/admin/overview',public.json()).status_code,403)
        for candidate in [self.owner,self.other]:
            for path in ['/admin/overview','/admin/users','/admin/subscriptions','/admin/billing','/admin/ai-usage','/admin/activity','/admin/settings']:
                self.assertEqual(self.get(path,candidate).status_code,403)
        self.assertEqual(self.db.scalar(select(func.count(PlatformEvent.id)).where(PlatformEvent.kind=='operator_admin_bootstrap')),1)

    def test_promotion_verifies_password_and_preserves_hashes_and_finances(self):
        user=self.db.get(User,self.owner['user']['id'])
        identity=self.db.scalar(select(AuthIdentity).where(AuthIdentity.user_id==user.id))
        original_hash=identity.password_hash
        with self.assertRaises(ProvisionError):provision(self.db,self.email('owner'),'incorrect')
        self.assertEqual(user.role,'owner')
        with self.assertRaises(ProvisionError):provision(self.db,self.email('owner'),'Something1!',create=True)
        provision(self.db,self.email('owner'),'SecurePassword1!');self.db.commit()
        self.assertEqual(identity.password_hash,original_hash)
        self.assertEqual(user.role,'admin')
        self.assertEqual(self.get('/family',self.owner).json()['role'],'owner')
        self.assertEqual(provision(self.db,self.email('owner'),'SecurePassword1!'),'already_admin')
        with self.assertRaises(ProvisionError):provision(self.db,'invalid-email','NotUsed1!',create=True)
        with self.assertRaises(ProvisionError):provision(self.db,self.email('weak'),'weak',create=True)

    def test_missing_expired_tampered_and_suspended_admin(self):
        person,_=self.admin_account()
        self.assertIn(self.client.get('/admin/overview').status_code,[401,403])
        token=jwt.encode({'sub':str(person['user']['id']),'exp':now_utc()-timedelta(seconds=1)},get_settings().JWT_SECRET,algorithm='HS256')
        self.assertEqual(self.client.get('/admin/overview',headers={'Authorization':'Bearer '+token}).status_code,401)
        self.assertEqual(self.client.get('/admin/overview',headers={'Authorization':'Bearer invalid.token.value'}).status_code,401)
        self.db.get(User,person['user']['id']).is_active=False;self.db.commit()
        self.assertEqual(self.get('/admin/overview',person).status_code,401)

    def test_user_actions_search_filters_cycles_and_private_metadata(self):
        admin,_=self.admin_account();target=self.owner['user']['id']
        sub=self.db.scalar(select(Subscription).where(Subscription.user_id==target))
        sub.plan='premium_individual';sub.source='demo';sub.status='active';sub.billing_cycle='yearly';sub.expires_at=now_utc()+timedelta(days=365)
        account=Account(user_id=target,name='PRIVATE ACCOUNT DATA',kind='cash',currency='LKR',opening_balance=100)
        self.db.add(account);self.db.flush()
        self.db.add(Transaction(user_id=target,account_id=account.id,kind='income',category='Salary',amount=100,description='PRIVATE SALARY DATA',txn_date=now_utc().date()))
        self.db.add(AdvisorMessage(user_id=target,question='PRIVATE CHAT DATA',answer='Private answer',request_id='private'))
        scan=AIScan(user_id=target,status='review',image_path='/PRIVATE/RECEIPT/PATH',details={'merchant':'PRIVATE MERCHANT'})
        self.db.add(scan);self.db.flush();self.db.add(AIUsage(user_id=target,scan_id=scan.id))
        self.db.add(PlatformEvent(user_id=target,kind='ai_failure',details={'feature':'receipt','status_code':502}))
        self.db.commit()
        self.assertTrue(any(row['id']==admin['user']['id'] for row in self.get('/admin/users?plan=free',admin).json()))
        users=self.get('/admin/users?q='+self.email('owner')+'&plan=premium_individual&billing_cycle=yearly',admin).json()
        self.assertEqual(len(users),1);self.assertEqual(users[0]['billing_cycle'],'yearly')
        subs=self.get('/admin/subscriptions?plan=premium_individual&billing_cycle=yearly',admin).json()
        self.assertTrue(any(row['user_id']==target for row in subs))
        self.assertEqual(self.get('/admin/users?billing_cycle=weekly',admin).status_code,422)
        self.assertEqual(self.get('/admin/users?offset=10000',admin).json(),[])
        for active in [False,True]:
            result=self.client.patch(f'/admin/users/{target}',headers=self.headers(admin),json={'is_active':active})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(self.get('/accounts',self.owner).status_code,200 if active else 401)
        self.assertEqual(self.client.patch(f"/admin/users/{admin['user']['id']}",headers=self.headers(admin),json={'is_active':False}).status_code,409)
        self.assertEqual(self.client.patch(f'/admin/subscriptions/{sub.id}',headers=self.headers(admin),json={'status':'suspended'}).status_code,200)
        self.assertEqual(self.client.patch(f'/admin/subscriptions/{sub.id}',headers=self.headers(admin),json={'status':'active'}).status_code,200)
        usage=self.get('/admin/ai-usage',admin).json()
        own=next(row for row in usage if row['user_id']==target)
        self.assertEqual((own['scans'],own['messages'],own['failures']),(1,1,1))
        for path in ['/admin/overview','/admin/users','/admin/subscriptions','/admin/billing','/admin/ai-usage','/admin/activity','/admin/settings']:
            result=self.get(path,admin);self.assertEqual(result.status_code,200,result.text)
            for secret in ['PRIVATE ACCOUNT DATA','PRIVATE SALARY DATA','PRIVATE CHAT DATA','PRIVATE MERCHANT','/PRIVATE/RECEIPT/PATH','password_hash','GROQ_API_KEY','JWT_SECRET']:
                self.assertNotIn(secret,result.text)
        events=self.get('/admin/activity',admin).text
        self.assertIn('admin_user_suspended',events);self.assertIn('admin_user_reactivated',events);self.assertIn('admin_subscription_status',events)

    def test_trial_monthly_yearly_statistics_and_simulated_revenue(self):
        admin,_=self.admin_account()
        for index,(plan,cycle) in enumerate([('trial',None),('premium_individual','monthly'),('premium_individual','yearly'),('family_pack','monthly'),('family_pack','yearly')]):
            auth=self.client.post('/auth/register',json=self.payload('plan'+str(index))).json()
            row=self.db.scalar(select(Subscription).where(Subscription.user_id==auth['user']['id']))
            row.plan=plan;row.billing_cycle=cycle;row.source='trial' if plan=='trial' else 'demo';row.status='trialing' if plan=='trial' else 'active';row.expires_at=now_utc()+timedelta(days=31)
            self.db.commit()
        self.db.add(DemoCheckout(id=secrets.token_hex(16),user_id=admin['user']['id'],plan='family_pack',billing_cycle='monthly',amount=100,currency='LKR',status='succeeded',request_id='demo',expires_at=now_utc()+timedelta(minutes=15)))
        self.db.commit()
        overview=self.get('/admin/overview',admin).json()
        self.assertTrue(all(row['subscriptions']>=1 for row in overview['subscription_breakdown']),overview['subscription_breakdown'])
        self.assertEqual(overview['revenue_type'],'SIMULATED / DEMO REVENUE')
        self.assertEqual(overview['verified_real_revenue_lkr'],'0.00')
        self.assertEqual(float(overview['simulated_revenue_lkr']),100)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AdminTests(name) for name in AdminTests.__dict__ if name.startswith('test_'))
