"""Local/test-only manual grant: fresh isolated DB, never the configured MySQL."""
from datetime import timedelta
import json
import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.main import app
from app.database import get_db
from app.core.config import get_settings
from app.models.family import Family, FamilyMembership, Subscription
from app.models.finance import Transaction
from app.models.platform import DemoCheckout, PlatformEvent
from app.models.user import User, now_utc
from app.services.subscriptions import subscription_valid
from scripts.local_family_test import Sandbox, LocalTestError, OWNER_EMAIL, MEMBER_EMAILS, main

PASSWORD = 'LocalTestOnlyPassword1!'


class LocalFamilyAccessTests(unittest.TestCase):
    def test_cli_preview_and_noninteractive_apply_never_grant(self):
        with patch('scripts.local_family_test.ROOT', self.sandbox.root), patch('scripts.local_family_test.load_settings', return_value=self.settings):
            with redirect_stdout(io.StringIO()) as output:
                main(['grant', '--email', OWNER_EMAIL])
            self.assertIn('Preview only', output.getvalue())
            with patch('sys.stdin.isatty', return_value=False), self.assertRaises(SystemExit):
                main(['grant', '--email', OWNER_EMAIL, '--apply'])
        self.assertEqual(self.sandbox.status()['plan'], 'free')

    def setUp(self):
        self.directory = TemporaryDirectory(prefix='maxbud-local-grant-tests-')
        self.addCleanup(self.directory.cleanup)
        self.settings = SimpleNamespace(ENVIRONMENT='test')
        self.sandbox = Sandbox(Path(self.directory.name) / '.local-family-test', self.settings)
        self.sandbox.initialize(PASSWORD)
        self.engine = self.sandbox.engine()
        self.addCleanup(self.engine.dispose)
        def sessions():
            with Session(self.engine, expire_on_commit=False) as db:
                yield db
        app.dependency_overrides[get_db] = sessions
        self.addCleanup(app.dependency_overrides.clear)
        limiter = patch.object(get_settings(), 'RATE_LIMIT_ENABLED', False)
        limiter.start(); self.addCleanup(limiter.stop)
        demo = patch.object(get_settings(), 'DEMO_PAYMENTS_ENABLED', False)
        demo.start(); self.addCleanup(demo.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def login(self, email):
        response = self.client.post('/auth/login', json={'email': email, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def post(self, path, body, who):
        return self.client.post(path, json=body, headers=who)

    def grant(self, hours=24):
        return self.sandbox.change('grant', OWNER_EMAIL, OWNER_EMAIL, PASSWORD, hours)

    def household(self):
        owner = self.login(OWNER_EMAIL)
        result = self.post('/family', {'name': 'Local Test Household'}, owner)
        self.assertEqual(result.status_code, 201, result.text)
        people = []
        for email in MEMBER_EMAILS:
            member = self.login(email)
            invite = self.post('/family/invitations', {'email': email, 'can_view_shared': True, 'can_add_shared': True}, owner)
            self.assertEqual(invite.status_code, 201, invite.text)
            accepted = self.post('/family/invitations/respond', {'token': invite.json()['token'], 'accept': True}, member)
            self.assertEqual(accepted.status_code, 200, accepted.text)
            people.append(member)
        return owner, people

    def test_init_is_new_only_private_synthetic_and_has_no_financial_seed(self):
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count(User.id))), 6)
            self.assertEqual(db.scalar(select(func.count(Transaction.id))), 0)
            self.assertEqual(db.scalar(select(func.count(Family.id))), 0)
            self.assertTrue(all(row.plan == 'free' and row.source == 'local_test_baseline' for row in db.scalars(select(Subscription))))
        self.assertEqual(self.sandbox.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.sandbox.marker.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.sandbox.database.stat().st_mode & 0o777, 0o600)
        self.assertNotEqual(self.sandbox.manifest()['jwt_secret'], get_settings().JWT_SECRET)
        with self.assertRaises(LocalTestError):
            self.sandbox.initialize(PASSWORD)

    def test_explicit_owner_confirmation_password_and_bounded_expiry_required(self):
        for email, confirmation, password, hours in [
            (MEMBER_EMAILS[0], MEMBER_EMAILS[0], PASSWORD, 24),
            (OWNER_EMAIL, 'wrong@example.com', PASSWORD, 24),
            (OWNER_EMAIL, None, None, 24),
            (OWNER_EMAIL, OWNER_EMAIL, 'wrong', 24),
            (OWNER_EMAIL, OWNER_EMAIL, PASSWORD, 0),
            (OWNER_EMAIL, OWNER_EMAIL, PASSWORD, 169),
        ]:
            with self.subTest(email=email, hours=hours):
                with self.assertRaises(LocalTestError):
                    self.sandbox.change('grant', email, confirmation, password, hours)
        self.assertEqual(self.sandbox.status()['plan'], 'free')
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count(PlatformEvent.id))), 0)

    def test_test_access_is_forbidden_in_beta_production_and_without_expiry(self):
        for environment in ['beta', 'production']:
            with self.subTest(environment=environment):
                self.settings.ENVIRONMENT = environment
                with self.assertRaises(LocalTestError):
                    self.grant()
                with self.assertRaises(LocalTestError):
                    self.sandbox.status()
                with self.assertRaises(LocalTestError):
                    self.sandbox.prepare_app()
        self.settings.ENVIRONMENT = 'test'
        self.grant()
        with Session(self.engine) as db:
            sub = db.scalar(select(Subscription).where(Subscription.source == 'test_access'))
            for environment in ['beta', 'production']:
                with patch.object(get_settings(), 'ENVIRONMENT', environment):
                    self.assertFalse(subscription_valid(sub))
            sub.expires_at = None
            self.assertFalse(subscription_valid(sub))

    def test_unmarked_or_symlinked_database_is_never_opened(self):
        marker = json.loads(self.sandbox.marker.read_text())
        self.sandbox.marker.write_text('{}')
        with self.assertRaises(LocalTestError):
            self.sandbox.engine()
        self.sandbox.marker.write_text(json.dumps(marker))
        fake = Sandbox(Path(self.directory.name) / 'unmarked', self.settings)
        with self.assertRaises(LocalTestError):
            fake.status()
        link = Path(self.directory.name) / 'link'
        link.symlink_to(self.sandbox.root, target_is_directory=True)
        with self.assertRaises(LocalTestError):
            Sandbox(link, self.settings).status()

    def test_grant_sponsors_five_with_demo_disabled_and_revoke_preserves_history(self):
        status = self.grant()
        self.assertEqual((status['plan'], status['source']), ('family_pack', 'test_access'))
        self.assertIsNotNone(status['expires_at_utc'])
        owner, members = self.household()
        rights = self.client.get('/subscriptions', headers=owner).json()
        self.assertTrue(rights['test_access'])
        self.assertFalse(rights['catalog']['demo_enabled'])
        for member in members:
            sponsored = self.client.get('/subscriptions', headers=member).json()
            self.assertTrue(sponsored['test_access'])
            self.assertEqual((sponsored['plan'], sponsored['billing_plan']), ('premium_individual', 'free'))
        self.assertEqual(self.client.get('/family', headers=owner).json()['total_active_members'], 6)
        self.assertEqual(self.post('/family/invitations', {'email': 'seventh@example.com', 'can_view_shared': True, 'can_add_shared': True}, owner).status_code, 409)
        wallet = self.post('/family/wallets', {'name': 'Test wallet'}, owner).json()['id']
        income = {'account_id': wallet, 'category': 'Common', 'amount': '1000', 'request_id': 'income'}
        self.assertEqual(self.post('/family/income', income, members[0]).status_code, 201)
        self.assertEqual(self.post('/family/expenses', {'account_id': wallet, 'category': 'Food', 'amount': '200', 'request_id': 'expense'}, members[1]).status_code, 201)
        self.assertEqual(self.post('/subscriptions/checkout', {'plan': 'family_pack', 'billing_cycle': 'monthly', 'request_id': 'cannot-pay'}, owner).status_code, 403)
        before = self.client.get('/dashboard?scope=family', headers=owner).json()
        self.sandbox.change('revoke', OWNER_EMAIL, OWNER_EMAIL, PASSWORD)
        for member in [owner, *members]:
            self.assertEqual(self.post('/family/income', income | {'request_id': 'blocked'}, member).status_code, 403)
            self.assertEqual(self.client.get('/dashboard?scope=family', headers=member).json()['total_balance'], before['total_balance'])
            self.assertEqual(self.post('/accounts', {'name': 'Own private account', 'kind': 'cash'}, member).status_code, 201)
        rights = self.client.get('/subscriptions', headers=members[0]).json()
        self.assertEqual((rights['plan'], rights['limits']['active_goals']), ('free', 3))
        self.assertFalse(rights['test_access'])
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count(Transaction.id))), 2)
            self.assertEqual(db.scalar(select(func.count(FamilyMembership.id))), 6)
            self.assertEqual(db.scalar(select(func.count(DemoCheckout.id))), 0)
            events = db.scalars(select(PlatformEvent).where(PlatformEvent.kind.like('local_test_family_%'))).all()
            self.assertEqual(len(events), 2)
            self.assertTrue(all(row.details['payment'] is False for row in events))

    def test_expiry_locks_shared_writes_without_deleting_household(self):
        self.grant(hours=1)
        owner, members = self.household()
        wallet = self.post('/family/wallets', {'name': 'Wallet'}, owner).json()['id']
        with Session(self.engine) as db:
            db.scalar(select(Subscription).where(Subscription.source == 'test_access')).expires_at = now_utc() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.post('/family/income', {'account_id': wallet, 'category': 'Blocked', 'amount': '1', 'request_id': 'expired'}, members[0]).status_code, 403)
        self.assertFalse(self.client.get('/family', headers=owner).json()['can_edit_shared'])
        self.assertEqual(self.client.get('/family/wallets', headers=members[0]).status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(db.scalar(select(func.count(Family.id))), 1)

    def test_other_subscription_sources_are_not_overwritten(self):
        with Session(self.engine) as db:
            sub = db.scalar(select(Subscription).where(Subscription.user_id == self.sandbox.manifest()['owner_id']))
            sub.plan = 'premium_individual'; sub.source = 'demo'
            db.commit()
        for action in ['grant', 'revoke']:
            with self.assertRaises(LocalTestError):
                self.sandbox.change(action, OWNER_EMAIL, OWNER_EMAIL, PASSWORD)
        self.assertEqual(self.sandbox.status()['source'], 'demo')

    def test_no_public_test_grant_endpoint(self):
        paths = app.openapi()['paths']
        self.assertFalse(any('test-access' in path or 'test_access' in path or 'local-family' in path for path in paths))


if __name__ == '__main__':
    unittest.main()
