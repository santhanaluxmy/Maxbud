"""Family API security tests. SQLite default; MySQL runs inside an outer transaction that is always rolled back."""
import os
import uuid
import unittest
from datetime import date, datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database import Base, engine as mysql_engine, get_db
from app.main import app
from app.models.family import Family, FamilyMembership, Subscription
from app.models.finance import Account, Budget, Goal, Transaction
from app.models.user import AuthIdentity, User

MYSQL = os.environ.get("FAMILY_TEST_MYSQL") == "1"


class FamilyTests(unittest.TestCase):
    def setUp(self):
        self.email_suffix = uuid.uuid4().hex[:12] if MYSQL else ""
        if MYSQL:
            self.connection = mysql_engine.connect()
            self.outer = self.connection.begin()
            self.db = Session(self.connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
            self.addCleanup(self.close_mysql)
        else:
            self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
            Base.metadata.create_all(self.engine)
            self.db = Session(self.engine, expire_on_commit=False)
        self.initial_families = len(self.db.scalars(select(Family)).all())
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.owner = self.register("owner")
        self.other = self.register("other")

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        if not MYSQL:
            self.engine.dispose()

    def close_mysql(self):
        self.db.close()
        self.outer.rollback()
        self.connection.close()

    def email(self, name):
        return f"{name}{self.email_suffix}@example.com"

    def payload(self, name):
        return {"full_name": f"Test {name}", "email": self.email(name),
                "password": "SecurePassword1!", "confirm_password": "SecurePassword1!"}

    def register(self, name):
        response = self.client.post("/auth/register", json=self.payload(name))
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def headers(self, person):
        return {"Authorization": f"Bearer {person['access_token']}"}

    def get(self, path, person=None):
        return self.client.get(path, headers=self.headers(person or self.owner))

    def add(self, name, person=None):
        return self.client.post("/family/members", headers=self.headers(person or self.owner), json=self.payload(name))

    def login_member(self, name="member"):
        response = self.add(name)
        self.assertEqual(response.status_code, 201, response.text)
        login = self.client.post("/auth/login", json={"email": self.email(name), "password": "SecurePassword1!"})
        self.assertEqual(login.status_code, 200, login.text)
        return login.json()

    def remove(self, user_id, person=None):
        return self.client.delete(f"/family/members/{user_id}", headers=self.headers(person or self.owner))

    def test_registration_overview_and_refresh(self):
        info = self.get("/family").json()
        self.assertEqual((info["plan"], info["currency"], info["role"], info["max_members"], info["available_slots"]), ("free", "LKR", "owner", 3, 2))
        self.assertEqual(self.owner["user"]["role"], "owner")
        before = self.db.scalar(select(Family.id).where(Family.owner_user_id == self.owner["user"]["id"]))
        for _ in range(2):
            self.client.post("/auth/login", json={"email": self.email("owner"), "password": "SecurePassword1!"})
        self.db.expire_all()
        self.assertEqual(before, self.get("/family").json()["id"])
        self.assertEqual(len(self.db.scalars(select(Family)).all()), self.initial_families + 2)

    def test_member_login_list_and_password_safety(self):
        member = self.login_member()
        self.assertEqual(member["user"]["role"], "member")
        listing = self.get("/family/members").json()
        self.assertEqual(len(listing), 2)
        self.assertNotIn("password", str(listing))
        self.assertEqual(len(self.get("/family/members", member).json()), 1)
        self.assertEqual(self.get("/family", member).json()["role"], "member")
        identity = self.db.scalar(select(AuthIdentity).where(AuthIdentity.user_id == member["user"]["id"]))
        self.assertTrue(identity.password_hash.startswith("$argon2"))
        self.assertFalse(member["onboarding_completed"])

    def test_member_and_cross_family_authorization(self):
        member = self.login_member()
        for path in ["/dashboard?scope=family"]:
            self.assertEqual(self.get(path, member).status_code, 403)
        self.assertEqual(self.add("denied", member).status_code, 403)
        self.assertEqual(self.remove(self.owner["user"]["id"], member).status_code, 403)
        self.assertEqual(self.remove(member["user"]["id"], self.other).status_code, 404)
        self.assertEqual(len(self.get("/family/members", self.other).json()), 1)
        self.assertEqual(self.remove(self.owner["user"]["id"]).status_code, 403)
        self.assertEqual(self.remove(999999).status_code, 404)

    def test_free_limit(self):
        self.assertEqual(self.add("one").status_code, 201)
        self.assertEqual(self.add("two").status_code, 201)
        self.assertEqual(self.add("three").status_code, 409)
        self.assertEqual(self.get("/family").json()["available_slots"], 0)

    def test_premium_limit_and_expiration(self):
        subscription = self.db.scalar(select(Subscription).where(Subscription.user_id == self.owner["user"]["id"]))
        subscription.plan = "premium"
        self.db.commit()
        for i in range(6):
            self.assertEqual(self.add(f"premium{i}").status_code, 201)
        self.assertEqual(self.add("overflow").status_code, 409)
        self.assertEqual(self.get("/family").json()["max_members"], 7)
        subscription.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        self.db.commit()
        self.assertEqual(self.get("/family").json()["plan"], "free")

    def test_invalid_and_duplicate_inputs(self):
        self.assertEqual(self.add("owner").status_code, 409)
        self.assertEqual(self.add("other").status_code, 409)
        for changes in [{"full_name": "  "}, {"full_name": "x" * 101}, {"email": "bad"},
                        {"password": "weak", "confirm_password": "weak"}, {"confirm_password": "wrong"}]:
            response = self.client.post("/family/members", headers=self.headers(self.owner), json=self.payload("invalid") | changes)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(len(self.get("/family/members").json()), 1)

    def financial_data(self, person, income, expense):
        uid = person["user"]["id"]
        account = Account(user_id=uid, name="Personal", kind="cash", opening_balance=100, currency="LKR")
        self.db.add(account)
        self.db.flush()
        for kind, amount in [("income", income), ("expense", expense)]:
            self.db.add(Transaction(user_id=uid, account_id=account.id, kind=kind, category="food", amount=amount, txn_date=date.today(), description="Private"))
        self.db.add(Budget(user_id=uid, category="food", monthly_limit=100))
        self.db.add(Goal(user_id=uid, name="Private goal", target_amount=1000, saved_amount=50))
        self.db.commit()
        return account.id

    def test_dashboard_totals_budgets_transfer_and_isolation(self):
        member = self.login_member()
        self.financial_data(self.owner, 500, 20)
        self.financial_data(member, 200, 30)
        self.financial_data(self.other, 9000, 5000)
        # Actual transfer API generates the same ledger entries the dashboard must ignore.
        aid = self.db.scalar(select(Account.id).where(Account.user_id == self.owner["user"]["id"]))
        another = Account(user_id=self.owner["user"]["id"], name="Destination", kind="cash", opening_balance=0, currency="LKR")
        self.db.add(another)
        self.db.commit()
        from app.models.finance import AccountTransfer
        transfer = AccountTransfer(user_id=self.owner["user"]["id"], from_account_id=aid, to_account_id=another.id, amount=10, currency="LKR", txn_date=date.today())
        self.db.add(transfer)
        self.db.flush()
        for kind in ["income", "expense"]:
            self.db.add(Transaction(user_id=self.owner["user"]["id"], account_id=aid, kind=kind, category="food", amount=10, txn_date=date.today(), transfer_id=transfer.id))
        self.db.commit()
        family = self.get("/dashboard?scope=family").json()
        self.assertEqual((family["monthly_income"], family["monthly_expenses"], family["total_balance"]), ("700.00", "50.00", "850.00"))
        self.assertEqual((family["budgets"][0]["limit"], family["budgets"][0]["spent"], family["remaining_budget"]), ("200.00", "50.00", "150.00"))
        self.assertEqual(family["recent_transactions"], [])
        self.assertEqual(family["goals"], [])
        self.assertEqual(family["six_month_trend"][-1]["income"], "700.00")
        self.assertEqual(self.get("/dashboard?scope=me", member).json()["monthly_income"], "200.00")
        self.assertEqual(self.get("/dashboard").json()["monthly_income"], "500.00")
        self.assertEqual(self.get("/dashboard?scope=bad").status_code, 422)
        self.assertEqual(self.get("/accounts", member).json()["items"][0]["id"], self.db.scalar(select(Account.id).where(Account.user_id == member["user"]["id"])))
        self.assertEqual(self.get("/budgets", member).json()[0]["spent"], "30.00")

    def test_removal_preserves_data_and_revokes_existing_token(self):
        member = self.login_member()
        account_id = self.financial_data(member, 200, 30)
        uid = member["user"]["id"]
        self.assertEqual(self.remove(uid).status_code, 200)
        self.db.expire_all()
        self.assertEqual(self.get("/family", member).status_code, 404)
        self.assertEqual(self.get("/family/members", member).status_code, 404)
        self.assertEqual(self.get("/dashboard?scope=family", member).status_code, 403)
        self.assertEqual(self.get("/dashboard?scope=me", member).json()["monthly_income"], "200.00")
        self.assertIsNotNone(self.db.get(Account, account_id))
        self.assertEqual(len(self.db.scalars(select(Transaction).where(Transaction.user_id == uid)).all()), 2)
        self.assertIsNotNone(self.db.scalar(select(Budget).where(Budget.user_id == uid)))
        self.assertIsNotNone(self.db.scalar(select(Goal).where(Goal.user_id == uid)))
        self.assertEqual(self.get("/dashboard?scope=family").json()["monthly_income"], "0.00")
        self.assertEqual(self.get("/family").json()["available_slots"], 2)
        self.assertEqual(self.remove(uid).status_code, 404)

    def test_expired_and_inactive_auth(self):
        expired = jwt.encode({"sub": str(self.owner["user"]["id"]), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, get_settings().JWT_SECRET, algorithm="HS256")
        self.assertEqual(self.client.get("/family", headers={"Authorization": f"Bearer {expired}"}).status_code, 401)
        user = self.db.get(User, self.owner["user"]["id"])
        user.is_active = False
        self.db.commit()
        self.assertEqual(self.get("/family").status_code, 401)

    def test_legacy_user_not_changed_during_login(self):
        from app.core.security import hash_password
        from app.routers.auth import insert_user
        legacy = insert_user(self.db, "Legacy", self.email("legacy"), hash_password("SecurePassword1!"))
        self.db.add(AuthIdentity(user_id=legacy.id, provider="password", password_hash=hash_password("SecurePassword1!")))
        self.db.commit()
        login = self.client.post("/auth/login", json={"email": legacy.email, "password": "SecurePassword1!"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.get("/family", login.json()).status_code, 404)
        self.assertEqual(legacy.role, "user")


if __name__ == "__main__":
    unittest.main()
