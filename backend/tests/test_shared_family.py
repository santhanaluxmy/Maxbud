"""Shared-goal ledger, family privacy and financial integration regressions."""
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select
import test_family
from app.models.finance import Goal, GoalContribution
from app.models.family import Subscription
from app.models.user import User


class SharedFamilyTests(test_family.FamilyTests):
    def post(self, path, body, person=None):
        return self.client.post(path, headers=self.headers(person or self.owner), json=body)

    def goal(self, target='1000'):
        response = self.post('/goals?scope=family', {'name':'Buy Land','target_amount':target})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def contribution(self, goal, amount, key, person=None):
        return self.post(f"/goals/{goal['id']}/contribute", {'amount':amount,'request_id':key}, person)

    def test_full_family_journey_and_history_after_removal(self):
        member = self.login_member()
        steps = [('about-you',{'full_name':'Test Member','currency':'LKR'}),
                 ('income',{'sources':[{'name':'Salary','amount':'1000'}]}),
                 ('accounts',{'accounts':[{'name':'Member Cash','kind':'cash','opening_balance':'1000'}]}),
                 ('budgets',{'budgets':[{'category':'Food','monthly_limit':'100'}]}),
                 ('goals',{'goals':[]})]
        for path, body in steps:
            self.assertEqual(self.post('/onboarding/'+path,body,member).status_code,200)
        owner_account = self.post('/accounts',{'name':'Owner Cash','kind':'cash','opening_balance':'1000'}).json()
        member_account = self.get('/accounts',member).json()['items'][0]
        for person, account, income, expense in [(self.owner,owner_account,'1500','400'),(member,member_account,'1000','200')]:
            for kind, amount in [('income',income),('expense',expense)]:
                response = self.post('/transactions',{'account_id':account['id'],'kind':kind,'amount':amount,'category':'Food'},person)
                self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(self.get('/dashboard').json()['monthly_income'],'1500.00')
        self.assertEqual(self.get('/dashboard',member).json()['monthly_income'],'1000.00')
        report = self.get('/dashboard?scope=family').json()
        self.assertEqual((report['monthly_income'],report['monthly_expenses'],report['monthly_net_cash_flow']),('0.00','0.00','0.00'))
        self.assertEqual(report['recent_transactions'],[])
        self.assertEqual({row['user_id']:row['net_cash_flow'] for row in report['member_summaries']},{self.owner['user']['id']:'0.00',member['user']['id']:'0.00'})
        before = report['total_balance']
        goal = self.goal()
        self.assertEqual(self.contribution(goal,'300','owner-300').status_code,200)
        response = self.contribution(goal,'200','member-200',member)
        self.assertEqual(response.status_code,200,response.text)
        goal = response.json()
        self.assertEqual(Decimal(goal['saved_amount']),500)
        self.assertEqual({entry['user_id']:Decimal(entry['amount']) for entry in goal['contributions']},{self.owner['user']['id']:300,member['user']['id']:200})
        self.assertEqual(len(goal['history']),2)
        self.assertEqual(self.get('/dashboard?scope=family').json()['total_balance'],before)
        self.assertEqual(self.get('/dashboard?scope=family').json()['monthly_income'],'0.00')
        self.assertEqual(self.get('/dashboard').json()['shared_savings_allocated'],'300.00')
        self.assertEqual(self.get('/dashboard',member).json()['shared_savings_allocated'],'200.00')
        self.assertEqual(self.get('/goals').json(),[])
        self.assertEqual(self.get('/goals?scope=family',member).status_code,200)
        self.assertEqual(self.get('/dashboard?scope=family',member).status_code,403)
        self.assertEqual(self.get('/accounts/'+str(owner_account['id']),member).status_code,404)
        self.assertEqual(self.remove(member['user']['id']).status_code,200)
        self.assertEqual(self.get('/goals?scope=family',member).status_code,404)
        self.assertIn(self.contribution(goal,'1','removed',member).status_code,[403,404])
        self.assertEqual(self.get('/accounts',member).status_code,200)
        history = self.get('/goals?scope=family').json()[0]
        self.assertEqual(Decimal(history['saved_amount']),500)
        self.assertFalse(next(entry for entry in history['contributions'] if entry['user_id']==member['user']['id'])['is_active_member'])
        report = self.get('/dashboard?scope=family').json()
        self.assertEqual(report['monthly_income'],'0.00')
        self.assertEqual(Decimal(report['shared_goals'][0]['saved_amount']),500)
        login = self.client.post('/auth/login',json={'email':self.email('member'),'password':'SecurePassword1!'})
        self.assertEqual(login.status_code,200)
        self.assertTrue(login.json()['onboarding_completed'])
        self.assertEqual(self.get('/dashboard',login.json()).json()['monthly_income'],'1000.00')
        self.db.expire_all()
        self.assertEqual(self.db.scalar(select(GoalContribution.amount).where(GoalContribution.user_id==member['user']['id'])),Decimal('200'))

    def test_shared_goal_owner_permissions_and_duplicate_requests(self):
        member = self.login_member()
        goal = self.goal('500')
        self.assertEqual(self.post('/goals?scope=family',{'name':'No','target_amount':'10'},member).status_code,403)
        self.assertEqual(self.contribution(goal,'300','once').status_code,200)
        duplicate = self.contribution(goal,'300','once')
        self.assertEqual(duplicate.status_code,200)
        self.assertEqual(Decimal(duplicate.json()['saved_amount']),300)
        self.assertEqual(self.contribution(goal,'301','once').status_code,409)
        self.assertEqual(self.contribution(goal,'200','member',member).json()['status'],'completed')
        self.assertEqual(self.contribution(goal,'200','member',member).status_code,200)
        self.assertEqual(self.contribution(goal,'1','overflow').status_code,409)
        payload = {'name':'Edited Land','target_amount':'600','saved_amount':'500'}
        self.assertEqual(self.client.put(f"/goals/{goal['id']}",json=payload,headers=self.headers(member)).status_code,403)
        self.assertEqual(self.client.patch(f"/goals/{goal['id']}",json={'status':'archived'},headers=self.headers(member)).status_code,403)
        self.assertEqual(self.contribution(goal,'1','unrelated',self.other).status_code,404)
        self.assertEqual(self.client.put(f"/goals/{goal['id']}",json=payload|{'saved_amount':'0'},headers=self.headers(self.owner)).status_code,422)
        response = self.client.put(f"/goals/{goal['id']}",json=payload,headers=self.headers(self.owner))
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'active')
        self.assertEqual(self.client.patch(f"/goals/{goal['id']}",json={'status':'archived'},headers=self.headers(self.owner)).status_code,200)
        self.assertEqual(self.contribution(goal,'1','archived',member).status_code,409)
        self.assertEqual(self.client.patch(f"/goals/{goal['id']}",json={'status':'active'},headers=self.headers(self.owner)).status_code,200)
        self.assertEqual(len(self.get('/goals?scope=family').json()[0]['history']),2)
        # Contribution authorship comes from the token; an extra user_id cannot impersonate another member.
        response = self.post(f"/goals/{goal['id']}/contribute",{'amount':'10','request_id':'authorship','user_id':self.owner['user']['id']},member)
        self.assertEqual(response.status_code,422,response.text)
        response = self.contribution(goal,'10','authorship',member)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['history'][-1]['user_id'],member['user']['id'])

    def test_inactive_members_keep_seats_and_cannot_contribute(self):
        member = self.login_member()
        self.assertEqual(self.add('second').status_code,201)
        goal = self.goal()
        self.db.get(User,member['user']['id']).is_active=False
        self.db.commit()
        self.assertEqual(self.add('over-limit').status_code,409)
        self.assertEqual(self.contribution(goal,'1','inactive',member).status_code,401)
        members = self.get('/family/members').json()
        self.assertFalse(next(entry for entry in members if entry['id']==member['user']['id'])['is_active'])

    def test_currency_and_subscription_expiry_preserve_history(self):
        member = self.login_member()
        goal = self.goal()
        self.assertEqual(self.contribution(goal,'100','saved',member).status_code,200)
        self.db.get(User,member['user']['id']).currency='USD'
        self.db.commit()
        self.assertEqual(self.contribution(goal,'1','currency',member).status_code,409)
        self.assertEqual(self.get('/dashboard',member).status_code,409)
        self.assertEqual(self.get('/dashboard?scope=family').status_code,200)
        self.db.get(User,member['user']['id']).currency='LKR'
        subscription = self.db.scalar(select(Subscription).where(Subscription.user_id==self.owner['user']['id']))
        subscription.plan='premium'
        subscription.expires_at=datetime.utcnow()-timedelta(days=1)
        self.db.commit()
        self.assertEqual(self.get('/family').json()['plan'],'free')
        self.assertEqual(Decimal(self.get('/goals?scope=family').json()[0]['saved_amount']),100)
        self.assertEqual(self.remove(self.owner['user']['id']).status_code,403)

    def test_household_bills_omit_private_names_and_accounts(self):
        member=self.login_member()
        account=self.post('/accounts',{'name':'Private Account','kind':'cash','opening_balance':'100'},member).json()
        self.post('/reminders',{'name':'Private bill detail','category':'Rent','account_id':account['id'],'amount':'25','due_date':date.today().isoformat()},member)
        report=self.get('/dashboard?scope=family')
        self.assertEqual(report.status_code,200,report.text)
        self.assertNotIn('Private bill detail',report.text)
        self.assertNotIn('Private Account',report.text)
        self.assertEqual(report.json()['upcoming_bills'],[])


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(SharedFamilyTests(name) for name in SharedFamilyTests.__dict__ if name.startswith('test_'))
