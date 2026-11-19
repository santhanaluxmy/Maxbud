"""Family-only navigation and five-person capacity checks with temporary SQLite.
Run: FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/family_capacity_browser.py
Requires installed Playwright and /usr/bin/google-chrome.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=15000)
    with tempfile.TemporaryDirectory(prefix='maxbud-family-browser-') as scratch:
        directory = Path(scratch)
        output = directory / 'dist'
        artifacts = Path('/tmp/maxbud-family-review')
        artifacts.mkdir(exist_ok=True)
        os.environ.update({
            'ENVIRONMENT': 'test', 'FAMILY_TEST_MYSQL': '0', 'FAMILY_PACK_MEMBER_LIMIT': '6', 'RATE_LIMIT_ENABLED': 'false', 'JWT_SECRET': secrets.token_urlsafe(48),
            'DB_USER': 'isolated_unused', 'DB_PASSWORD': 'unused', 'SMTP_HOST': '',
            'SMTP_USERNAME': '', 'SMTP_PASSWORD': '', 'SMTP_FROM': '',
            'STRIPE_SECRET_KEY': '', 'STRIPE_WEBHOOK_SECRET': '', 'GROQ_API_KEY': '', 'OPENAI_API_KEY': '',
            'DEMO_PAYMENTS_ENABLED': 'false', 'RECEIPT_STORAGE_DIR': str(directory / 'receipts'),
        })
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine, event, select
        from sqlalchemy.orm import Session
        from app.main import app
        from app.database import Base, get_db
        from app.models.family import Subscription
        from app.models.user import now_utc
        from datetime import timedelta
        engine = create_engine('sqlite:///' + str(directory / 'isolated.db'), connect_args={'check_same_thread': False})
        @event.listens_for(engine, 'connect')
        def configure_isolated_sqlite(connection, _):
            connection.execute('PRAGMA synchronous=OFF')
            connection.execute('PRAGMA journal_mode=MEMORY')
        Base.metadata.create_all(engine)
        print("Browser fixture ready", flush=True)

        def sessions():
            with Session(engine, expire_on_commit=False) as db:
                yield db
        app.dependency_overrides[get_db] = sessions
        client = TestClient(app)
        request_lock = threading.Lock()
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def handle_request(self):
                try:
                    if self.path.startswith('/api/'):
                        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                        headers = {key: value for key, value in self.headers.items() if key.lower() not in {'host', 'connection', 'content-length'}}
                        with request_lock:
                            calls.append((self.command, self.path))
                            response = client.request(self.command, self.path[4:], content=body, headers=headers)
                        self.send_response(response.status_code)
                        self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                        data = response.content
                    else:
                        path = (output / unquote(self.path.split('?')[0]).lstrip('/')).resolve()
                        if output not in path.parents or not path.is_file():
                            path = output / 'index.html'
                        data = path.read_bytes()
                        self.send_response(200)
                        self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request

        web = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        url = 'http://127.0.0.1:' + str(web.server_address[1])
        from app.core.config import get_settings
        get_settings().FRONTEND_ORIGIN = url
        get_settings().PUBLIC_FRONTEND_URL = url
        with open(artifacts / 'build.log', 'w') as build_log:
            subprocess.run(['npm', 'run', 'build', '--', '--outDir', str(output)], cwd=ROOT / 'frontend',
                           env={**os.environ, 'VITE_API_URL': '/api', 'VITE_BACKEND_URL': '/api', 'VITE_GOOGLE_CLIENT_ID': ''},
                           check=True, stdout=build_log, stderr=subprocess.STDOUT)
        threading.Thread(target=web.serve_forever, daemon=True).start()
        print('Frontend built; starting local Chrome', flush=True)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))

                def screenshot(name):
                    page.screenshot(path=str(artifacts / (name + '.png')), full_page=True)

                def no_overflow():
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), page.url

                print('Checking family navigation and five-person capacity', flush=True)
                def request_api(path, data=None, person=None):
                    headers = {'Authorization': 'Bearer ' + person['access_token']} if person else {}
                    with request_lock:
                        return client.request('GET' if data is None else 'POST', path, json=data, headers=headers)

                def register(name):
                    result = request_api('/auth/register', {'full_name': name, 'email': name.lower().replace(' ', '-') + '@example.com', 'password': 'SyntheticFamilyPassword1!', 'confirm_password': 'SyntheticFamilyPassword1!'})
                    assert result.status_code == 201, result.text
                    return result.json()

                owner = register('Family Owner')
                with Session(engine) as db:
                    sub = db.scalar(select(Subscription).where(Subscription.user_id == owner['user']['id']))
                    sub.plan = 'family_pack'
                    sub.status = 'active'
                    sub.source = 'demo'
                    sub.expires_at = now_utc() + timedelta(days=30)
                    db.commit()
                created = request_api('/family', {'name': 'Family Capacity Test'}, owner)
                assert created.status_code == 201, created.text
                assert created.json()['max_members'] == 5
                assert created.json()['available_slots'] == 4
                assert request_api('/subscriptions', person=owner).json()['limits']['family_members'] == 5
                auth = {'token': owner['access_token'], 'user': owner['user'], 'onboarding_completed': True}
                context.add_init_script('sessionStorage.setItem("maxbud_auth", ' + json.dumps(json.dumps(auth)) + ')')
                expected = {
                    'wallets': 'Shared wallets', 'income': 'Shared income',
                    'expenses': 'Shared expenses & splitting', 'budgets': 'Shared budgets',
                    'goals': 'Shared goals', 'bills': 'Household bills',
                    'reimbursements': 'Reimbursements', 'reports': 'Shared reports',
                    'members': 'Household membership', 'activity': 'Household activity',
                }

                def layout():
                    expect(page.locator('.family-page')).to_have_attribute('aria-busy', 'false')
                    expect(page.locator('.db-sidebar')).to_have_count(1)
                    expect(page.locator('.family-page aside')).to_have_count(0)
                    expect(page.locator('.family-navigation')).to_have_count(0)
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    assert page.locator('.family-page').evaluate('main => { const style = getComputedStyle(main); const content = main.querySelector(".family-content"); return Math.abs(content.getBoundingClientRect().width - (main.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight))) < 2; }')

                for width in [1440, 768, 390]:
                    page.set_viewport_size({'width': width, 'height': 960})
                    page.goto(url + '/dashboard/family')
                    expect(page.locator('.family-task')).to_have_count(10)
                    layout()
                    screenshot('overview-' + str(width))
                    for key, title in expected.items():
                        page.locator('.family-task[href="/dashboard/family/' + key + '"]').click()
                        expect(page.locator('.family-page h1')).to_have_text(title)
                        expect(page).to_have_url(url + '/dashboard/family/' + key)
                        layout()
                        page.get_by_role('link', name='Family Overview', exact=True).click()
                        expect(page.locator('.family-task')).to_have_count(10)
                    print('PASS: all ten cards, correct routes, overview return links, full-width layout at ' + str(width), flush=True)

                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.goto(url + '/dashboard/family/members')
                expect(page.get_by_role('heading', name='Invite someone to your household')).to_be_visible()
                expect(page.locator('.family-invitations')).to_contain_text('1 owner + 4 members (5 people total)')
                people = [register('Family Member ' + str(index)) for index in range(4)]
                for index, person in enumerate(people):
                    page.get_by_label('Invited email', exact=True).fill(person['user']['email'])
                    page.get_by_role('button', name='Create Invitation', exact=True).click()
                    expect(page.locator('.family-created-invite')).to_contain_text(person['user']['email'])
                    invitation_url = page.locator('.family-invitation-url').inner_text()
                    token = invitation_url.split('#invite=', 1)[1].strip()
                    accepted = request_api('/family/invitations/respond', {'token': token, 'accept': True}, person)
                    assert accepted.status_code == 200, accepted.text
                    page.reload()
                    expect(page.locator('.family-member-card')).to_have_count(index + 2)
                full = request_api('/family', person=owner).json()
                assert (full['total_active_members'], full['max_members'], full['available_slots']) == (5, 5, 0)
                expect(page.get_by_role('button', name='Create Invitation', exact=True)).to_be_disabled()
                expect(page.locator('.family-content')).to_contain_text('No invitation spaces available (5 users including the owner')
                denied = request_api('/family/invitations', {'email': 'sixth@example.com', 'can_view_shared': True, 'can_add_shared': True}, owner)
                assert denied.status_code == 409, denied.text
                invitations = request_api('/family/invitations', person=owner).json()
                assert len(invitations) == 4 and all(row['status'] == 'accepted' for row in invitations)
                screenshot('members-full-desktop')
                page.set_viewport_size({'width': 390, 'height': 844})
                layout()
                screenshot('members-full-mobile')
                assert not errors, errors
                browser.close()
                print('PASS: one owner plus four members, legacy setting capped at five, accurate slots, disabled UI and rejected sixth invitation; existing invitations retained. Screenshots: /tmp/maxbud-family-review', flush=True)
        finally:
            web.shutdown()
            web.server_close()
            client.close()
            app.dependency_overrides.clear()
            engine.dispose()


if __name__ == '__main__':
    run()
