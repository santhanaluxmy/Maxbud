"""Registration/login contracts using synthetic, disposable database fixtures."""
import unittest
from datetime import timedelta
from sqlalchemy import func, select
import jwt
import test_family
from app.core.config import get_settings
from app.core.security import verify_password
from app.models.user import User, AuthIdentity, now_utc
from app.models.family import Family, Subscription


class AuthFlowTests(test_family.FamilyTests):
    def test_registration_normalizes_email_hashes_password_and_starts_personal_trial(self):
        payload = self.payload('fresh') | {'email': ' FRESH@EXAMPLE.COM ', 'full_name': '  Fresh Person  ', 'role': 'admin'}
        response = self.client.post('/auth/register', json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        user = result['user']
        self.assertEqual((user['email'], user['full_name'], user['role']), ('fresh@example.com', 'Fresh Person', 'user'))
        self.assertFalse(result['onboarding_completed'])
        identity = self.db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == user['id']))
        self.assertNotEqual(identity.password_hash, payload['password'])
        self.assertTrue(verify_password(payload['password'], identity.password_hash))
        self.assertNotIn('password', response.text)
        self.assertIsNone(self.db.scalar(select(Family).where(Family.owner_user_id == user['id'])))
        subscription = self.db.scalar(select(Subscription).where(Subscription.user_id == user['id']))
        self.assertEqual((subscription.plan, subscription.source), ('trial', 'trial'))
        self.assertGreater(subscription.trial_ends_at, now_utc())
        self.assertEqual(self.get('/auth/me', result).json()['id'], user['id'])

    def test_registration_validation_creates_no_partial_accounts(self):
        before = self.db.scalar(select(func.count(User.id)))
        for changes in [
            {'email': 'invalid'}, {'full_name': '  '}, {'full_name': 'N' * 101},
            {'password': 'weak', 'confirm_password': 'weak'},
            {'password': 'OnlyLetters', 'confirm_password': 'OnlyLetters'},
            {'confirm_password': 'DifferentPassword1!'},
        ]:
            with self.subTest(changes=changes):
                response = self.client.post('/auth/register', json=self.payload('invalid') | changes)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.db.scalar(select(func.count(User.id))), before)

    def test_duplicate_email_is_case_insensitive_and_does_not_replace_credentials(self):
        before = self.db.scalar(select(func.count(User.id)))
        response = self.client.post('/auth/register', json=self.payload('owner') | {'email': self.email('owner').upper(), 'password': 'DifferentPassword2!', 'confirm_password': 'DifferentPassword2!'})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.db.scalar(select(func.count(User.id))), before)
        login = self.client.post('/auth/login', json={'email': self.email('owner'), 'password': 'SecurePassword1!'})
        self.assertEqual(login.status_code, 200, login.text)

    def test_wrong_password_and_unknown_user_have_same_response(self):
        results = [self.client.post('/auth/login', json={'email': email, 'password': 'WrongPassword1!'}) for email in [self.email('owner'), self.email('unknown')]]
        self.assertEqual([r.status_code for r in results], [401, 401])
        self.assertEqual(results[0].json(), results[1].json())

    def test_login_returns_current_onboarding_and_role_state(self):
        for completed, role in [(False, 'owner'), (True, 'user'), (True, 'admin')]:
            user = self.db.get(User, self.owner['user']['id'])
            user.onboarding_completed = completed
            user.role = role
            self.db.commit()
            response = self.client.post('/auth/login', json={'email': ' ' + self.email('owner').upper() + ' ', 'password': 'SecurePassword1!'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['onboarding_completed'], completed)
            self.assertEqual(response.json()['user']['role'], role)

    def test_disabled_user_cannot_login_or_use_existing_token(self):
        user = self.db.get(User, self.owner['user']['id'])
        user.is_active = False
        self.db.commit()
        response = self.client.post('/auth/login', json={'email': self.email('owner'), 'password': 'SecurePassword1!'})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.get('/auth/me').status_code, 401)

    def test_protected_profile_rejects_missing_expired_and_tampered_tokens(self):
        self.assertIn(self.client.get('/auth/me').status_code, [401, 403])
        expired = jwt.encode({'sub': str(self.owner['user']['id']), 'exp': now_utc() - timedelta(seconds=1)}, get_settings().JWT_SECRET, algorithm='HS256')
        for token in [expired, 'not-a-token', jwt.encode({'sub': str(self.owner['user']['id']), 'exp': now_utc() + timedelta(minutes=5)}, 'synthetic-other-secret-that-is-long-enough', algorithm='HS256')]:
            self.assertEqual(self.client.get('/auth/me', headers={'Authorization': 'Bearer ' + token}).status_code, 401)

    def test_legacy_bcrypt_identity_can_login_without_changing_its_password(self):
        import bcrypt
        identity = self.db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == self.owner['user']['id'], AuthIdentity.provider == 'password'))
        original_hash = bcrypt.hashpw(b'SecurePassword1!', bcrypt.gensalt(rounds=4)).decode()
        identity.password_hash = original_hash
        self.db.commit()
        for password, expected in [('SecurePassword1!', 200), ('WrongPassword1!', 401)]:
            response = self.client.post('/auth/login', json={'email': self.email('owner'), 'password': password})
            self.assertEqual(response.status_code, expected, response.text)
        self.assertEqual(identity.password_hash, original_hash)

    def test_corrupt_password_hash_returns_authentication_error_instead_of_server_error(self):
        identity = self.db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == self.owner['user']['id'], AuthIdentity.provider == 'password'))
        for value in ['invalid-hash', '$2b$12$invalid']:
            identity.password_hash = value
            self.db.commit()
            response = self.client.post('/auth/login', json={'email': self.email('owner'), 'password': 'SecurePassword1!'})
            self.assertEqual(response.status_code, 401, response.text)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(AuthFlowTests(name) for name in AuthFlowTests.__dict__ if name.startswith('test_'))
