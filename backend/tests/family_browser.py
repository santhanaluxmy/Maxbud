"""Isolated browser check: python tests/family_browser.py (requires system Chrome)."""
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "SecurePassword1!"
API = "http://127.0.0.1:8765"
WEB = "http://127.0.0.1:5174"


def serve():
    from contextlib import asynccontextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database import Base, get_db
    from app.main import app
    from app.routers.auth import register
    from app.schemas.auth import RegisterIn
    import uvicorn

    engine = create_engine(os.environ["FAMILY_BROWSER_DB"], connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def db_session():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    @asynccontextmanager
    async def lifespan(_):
        yield

    app.router.lifespan_context = lifespan
    app.dependency_overrides[get_db] = db_session
    with Session(engine, expire_on_commit=False) as db:
        result = register(RegisterIn(full_name="Browser Owner", email="browser@example.com", password=PASSWORD, confirm_password=PASSWORD), db)
        from sqlalchemy import select
        from app.models.family import Family, FamilyMembership, Subscription
        user = result["user"]
        subscription = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
        subscription.plan = 'free'; subscription.status = 'active'; subscription.source = None
        subscription.trial_started_at = None; subscription.trial_ends_at = None; subscription.expires_at = None
        family = Family(owner_user_id=user.id, name="Browser legacy family")
        db.add(family); db.flush()
        db.add(FamilyMembership(family_id=family.id,user_id=user.id,status='active'))
        user.role = 'admin' if os.environ.get('BROWSER_ADMIN')=='true' else 'owner'
        result["user"].onboarding_completed = True
        db.commit()
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("BROWSER_API_PORT", "8765")), log_level="warning")


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    with tempfile.TemporaryDirectory(prefix="maxbud-family-browser-") as scratch:
        env = os.environ | {"PYTHONPATH": str(ROOT / "backend"), "FRONTEND_ORIGIN": WEB,
                            "FAMILY_BROWSER_DB": f"sqlite:///{scratch}/test.db", "RATE_LIMIT_ENABLED": "false"}
        with open(f"{scratch}/server.log", "w+") as log:
            backend = subprocess.Popen([sys.executable, __file__, "--serve"], cwd=ROOT / "backend", env=env, stdout=log, stderr=log, start_new_session=True)
            frontend = subprocess.Popen(["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5174", "--strictPort"], cwd=ROOT / "frontend", env=env | {"VITE_API_URL": API}, stdout=log, stderr=log, start_new_session=True)
            try:
                with sync_playwright() as pw:
                    request = pw.request.new_context()
                    for address in [f"{API}/openapi.json", WEB]:
                        for attempt in range(240):
                            try:
                                if request.get(address, timeout=1000).ok:
                                    break
                            except Exception:
                                pass
                            time.sleep(.25)
                        else:
                            log.seek(0)
                            raise RuntimeError(log.read())
                    browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True, args=["--no-sandbox"])
                    errors = []
                    context = browser.new_context(viewport={"width": 1440, "height": 1000})
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    auth = request.post(f"{API}/auth/login", data={"email": "browser@example.com", "password": PASSWORD}).json()

                    def session(page, auth):
                        stored = {"token": auth["access_token"], "user": auth["user"], "onboarding_completed": auth["onboarding_completed"]}
                        page.add_init_script(f"sessionStorage.setItem('maxbud_auth', {json.dumps(json.dumps(stored))});")

                    session(page, auth)
                    page.goto(f"{WEB}/dashboard/family")
                    expect(page.get_by_text("No family members yet.", exact=True)).to_be_visible()

                    def add(name, email):
                        page.get_by_role("button", name="Add Member", exact=True).first.click()
                        dialog = page.get_by_role("dialog")
                        dialog.get_by_label("Full Name", exact=True).fill(name)
                        dialog.get_by_label("Email Address", exact=True).fill(email)
                        dialog.get_by_label("Password", exact=True).fill(PASSWORD)
                        dialog.get_by_label("Confirm Password", exact=True).fill(PASSWORD)
                        dialog.get_by_role("button", name="Add Member", exact=True).click()
                        expect(page.get_by_role("cell", name=email, exact=True)).to_be_visible()

                    add("Browser Member", "member@example.com")
                    add("Second Member", "second@example.com")
                    expect(page.get_by_role("button", name="Add Member", exact=True)).to_be_disabled()
                    page.get_by_role("button", name="Remove Browser Member", exact=True).click()
                    expect(page.get_by_role("dialog").get_by_text("Browser Member", exact=True)).to_be_visible()
                    page.get_by_role("dialog").get_by_role("button", name="Remove Member", exact=True).click()
                    expect(page.get_by_role("cell", name="member@example.com", exact=True)).to_have_count(0)
                    page.reload()
                    expect(page.get_by_role("cell", name="second@example.com", exact=True)).to_be_visible()
                    page.get_by_role("button", name="New shared goal", exact=True).click()
                    page.get_by_label("Goal name", exact=True).fill("Buy Land")
                    page.get_by_label("Target amount (LKR)", exact=True).fill("1000")
                    page.get_by_role("button", name="Save shared goal", exact=True).click()
                    expect(page.get_by_role("heading", name="Buy Land", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Contribute to Buy Land", exact=True).click()
                    page.get_by_label("Contribution amount (LKR)", exact=True).fill("300")
                    page.get_by_role("button", name="Record contribution", exact=True).click()
                    expect(page.locator(".family-shared-goal")).to_contain_text("LKR 300")
                    page.goto(f"{WEB}/dashboard")
                    expect(page.get_by_label("Dashboard scope", exact=True)).to_be_visible()
                    page.get_by_label("Dashboard scope", exact=True).select_option("family")
                    expect(page.get_by_text("Family budget overview", exact=True)).to_be_visible()
                    page.get_by_label("Dashboard scope", exact=True).select_option("me")
                    expect(page.get_by_text("Recent Transactions", exact=True)).to_be_visible()
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.goto(f"{WEB}/dashboard/family")
                    expect(page.get_by_role("heading", name="Family Management", exact=True)).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows viewport"
                    # Complete the real onboarding API for the remaining member.
                    member = request.post(f"{API}/auth/login", data={"email": "second@example.com", "password": PASSWORD}).json()
                    headers = {"Authorization": f"Bearer {member['access_token']}"}
                    steps = [("about-you", {"full_name": "Second Member", "currency": "LKR"}),
                             ("income", {"sources": [{"name": "Salary", "amount": "1000", "frequency": "monthly"}]}),
                             ("accounts", {"accounts": [{"name": "Cash", "kind": "cash", "opening_balance": "0"}]}),
                             ("budgets", {"budgets": [{"category": "food", "monthly_limit": "100"}]}),
                             ("goals", {"goals": []})]
                    for path, data in steps:
                        response = request.post(f"{API}/onboarding/{path}", data=data, headers=headers)
                        assert response.ok, response.text()
                    member = request.post(f"{API}/auth/login", data={"email": "second@example.com", "password": PASSWORD}).json()
                    member_page = browser.new_page(viewport={"width": 390, "height": 844})
                    session(member_page, member)
                    member_page.goto(f"{WEB}/dashboard/family")
                    expect(member_page.get_by_text("Your membership", exact=True)).to_be_visible()
                    expect(member_page.get_by_role("button", name="Add Member", exact=True)).to_have_count(0)
                    expect(member_page.get_by_role("cell", name="browser@example.com")).to_have_count(0)
                    expect(member_page.get_by_role("button", name="New shared goal", exact=True)).to_have_count(0)
                    expect(member_page.get_by_role("button", name="Edit Buy Land", exact=True)).to_have_count(0)
                    member_page.get_by_role("button", name="Contribute to Buy Land", exact=True).click()
                    member_page.get_by_label("Contribution amount (LKR)", exact=True).fill("200")
                    member_page.get_by_role("button", name="Record contribution", exact=True).click()
                    expect(member_page.locator(".family-shared-goal")).to_contain_text("LKR 500")
                    page.goto(f"{WEB}/dashboard/family")
                    expect(page.locator(".family-shared-goal")).to_contain_text("LKR 500")
                    expect(page.get_by_text("Contribution history (2)", exact=True)).to_be_visible()
                    member_page.goto(f"{WEB}/dashboard")
                    expect(member_page.get_by_text("Recent Transactions", exact=True)).to_be_visible()
                    expect(member_page.get_by_label("Dashboard scope", exact=True)).to_have_count(0)
                    # Exercise the connected finance forms in the existing dashboard.
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    page.goto(f"{WEB}/dashboard/accounts")
                    page.get_by_role("button", name="Add account", exact=True).click()
                    page.get_by_label("Account name", exact=True).fill("Demo Cash")
                    page.get_by_label("Opening balance (LKR)", exact=True).fill("1000")
                    page.get_by_role("button", name="Create account", exact=True).click()
                    expect(page.get_by_role("heading", name="Demo Cash", exact=True)).to_be_visible()
                    page.reload()
                    expect(page.get_by_role("heading", name="Demo Cash", exact=True)).to_be_visible()
                    page.goto(f"{WEB}/dashboard/goals")
                    page.get_by_role("button", name="New goal", exact=True).click()
                    page.get_by_label("Goal name", exact=True).fill("Demo Savings")
                    page.get_by_label("Target amount (LKR)", exact=True).fill("100")
                    page.get_by_role("button", name="Create goal", exact=True).click()
                    expect(page.get_by_role("heading", name="Demo Savings", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Contribute", exact=True).click()
                    page.get_by_label("Contribution amount (LKR)", exact=True).fill("100")
                    page.get_by_role("button", name="Add contribution", exact=True).click()
                    expect(page.get_by_text("completed", exact=True)).to_be_visible()
                    page.goto(f"{WEB}/dashboard/reminders")
                    page.get_by_role("button", name="New reminder", exact=True).click()
                    page.get_by_label("Name", exact=True).fill("Demo Rent")
                    page.get_by_label("Amount", exact=True).fill("25")
                    page.get_by_label("Account", exact=True).select_option(label="Demo Cash")
                    page.get_by_role("button", name="Save reminder", exact=True).click()
                    expect(page.get_by_role("heading", name="Demo Rent", exact=True)).to_be_visible()
                    with page.expect_response(lambda response: "/reminders/" in response.url and response.url.endswith("/pay")) as payment:
                        page.get_by_role("button", name="Mark paid", exact=True).click()
                    assert payment.value.ok, payment.value.text()
                    # The resulting transaction is visible after navigation and refresh.
                    page.goto(f"{WEB}/dashboard/transactions")
                    expect(page.get_by_text("Demo Rent", exact=True)).to_be_visible()
                    page.goto(f"{WEB}/dashboard/reports")
                    expect(page.get_by_label("Report month", exact=True)).to_be_visible()
                    page.goto(f"{WEB}/dashboard/settings")
                    page.get_by_label("Full name", exact=True).fill("Browser Owner Updated")
                    page.get_by_role("button", name="Save profile", exact=True).click()
                    expect(page.get_by_text("Changes saved.", exact=True)).to_be_visible()
                    for path in ["reminders", "ai-scan", "ai-advisor", "settings", "notifications", "upgrade"]:
                        page.set_viewport_size({"width":390,"height":844})
                        page.goto(f"{WEB}/dashboard/{path}")
                        expect(page.locator("main")).to_be_visible()
                        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), path + " overflows mobile viewport"
                    assert not errors, errors
                    print("PASS: owner add/limit/remove/refresh, scope switching, member privacy, real onboarding, desktop/mobile, account persistence, goal completion, bill payment, reports/settings/AI pages, shared owner/member ledger 300+200=500 and refresh, no page errors")
                    browser.close()
            finally:
                for process in [frontend, backend]:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                for process in [frontend, backend]:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else run()
