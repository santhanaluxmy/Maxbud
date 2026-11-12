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
        result["user"].onboarding_completed = True
        db.commit()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


def run():
    from playwright.sync_api import sync_playwright, expect
    with tempfile.TemporaryDirectory(prefix="maxbud-family-browser-") as scratch:
        env = os.environ | {"PYTHONPATH": str(ROOT / "backend"), "FRONTEND_ORIGIN": WEB,
                            "FAMILY_BROWSER_DB": f"sqlite:///{scratch}/test.db"}
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
                    member_page.goto(f"{WEB}/dashboard")
                    expect(member_page.get_by_text("Recent Transactions", exact=True)).to_be_visible()
                    expect(member_page.get_by_label("Dashboard scope", exact=True)).to_have_count(0)
                    assert not errors, errors
                    print("PASS: owner add/limit/remove/refresh, scope switching, member privacy, real onboarding, desktop/mobile, no page errors")
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
