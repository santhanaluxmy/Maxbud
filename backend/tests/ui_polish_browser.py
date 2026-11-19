"""Full React/API smoke test with temporary SQLite and mocked AI; no genuine records.
Run: FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/ui_polish_browser.py
Requires installed Playwright and /usr/bin/google-chrome.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=15000)
    with tempfile.TemporaryDirectory(prefix='maxbud-ui-browser-') as scratch:
        directory = Path(scratch)
        output = directory / 'dist'
        artifacts = Path('/tmp/maxbud-ui-review')
        artifacts.mkdir(exist_ok=True)
        os.environ.update({
            'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false', 'JWT_SECRET': secrets.token_urlsafe(48),
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
        from app.models.ai import MerchantRule
        from app.models.family import Subscription
        from app.models.user import now_utc
        from datetime import timedelta
        from PIL import Image
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

                print('Checking authentication', flush=True)
                page.goto(url + '/login')
                illustration = page.locator('.auth-visual > img').get_attribute('src')
                logo_size = page.locator('.auth-brand img').evaluate('(img) => [getComputedStyle(img).width, getComputedStyle(img).height, getComputedStyle(img).objectFit]')
                page.get_by_role('button', name='Sign In').click()
                expect(page.locator('#email-error')).to_be_visible()
                expect(page.locator('#password-error')).to_be_visible()
                page.get_by_role('textbox', name='Email Address').fill('missing@example.com')
                page.get_by_label('Password', exact=True).fill('WrongPassword1!')
                page.get_by_role('button', name='Sign In').click()
                expect(page.locator('form .auth-feedback')).to_contain_text('Invalid email or password')
                assert page.locator('form').evaluate('(form) => Boolean(form.querySelector(".auth-feedback").compareDocumentPosition(form.querySelector("button[type=submit]")) & Node.DOCUMENT_POSITION_FOLLOWING)')
                screenshot('login')
                page.goto(url + '/register')
                assert page.locator('.auth-visual > img').get_attribute('src') == illustration
                assert page.locator('.auth-brand img').evaluate('(img) => [getComputedStyle(img).width, getComputedStyle(img).height, getComputedStyle(img).objectFit]') == logo_size
                page.get_by_role('button', name='Create Account').click()
                expect(page.locator('#name-error')).to_be_visible()
                expect(page.locator('#email-error')).to_be_visible()
                expect(page.locator('#password-error')).to_be_visible()
                page.get_by_role('textbox', name='Full Name').fill('UI Test User')
                page.get_by_role('textbox', name='Email Address').fill('polish@example.com')
                page.get_by_label('Password', exact=True).fill('SyntheticPassword1!')
                page.get_by_label('Confirm Password', exact=True).fill('different')
                page.get_by_role('button', name='Create Account').click()
                expect(page.locator('#confirmPassword-error')).to_be_visible()
                page.get_by_label('Confirm Password', exact=True).fill('SyntheticPassword1!')
                screenshot('register')
                page.get_by_role('button', name='Create Account').click()
                expect(page.get_by_role('heading', name='Tell us about yourself')).to_be_visible()
                expect(page.get_by_text('Step 1 of 4')).to_be_visible()
                page.get_by_role('button', name='Save & Continue').click()
                expect(page.get_by_role('heading', name='Where do you keep money?')).to_be_visible()
                page.get_by_label('Opening balance', exact=True).fill('1000.10')
                page.get_by_role('button', name='Add account', exact=True).click()
                page.get_by_label('Account name', exact=True).nth(1).fill('Bank')
                page.get_by_label('Opening balance', exact=True).nth(1).fill('500.20')
                page.get_by_role('button', name='Save & Continue').click()
                expect(page.get_by_text('Step 3 of 4')).to_be_visible()
                page.get_by_label('Food', exact=True).fill('1000')
                expect(page.locator('.ob-allocation')).to_contain_text('Within available balance · LKR 500.3 unallocated')
                page.get_by_label('Food', exact=True).fill('2000')
                expect(page.locator('.ob-allocation')).to_contain_text('Over allocated · LKR 499.7')
                page.get_by_text('How do spending limits work?', exact=True).click()
                page.locator('#budget-example').press('End')
                expect(page.locator('output')).to_contain_text('over the limit')
                screenshot('onboarding-budget')
                page.reload()
                expect(page.get_by_text('Step 3 of 4')).to_be_visible()
                expect(page.locator('.ob-allocation')).to_contain_text('LKR 1,500.3')
                page.get_by_label('Food', exact=True).fill('500')
                page.get_by_role('button', name='Save & Continue').click()
                expect(page.get_by_text('Step 4 of 4')).to_be_visible()
                page.get_by_role('button', name='Open my dashboard').click()
                expect(page.get_by_role('heading', name='Welcome back, UI')).to_be_visible()
                session = page.evaluate('JSON.parse(localStorage.getItem("maxbud_auth") || sessionStorage.getItem("maxbud_auth"))')
                headers = {'Authorization': 'Bearer ' + session['token']}
                accounts = client.get('/accounts', headers=headers).json()['items']
                assert [row['current_balance'] for row in accounts] == ['1000.10', '500.20']
                assert not any(path == '/api/onboarding/income' for _, path in calls)
                expect(page.locator('.db-search')).to_have_count(0)
                screenshot('overview')
                no_overflow()

                with Session(engine) as db:
                    db.add(MerchantRule(user_id=session['user']['id'], merchant='known store', category='Food'))
                    db.commit()
                image = BytesIO()
                Image.new('RGB', (40, 40), 'white').save(image, format='PNG')
                extracted = json.dumps({'merchant': 'Extracted Store', 'date': '2026-11-19', 'total': 25, 'currency': None, 'category': 'Food', 'items': [{'name': 'Rice', 'amount': 25}]})
                page.goto(url + '/dashboard/ai-scan')
                page.get_by_label('Receipt image').set_input_files({'name': 'test.png', 'mimeType': 'image/png', 'buffer': image.getvalue()})
                with patch('app.routers.ai.complete', return_value=extracted):
                    page.get_by_role('button', name='Scan receipt', exact=True).click()
                    expect(page.get_by_role('combobox', name='Merchant', exact=True)).to_have_value('Extracted Store')
                expect(page.get_by_label('Currency', exact=True)).to_have_value('LKR')
                expect(page.get_by_label('Expense category', exact=True)).to_have_value('Food')
                assert client.get('/transactions', headers=headers).json() == []
                merchant = page.get_by_role('combobox', name='Merchant', exact=True)
                merchant.fill('known')
                page.get_by_role('option', name='known store', exact=True).click()
                expect(merchant).to_have_value('known store')
                merchant.fill('New Merchant')
                page.get_by_role('option', name='Use “New Merchant” as a new merchant').click()
                page.get_by_label('Account', exact=True).select_option(str(accounts[0]['id']))
                page.get_by_label('Currency', exact=True).select_option('USD')
                expect(page.get_by_role('button', name='Confirm expense')).to_be_disabled()
                page.get_by_label('Currency', exact=True).select_option('LKR')
                page.get_by_label('Account', exact=True).select_option(str(accounts[0]['id']))
                screenshot('receipt-review')
                page.set_viewport_size({'width': 390, 'height': 844})
                no_overflow()
                screenshot('receipt-review-mobile')
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.get_by_role('button', name='Confirm expense').evaluate('(button) => { button.click(); button.click(); }')
                expect(page.get_by_role('heading', name='Transaction saved', exact=True)).to_be_visible()
                assert len(client.get('/transactions', headers=headers).json()) == 1
                assert len([path for method, path in calls if method == 'POST' and path.endswith('/confirm')]) == 1
                assert client.get('/accounts', headers=headers).json()['items'][0]['current_balance'] == '975.10'

                page.goto(url + '/dashboard/ai-advisor')
                expect(page.get_by_text('Make room for a clearer plan')).to_be_visible()
                page.get_by_label('Your question', exact=True).fill('How can I plan my budget?')
                with patch('app.routers.ai.complete', return_value='## A practical plan\n\nKeep your Food spending within LKR 500.'):
                    page.get_by_role('button', name='Send question').click()
                    expect(page.get_by_role('heading', name='A practical plan')).to_be_visible()
                assert page.locator('.advisor-conversation').evaluate('(node) => getComputedStyle(node).overflowY') == 'visible'
                page.reload()
                expect(page.get_by_role('heading', name='A practical plan')).to_be_visible()
                screenshot('advisor')
                no_overflow()

                with Session(engine) as db:
                    sub = db.scalar(select(Subscription).where(Subscription.user_id == session['user']['id']))
                    sub.plan = 'family_pack'; sub.status = 'active'; sub.source = 'demo'; sub.expires_at = now_utc() + timedelta(days=30)
                    db.commit()
                created = client.post('/family', headers=headers, json={'name': 'Test Household'})
                assert created.status_code == 201, created.text
                for section in ['', '/wallets', '/income', '/expenses', '/budgets', '/goals', '/reimbursements', '/reports', '/bills', '/activity', '/members']:
                    page.goto(url + '/dashboard/family' + section)
                    expect(page.locator('.family-navigation')).to_have_count(0)
                    expect(page.get_by_text('Loading family membership…')).to_have_count(0)
                    no_overflow()
                screenshot('family-members-desktop')
                page.goto(url + '/dashboard/family/wallets')
                page.get_by_role('button', name='New shared wallet').click()
                page.locator('.family-form').get_by_label('Name', exact=True).fill('Household Wallet')
                page.get_by_role('button', name='Save shared record', exact=True).click()
                expect(page.get_by_role('heading', name='Household Wallet', exact=True)).to_be_visible()
                page.get_by_role('button', name='Contribute to wallet', exact=True).click()
                page.locator('.family-form').get_by_label('Amount (LKR)', exact=True).fill('100')
                page.get_by_role('combobox', name='Payment account', exact=True).select_option(str(accounts[0]['id']))
                page.get_by_role('button', name='Save shared record', exact=True).click()
                expect(page.locator('.family-shared-goal')).to_contain_text('LKR 100')
                page.goto(url + '/dashboard/family/budgets')
                page.get_by_role('button', name='New shared budget').click()
                page.locator('.family-form').get_by_label('Category', exact=True).fill('Food')
                page.locator('.family-form').get_by_label('Monthly limit (LKR)', exact=True).fill('50')
                page.get_by_role('button', name='Save shared record', exact=True).click()
                expect(page.get_by_role('heading', name='Food', exact=True)).to_be_visible()
                page.goto(url + '/dashboard/family/goals')
                page.get_by_role('button', name='New shared goal').click()
                page.get_by_label('Goal name', exact=True).fill('Family Holiday')
                page.get_by_label('Target amount (LKR)', exact=True).fill('500')
                page.get_by_role('button', name='Save shared goal', exact=True).click()
                expect(page.get_by_role('heading', name='Family Holiday', exact=True)).to_be_visible()
                page.goto(url + '/dashboard/family/members')
                page.get_by_label('Invited email', exact=True).fill('synthetic-invite@example.com')
                page.get_by_role('button', name='Create Invitation', exact=True).click()
                expect(page.locator('.family-created-invite')).to_be_visible()
                page.goto(url + '/dashboard/family')
                expect(page.locator('.family-task')).to_have_count(10)
                screenshot('family-overview-desktop')
                page.set_viewport_size({'width': 390, 'height': 844})
                for path in ['/dashboard/family', '/dashboard/family/members', '/dashboard/family/reports', '/dashboard/ai-advisor', '/dashboard/ai-scan', '/dashboard/accounts', '/dashboard/transactions', '/dashboard/budgets', '/dashboard/goals', '/dashboard/reminders', '/login', '/register', '/']:
                    page.goto(url + path)
                    page.wait_for_load_state('networkidle')
                    no_overflow()
                    if path in ['/dashboard/family', '/dashboard/family/members', '/dashboard/ai-advisor', '/register']:
                        screenshot(path.strip('/').replace('/', '-') + '-mobile')
                assert not errors, errors
                browser.close()
                print('PASS: auth validation, four-step onboarding + resume, balances, scanner confirmation/idempotency, advisor persistence, all family routes, desktop/mobile overflow. Screenshots: /tmp/maxbud-ui-review')
        finally:
            web.shutdown()
            web.server_close()
            client.close()
            app.dependency_overrides.clear()
            engine.dispose()


if __name__ == '__main__':
    run()
