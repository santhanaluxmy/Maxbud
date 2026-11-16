from datetime import date
from test_family import FamilyTests


class FeatureTests(FamilyTests):
    def setUp(self):
        super().setUp()
        import tempfile
        from unittest.mock import patch
        from app.core.config import get_settings
        directory = tempfile.TemporaryDirectory(prefix="maxbud-receipt-test-")
        self.addCleanup(directory.cleanup)
        setting = patch.object(get_settings(), "RECEIPT_STORAGE_DIR", directory.name)
        setting.start()
        self.addCleanup(setting.stop)

    def post(self, path, data, person=None):
        return self.client.post(path, json=data, headers=self.headers(person or self.owner))

    def test_goal_completion_limits_and_isolation(self):
        payload = {"name": "Emergency fund", "target_amount": "100", "saved_amount": "0"}
        ids = []
        for _ in range(3):
            response = self.post('/goals', payload)
            self.assertEqual(response.status_code, 201, response.text)
            ids.append(response.json()['id'])
        self.assertEqual(self.post('/goals', payload).status_code, 403)
        self.assertEqual(self.post(f'/goals/{ids[0]}/contribute', {"amount": "10"}, self.other).status_code, 404)
        self.assertEqual(self.post(f'/goals/{ids[0]}/contribute', {"amount": "100"}).json()['status'], 'completed')
        self.assertEqual(self.post(f'/goals/{ids[0]}/contribute', {"amount": "1"}).status_code, 409)
        self.assertEqual(self.post('/goals', payload).status_code, 201)

    def test_reminder_payment_is_idempotent_and_isolated(self):
        account = self.post('/accounts', {"name": "Cash", "kind": "cash", "opening_balance": "500"})
        self.assertEqual(account.status_code, 201, account.text)
        row = self.post('/reminders', {"name": "Rent", "category": "Rent", "amount": "100", "account_id": account.json()['id'], "due_date": "2026-01-31", "recurrence": "monthly"})
        self.assertEqual(row.status_code, 201, row.text)
        key = row.json()['id']
        body = {"due_date": "2026-01-31"}
        self.assertEqual(self.post(f'/reminders/{key}/pay', body, self.other).status_code, 404)
        first = self.post(f'/reminders/{key}/pay', body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['next_due_date'], '2026-02-28')
        second = self.post(f'/reminders/{key}/pay', body)
        self.assertTrue(second.json()['already_paid'])
        self.assertEqual(first.json()['transaction_id'], second.json()['transaction_id'])
        self.assertEqual(len(self.get('/transactions').json()), 1)
        self.assertEqual(float(self.get('/accounts').json()['items'][0]['current_balance']), 400)

    def test_advisor_provider_failure_does_not_consume_usage(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        payload = {"question": "How can I budget?", "request_id": "test-request"}
        with patch('app.routers.ai.complete', side_effect=HTTPException(502, "Provider unavailable")):
            self.assertEqual(self.post('/ai/advisor', payload).status_code, 502)
        self.assertEqual(self.get('/ai/usage').json()['used']['advisor_messages'], 0)
        with patch('app.routers.ai.complete', return_value="Keep a monthly budget."):
            self.assertEqual(self.post('/ai/advisor', payload).status_code, 200)
            self.assertEqual(self.post('/ai/advisor', payload).status_code, 200)
        self.assertEqual(self.get('/ai/usage').json()['used']['advisor_messages'], 1)
        self.assertEqual(self.get('/ai/advisor', self.other).json(), [])

    def test_receipt_review_confirmation_and_invalid_upload(self):
        from io import BytesIO
        from unittest.mock import patch
        from PIL import Image
        image = BytesIO()
        Image.new('RGB', (40, 40), 'white').save(image, format='PNG')
        data = '{"merchant":"Shop","date":"2026-11-13","total":25,"currency":"LKR","category":"Food","items":[{"name":"Rice","amount":25}]}'
        from app.models.finance import Category
        self.db.add(Category(user_id=self.owner['user']['id'],name='Food',kind='expense',archived=False)); self.db.commit()
        with patch('app.routers.ai.complete', return_value=data):
            scan = self.client.post('/ai/receipts', headers=self.headers(self.owner), files={'file': ('bill.png', image.getvalue(), 'image/png')})
        self.assertEqual(scan.status_code, 201, scan.text)
        self.assertEqual(self.get('/ai/usage').json()['used']['receipt_scans'], 1)
        self.assertEqual(self.get('/transactions').json(), [])
        account = self.post('/accounts', {"name":"Cash", "kind":"cash", "opening_balance":"100"}).json()
        key = scan.json()['id']
        payload = scan.json()['data'] | {'account_id':account['id']}
        self.assertEqual(self.post(f'/ai/receipts/{key}/confirm', payload, self.other).status_code, 404)
        first = self.post(f'/ai/receipts/{key}/confirm', payload)
        self.assertEqual(first.status_code, 200, first.text)
        second = self.post(f'/ai/receipts/{key}/confirm', payload)
        self.assertEqual(first.json()['transaction_id'], second.json()['transaction_id'])
        self.assertEqual(len(self.get('/transactions').json()), 1)
        bad = self.client.post('/ai/receipts', headers=self.headers(self.owner), files={'file': ('bad.png', b'invalid', 'image/png')})
        self.assertEqual(bad.status_code, 422)

    def test_admin_is_separate_from_owner_and_settings(self):
        self.assertEqual(self.get('/admin/overview').status_code, 403)
        response = self.client.put('/settings/profile', headers=self.headers(self.owner), json={'full_name': 'Updated Owner'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get('/auth/me').json()['full_name'], 'Updated Owner')
        from app.models.user import User
        self.db.get(User, self.owner['user']['id']).role = 'admin'
        self.db.commit()
        self.assertEqual(self.get('/admin/overview').status_code, 200)
        self.assertEqual(self.get('/admin/users', self.other).status_code, 403)
        target = self.other['user']['id']
        response = self.client.patch(f'/admin/users/{target}', headers=self.headers(self.owner), json={'is_active':False})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get('/auth/me', self.other).status_code, 401)
        self.assertEqual(self.client.patch(f'/admin/users/{target}', headers=self.headers(self.owner), json={'is_active':True}).status_code, 200)
        self.assertEqual(self.get('/auth/me', self.other).status_code, 200)
        body = {'current_password':'SecurePassword1!', 'new_password':'ChangedPassword2!', 'confirm_password':'ChangedPassword2!'}
        response = self.client.put('/settings/password', json=body, headers=self.headers(self.owner))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.post('/auth/login', json={'email':self.email('owner'), 'password':'SecurePassword1!'}).status_code, 401)
        self.assertEqual(self.client.post('/auth/login', json={'email':self.email('owner'), 'password':'ChangedPassword2!'}).status_code, 200)

    def test_notification_state_is_personal(self):
        account = self.post('/accounts', {'name':'Cash', 'kind':'cash', 'opening_balance':'100'}).json()
        self.post('/reminders', {'name':'Rent', 'category':'Rent', 'amount':'10', 'account_id':account['id'], 'due_date':date.today().isoformat()})
        rows = self.get('/notifications').json()
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]['read'])
        self.assertEqual(self.post('/notifications/read', {'key': rows[0]['key']}).status_code, 200)
        self.assertTrue(self.get('/notifications').json()[0]['read'])
        self.assertEqual(self.get('/notifications', self.other).json(), [])


    def test_transaction_submission_key_prevents_duplicate(self):
        account = self.post('/accounts', {'name':'Cash', 'kind':'cash', 'opening_balance':'100'}).json()
        body = {'account_id':account['id'], 'kind':'expense', 'category':'Food', 'amount':'10', 'txn_date':date.today().isoformat()}
        headers = self.headers(self.owner) | {'Idempotency-Key': 'same-submission'}
        first = self.client.post('/transactions', json=body, headers=headers)
        second = self.client.post('/transactions', json=body, headers=headers)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.assertEqual(self.client.post('/transactions', json=body | {'amount':'20'}, headers=headers).status_code, 409)
        self.assertEqual(len(self.get('/transactions').json()), 1)

    def test_safe_to_spend_reserves_bills_once(self):
        account = self.post('/accounts', {'name':'Cash', 'kind':'cash', 'opening_balance':'1000'}).json()
        self.post('/budgets', {'category':'Food', 'monthly_limit':'100'})
        self.post('/transactions', {'account_id':account['id'], 'kind':'expense', 'category':'Food', 'amount':'20'})
        self.post('/goals', {'name':'Savings', 'target_amount':'100', 'saved_amount':'50'})
        for name, category, amount in [('Food bill','Food','50'), ('Rent','Rent','100')]:
            self.post('/reminders', {'name':name, 'category':category, 'amount':amount, 'account_id':account['id'], 'due_date':date.today().isoformat()})
        summary = self.get('/dashboard').json()
        self.assertEqual(summary['total_balance'], '980.00')
        self.assertEqual(summary['unpaid_bill_reserve'], '100.00')
        self.assertEqual(summary['safe_to_spend_estimate'], '750.00')
        self.assertEqual(self.get('/dashboard?year=2026&month=13').status_code, 422)

    def test_new_user_onboarding_and_persistence(self):
        self.assertEqual(self.post('/onboarding/accounts', {'accounts':[{'name':'Cash','kind':'cash'}]}).status_code, 409)
        steps = [('about-you', {'full_name':'New Owner','currency':'LKR'}),
                 ('income', {'sources':[{'name':'Salary','amount':'1000'}]}),
                 ('accounts', {'accounts':[{'name':'Cash','kind':'cash','opening_balance':'1000'}]}),
                 ('budgets', {'budgets':[{'category':'Food','monthly_limit':'100'}]}),
                 ('goals', {'goals':[{'name':'Emergency','target_amount':'200','saved_amount':'0'}]})]
        for index, (path, body) in enumerate(steps):
            response = self.post('/onboarding/' + path, body)
            self.assertEqual(response.status_code, 200, response.text)
            status = self.get('/onboarding/status').json()
            self.assertEqual(status['current_step'], min(5,index+2))
        login = self.client.post('/auth/login', json={'email':self.email('owner'), 'password':'SecurePassword1!'})
        self.assertTrue(login.json()['onboarding_completed'])
        self.assertEqual(self.get('/dashboard').json()['planned_monthly_income'], '1000.00')
        self.assertEqual(len(self.get('/goals').json()), 1)
        self.assertEqual(self.post('/onboarding/about-you', steps[0][1]).status_code, 409)

    def test_ai_limits_and_premium_test_subscription(self):
        from unittest.mock import patch
        from app.models.family import Subscription
        from sqlalchemy import select
        with patch('app.routers.ai.complete', return_value='Test provider response'):
            for number in range(10):
                response = self.post('/ai/advisor', {'question':'Budget advice', 'request_id':str(number)})
                self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.post('/ai/advisor', {'question':'Budget advice','request_id':'over-limit'}).status_code, 403)
            # An already successful request remains idempotent at the quota boundary.
            self.assertEqual(self.post('/ai/advisor', {'question':'Budget advice','request_id':'0'}).status_code, 200)
            subscription = self.db.scalar(select(Subscription).where(Subscription.user_id == self.owner['user']['id']))
            subscription.plan = 'premium'
            self.db.commit()
            self.assertEqual(self.post('/ai/advisor', {'question':'Budget advice','request_id':'premium-message'}).status_code, 200)
            self.assertEqual(self.get('/ai/usage').json()['limits']['advisor_messages'], 200)



    def test_rate_limit_has_cors_and_retry_header(self):
        from unittest.mock import patch
        from app.core.config import get_settings
        with patch.object(get_settings(), 'RATE_LIMIT_ENABLED', True):
            for _ in range(31):
                response = self.client.post('/auth/login', json={'email':self.email('unknown'),'password':'wrong'}, headers={'Origin':'http://localhost:5173'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['retry-after'], '60')
            self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')

    def test_google_verification_and_verified_email(self):
        from unittest.mock import patch
        from app.core.config import get_settings
        with patch.object(get_settings(), 'GOOGLE_CLIENT_ID', 'test-client'):
            with patch('app.routers.auth.id_token.verify_oauth2_token', side_effect=ValueError('invalid')):
                self.assertEqual(self.post('/auth/google', {'credential':'x'*30}).status_code, 401)
            with patch('app.routers.auth.id_token.verify_oauth2_token', return_value={'email':'google@example.com','email_verified':False,'sub':'google-subject'}):
                self.assertEqual(self.post('/auth/google', {'credential':'x'*30}).status_code, 401)
            email = self.email('google')
            with patch('app.routers.auth.id_token.verify_oauth2_token', return_value={'email':email,'email_verified':True,'sub':email,'name':'Google Test'}):
                response = self.post('/auth/google', {'credential':'x'*30})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['user']['email'], email)
                self.assertEqual(self.get('/auth/me', response.json()).status_code, 200)



def load_tests(loader, tests, pattern):
    import unittest
    return unittest.TestSuite(FeatureTests(name) for name in FeatureTests.__dict__ if name.startswith('test_'))
