"""Disposable browser acceptance. SMTP and AI are mocked only in this harness.
Real Groq verification is separately performed by live_groq.py.
Never opens the configured MySQL or existing family sandbox.
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from core_flow_browser import ROOT, PASSWORD, stop

API = 'http://127.0.0.1:8797'
WEB = 'http://127.0.0.1:5187'


def serve():
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    @event.listens_for(Engine, 'connect')
    def temporary_sqlite_only(connection, _):
        if isinstance(connection, sqlite3.Connection):
            # Only this disposable test process; production durability is unchanged.
            connection.execute('PRAGMA synchronous=OFF')
            connection.execute('PRAGMA journal_mode=MEMORY')
    from core_flow_browser import serve as core_serve
    from app.routers import ai
    from app.services import recovery
    directory = Path(os.environ['CORE_FLOW_DIRECTORY']).resolve()
    assert directory.parent == Path(tempfile.gettempdir()).resolve() and directory.name.startswith('maxbud-core-flow-')
    def complete(content, instructions, schema=None, history=None):
        if schema:
            return json.dumps({'merchant': 'Reviewed Shop', 'date': '2026-11-17', 'total': None, 'currency': 'LKR', 'category': 'Food', 'items': [{'name': 'Milk', 'quantity': 1, 'unit_price': 200, 'amount': 200}]})
        return '## Your recorded budget\n\n**LKR 200** is recorded spending.\n\n- Keep a savings buffer.\n- செலவுகளை கவனமாக திட்டமிடுங்கள்.\n\nUngal budget-ai review pannunga.'
    def send(email, code):
        path = directory / 'test-email.json'
        path.write_text(json.dumps({'email': email, 'code': code}))
        path.chmod(0o600)
    ai.complete = complete
    recovery.configured = lambda: True
    recovery.send_code = send
    core_serve()


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=30000)
    with tempfile.TemporaryDirectory(prefix='maxbud-core-flow-') as scratch:
        env = os.environ | {'CORE_FLOW_DIRECTORY': scratch, 'CORE_FLOW_API_PORT': '8797', 'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false', 'DEMO_PAYMENTS_ENABLED': 'false',
                            'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1', 'RECEIPT_STORAGE_DIR': scratch + '/receipts',
                            'GROQ_API_KEY': '', 'OPENAI_API_KEY': '', 'STRIPE_SECRET_KEY': '', 'STRIPE_WEBHOOK_SECRET': '',
                            'VITE_API_URL': '', 'VITE_BACKEND_URL': '', 'VITE_GOOGLE_CLIENT_ID': '', 'API_PROXY_TARGET': API}
        backend = frontend = None
        with open('/tmp/maxbud-improvements-browser-services.log', 'w+') as log:
            try:
                backend = subprocess.Popen([sys.executable, __file__, '--serve'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
                frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5187', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, start_new_session=True)
                with sync_playwright() as pw:
                    req = pw.request.new_context()
                    for _ in range(600):
                        try:
                            if req.get(WEB + '/api/health', timeout=1000).ok:
                                break
                        except Exception:
                            pass
                        assert backend.poll() is None and frontend.poll() is None
                        time.sleep(.2)
                    else:
                        raise AssertionError('Readiness timeout')
                    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    page = context.new_page()
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    def login(email, password=PASSWORD):
                        response = req.post(WEB + '/api/auth/login', data={'email': email, 'password': password})
                        assert response.ok
                        return response.json()
                    if '--responsive-only' in sys.argv or '--member-only' in sys.argv:
                        def create(name, email):
                            result = req.post(WEB + '/api/auth/register', data={'full_name': name, 'email': email, 'password': PASSWORD, 'confirm_password': PASSWORD})
                            assert result.ok
                            return result.json()
                        person = create('Browser Owner', 'browser-owner@example.com')
                        headers = {'Authorization': 'Bearer ' + person['access_token']}
                        for step, data in [('about-you', {'full_name': 'Browser Owner', 'currency': 'LKR'}), ('income', {'sources': [{'name': 'Planned income', 'amount': '10000'}]}), ('accounts', {'accounts': [{'name': 'Receipt Cash', 'kind': 'cash', 'opening_balance': '1000'}]}), ('budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '500'}]}), ('goals', {'goals': []})]:
                            assert req.post(WEB + '/api/onboarding/' + step, headers=headers, data=data).ok
                        admin = create('Browser Admin', 'browser-admin@example.com')
                        with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                            db.execute('PRAGMA synchronous=OFF')
                            db.execute('UPDATE users SET role=?,onboarding_completed=1 WHERE id=?', ('admin', admin['user']['id']))
                            db.execute('UPDATE subscriptions SET plan=?,source=?,status=?,expires_at=? WHERE user_id=?', ('family_pack', 'demo', 'active', '2099-01-01', person['user']['id']))
                        person = login('browser-owner@example.com')
                        headers = {'Authorization': 'Bearer ' + person['access_token']}
                        assert req.post(WEB + '/api/family', headers=headers, data={'name': 'Browser Household'}).ok
                        assert req.post(WEB + '/api/goals?scope=family', headers=headers, data={'name': 'Shared Travel', 'target_amount': '5000'}).ok
                        page.goto(WEB + '/login', wait_until='domcontentloaded')
                        page.evaluate('value => sessionStorage.setItem("maxbud_auth", JSON.stringify(value))', {'token': person['access_token'], 'user': person['user'], 'onboarding_completed': True})
                    else:
                        page.goto(WEB, wait_until='domcontentloaded')
                        expect(page.locator('.showcase-card')).to_have_count(6)
                        # Compare computed border/radius/hover; never alter the approved other four.
                        borders = page.locator('.showcase-card').evaluate_all('(cards) => cards.map(c => { const s=getComputedStyle(c); return [s.borderWidth,s.borderColor,s.borderStyle,s.borderRadius]; })')
                        assert all(row == borders[0] for row in borders), borders
                        assert page.locator('.section-heading > p').count() == 0
                        expect(page.locator('#pricing')).to_contain_text('LKR 650')
                        expect(page.locator('#pricing')).to_contain_text('LKR 900')
                        print('PASS landing: all six computed outlines match; concise headings and canonical prices; hero untouched in source', flush=True)

                        page.goto(WEB + '/register', wait_until='domcontentloaded')
                        page.get_by_label('Full Name', exact=True).fill('Browser Owner')
                        page.get_by_label('Email Address', exact=True).fill('browser-owner@example.com')
                        page.get_by_label('Password', exact=True).fill(PASSWORD)
                        page.get_by_label('Confirm Password', exact=True).fill(PASSWORD)
                        page.get_by_role('button', name='Create Account', exact=False).click()
                        page.wait_for_url('**/onboarding')
                        person = login('browser-owner@example.com')
                        headers = {'Authorization': 'Bearer ' + person['access_token']}
                        for step, data in [('about-you', {'full_name': 'Browser Owner', 'currency': 'LKR'}), ('income', {'sources': [{'name': 'Planned income', 'amount': '10000'}]}), ('accounts', {'accounts': [{'name': 'Receipt Cash', 'kind': 'cash', 'opening_balance': '1000'}]}), ('budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '500'}]}), ('goals', {'goals': []})]:
                            response = req.post(WEB + '/api/onboarding/' + step, headers=headers, data=data)
                            assert response.ok, response.text()
                        page.goto(WEB + '/login', wait_until='domcontentloaded')
                        page.get_by_label('Email Address', exact=True).fill('browser-owner@example.com')
                        page.get_by_label('Password', exact=True).fill('wrong')
                        page.get_by_role('button', name='Sign In', exact=False).click()
                        expect(page.get_by_role('alert')).to_contain_text('Invalid')
                        page.get_by_label('Password', exact=True).fill(PASSWORD)
                        page.get_by_role('button', name='Sign In', exact=False).click()
                        page.wait_for_url('**/dashboard')
                        print('PASS auth: browser registration, invalid credentials and login; original fields retained', flush=True)

                        page.goto(WEB + '/dashboard/ai-scan', wait_until='domcontentloaded')
                        page.get_by_label('Receipt image', exact=True).set_input_files(ROOT / 'backend/sample_receipt.jpg')
                        page.get_by_role('button', name='Scan receipt', exact=True).click()
                        expect(page.get_by_role('heading', name='Review receipt', exact=True)).to_be_visible()
                        expect(page.get_by_label('Reviewed transaction total', exact=True)).to_have_value('')
                        page.get_by_label('Reviewed transaction total', exact=True).fill('200')
                        page.get_by_label('Expense category', exact=True).select_option('Food')
                        page.get_by_label('Account', exact=True).select_option(label='Receipt Cash')
                        with page.expect_response(lambda r: '/confirm' in r.url and r.request.method == 'POST') as saved:
                            page.get_by_role('button', name='Confirm expense', exact=True).click()
                        assert saved.value.ok, saved.value.text()
                        expect(page.get_by_role('heading', name='Transaction saved', exact=True)).to_be_visible()
                        transaction_id = saved.value.json()['transaction_id']
                        account = req.get(WEB + '/api/accounts', headers=headers).json()['items'][0]
                        assert account['current_balance'] == '800.00'
                        budgets = req.get(WEB + '/api/budgets', headers=headers).json()
                        assert budgets[0]['spent'] == '200.00'
                        page.get_by_role('link', name='View saved transaction', exact=True).click()
                        expect(page.locator('main')).to_contain_text('Reviewed Shop')
                        page.reload(wait_until='domcontentloaded')
                        expect(page.locator('main')).to_contain_text('Reviewed Shop')
                        assert len(req.get(WEB + '/api/transactions', headers=headers).json()) == 1
                        print('PASS scanner: real image upload with mocked AI; missing total stays empty; one persisted transaction, account 800, budget 200, visible after refresh', flush=True)

                        page.goto(WEB + '/dashboard/ai-advisor', wait_until='domcontentloaded')
                        page.get_by_label('Your question', exact=True).fill('En budget eppadi? தமிழில் சொல்லுங்கள்.')
                        page.get_by_role('button', name='Send question', exact=True).click()
                        expect(page.locator('.advisor-prose')).to_contain_text('LKR 200')
                        expect(page.locator('.advisor-prose')).to_contain_text('செலவுகளை')
                        expect(page.locator('.advisor-prose')).not_to_contain_text('{"')
                        page.screenshot(path='/tmp/maxbud-polish-advisor-conversation.png', full_page=True)
                        page.reload(wait_until='domcontentloaded')
                        expect(page.locator('.advisor-prose')).to_contain_text('LKR 200')
                        print('PASS advisor: submission, safe English/Tamil/Tanglish rendering and persisted history (mocked provider)', flush=True)

                        # New synthetic admin and Family Pack fixtures only inside this disposable DB.
                        admin = req.post(WEB + '/api/auth/register', data={'full_name': 'Browser Admin', 'email': 'browser-admin@example.com', 'password': PASSWORD, 'confirm_password': PASSWORD}).json()
                        with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                            db.execute('PRAGMA synchronous=OFF')
                            db.execute('UPDATE users SET role=?,onboarding_completed=1 WHERE id=?', ('admin', admin['user']['id']))
                            db.execute('UPDATE subscriptions SET plan=?,source=?,status=?,expires_at=? WHERE user_id=?', ('family_pack', 'demo', 'active', '2099-01-01', person['user']['id']))
                        # Subscription persists across logout/login; no further payment required.
                        renewed_login = login('browser-owner@example.com')
                        headers = {'Authorization': 'Bearer ' + renewed_login['access_token']}
                        assert req.get(WEB + '/api/subscriptions', headers=headers).json()['plan'] == 'family_pack'
                        family = req.post(WEB + '/api/family', headers=headers, data={'name': 'Browser Household'})
                        assert family.status == 201
                        page.goto(WEB + '/dashboard/family', wait_until='domcontentloaded')
                        page.get_by_role('link', name='Manage Goals', exact=True).click()
                        expect(page.get_by_role('heading', name='Shared goals', exact=True)).to_be_visible()
                        page.get_by_role('button', name='New shared goal', exact=True).click()
                        page.get_by_label('Goal name', exact=True).fill('Shared Travel')
                        page.get_by_label('Target amount (LKR)', exact=True).fill('5000')
                        page.get_by_role('button', name='Save shared goal', exact=True).click()
                        expect(page.get_by_role('heading', name='Shared Travel', exact=True)).to_be_visible()

                    if '--member-only' in sys.argv:
                        verify_member(req, page, browser, person, headers, scratch, expect)
                        assert not errors, errors
                        browser.close()
                        return
                    for width in [360, 768, 1024, 1440]:
                        page.set_viewport_size({'width': width, 'height': 1000})
                        for path, selector in [('/', '#features'), ('/login', '.auth-card'), ('/register', '.auth-card'), ('/dashboard/family/goals', '.family-page'), ('/dashboard/ai-scan', '.receipt-workspace'), ('/dashboard/ai-advisor', '.advisor-chat')]:
                            page.goto(WEB + path, wait_until='domcontentloaded')
                            expect(page.locator(selector)).to_be_visible()
                            if path == '/dashboard/family/goals':
                                expect(page.get_by_role('heading', name='Shared Travel', exact=True)).to_be_visible()
                            elif path == '/dashboard/ai-advisor':
                                expect(page.get_by_text('Loading your conversation…', exact=True)).not_to_be_visible()
                            elif path == '/dashboard/ai-scan':
                                expect(page.get_by_text('Loading scan allowance…', exact=False)).not_to_be_visible()
                            elif path == '/':
                                expect(page.locator('#pricing')).to_contain_text('LKR 650')
                            if not page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'):
                                page.screenshot(path='/tmp/maxbud-polish-overflow.png', full_page=True)
                                offenders = page.locator('body *').evaluate_all('(nodes) => nodes.map(n => ({tag:n.tagName, cls:n.className, left:n.getBoundingClientRect().left, right:n.getBoundingClientRect().right})).filter(n => n.left >= 0 && n.right > innerWidth + 2).slice(0,20)')
                                raise AssertionError((width, path, offenders))
                            if path in ['/login', '/register']:
                                box = page.locator('.auth-brand').bounding_box()
                                panel = page.locator('.auth-card').bounding_box()
                                assert abs((box['x'] + box['width']/2) - (panel['x'] + panel['width']/2)) < 3
                            page.screenshot(path=f'/tmp/maxbud-polish-{width}-{path.split("/")[-1] or "landing"}.png', full_page=True)
                    print('PASS responsive: landing/auth/family/scanner/advisor at 360/768/1024/1440; centered auth logos and no horizontal page overflow', flush=True)

                    # Full password recovery via UI using the private mocked SMTP transport.
                    page.goto(WEB + '/login', wait_until='domcontentloaded')
                    page.get_by_role('link', name='Forgot password?', exact=True).click()
                    page.get_by_label('Email address', exact=True).fill('browser-owner@example.com')
                    page.get_by_role('button', name='Send recovery code', exact=True).click()
                    expect(page.get_by_label('Recovery code', exact=True)).to_be_visible()
                    code = json.loads((Path(scratch) / 'test-email.json').read_text())['code']
                    page.get_by_label('Recovery code', exact=True).fill(code)
                    page.get_by_role('button', name='Verify code', exact=True).click()
                    page.get_by_label('New password', exact=True).fill('NewBrowserPassword2!')
                    page.get_by_label('Confirm password', exact=True).fill('NewBrowserPassword2!')
                    page.get_by_role('button', name='Save new password', exact=True).click()
                    expect(page.get_by_role('heading', name='You’re ready to sign in', exact=True)).to_be_visible()
                    page.get_by_role('link', name='Back to sign in', exact=True).click()
                    page.get_by_label('Email Address', exact=True).fill('browser-owner@example.com')
                    page.get_by_label('Password', exact=True).fill('NewBrowserPassword2!')
                    page.get_by_role('button', name='Sign In', exact=False).click()
                    page.wait_for_url('**/dashboard')
                    assert req.get(WEB + '/api/auth/me', headers=headers).status == 401
                    print('PASS recovery: actual UI request/verify/reset/new-password login, old JWT revoked; mocked SMTP only', flush=True)

                    page.goto(WEB + '/login', wait_until='domcontentloaded')
                    page.get_by_label('Email Address', exact=True).fill('browser-admin@example.com')
                    page.get_by_label('Password', exact=True).fill(PASSWORD)
                    page.get_by_role('button', name='Sign In', exact=False).click()
                    page.wait_for_url('**/dashboard/admin', wait_until='domcontentloaded')
                    page.goto(WEB + '/dashboard/admin', wait_until='domcontentloaded')
                    expect(page.get_by_role('heading', name='Administration', exact=True)).to_be_visible()
                    admin_session = login('browser-admin@example.com')
                    admin_headers = {'Authorization': 'Bearer ' + admin_session['access_token']}
                    expect(page.locator('.db-metric-grid')).to_be_visible()
                    overview_response = req.get(WEB + '/api/admin/overview', headers=admin_headers)
                    assert overview_response.ok and 'Reviewed Shop' not in overview_response.text()
                    for endpoint, tab in [('users', 'User Management'), ('subscriptions', 'Subscriptions'), ('billing', 'Demo Billing Reports'), ('ai-usage', 'AI Usage Monitoring'), ('activity', 'Support / Activity'), ('settings', 'Admin Settings')]:
                        with page.expect_response(lambda r: '/admin/' + endpoint in r.url and r.request.method == 'GET') as response:
                            page.get_by_role('navigation', name='Admin modules').get_by_role('button', name=tab, exact=True).click()
                        assert response.value.ok
                        response.value.finished()
                        body = response.value.text()
                        assert 'Reviewed Shop' not in body and 'Receipt Cash' not in body
                        expect(page.get_by_text('Loading platform data…', exact=True)).not_to_be_visible()
                    page.get_by_role('navigation', name='Admin modules').get_by_role('button', name='User Management', exact=True).click()
                    page.get_by_label('Search users', exact=True).fill('browser-owner@example.com')
                    page.get_by_role('button', name='Search', exact=True).click()
                    row = page.get_by_role('row').filter(has_text='browser-owner@example.com')
                    for action in ['Suspend', 'Reactivate']:
                        page.once('dialog', lambda dialog: dialog.accept())
                        with page.expect_response(lambda r: '/admin/users/' in r.url and r.request.method == 'PATCH') as response:
                            row.get_by_role('button', name=action, exact=True).click()
                        assert response.value.ok, response.value.text()
                        expect(row.get_by_role('button', name='Reactivate' if action == 'Suspend' else 'Suspend', exact=True)).to_be_visible()
                    print('PASS admin actions: live backend data for seven modules; confirmed user suspension/reactivation; financial details absent', flush=True)
                    for width in [360, 768, 1024, 1440]:
                        page.set_viewport_size({'width': width, 'height': 1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2'), (width, 'admin')
                        page.screenshot(path=f'/tmp/maxbud-polish-{width}-admin.png', full_page=True)
                    assert not errors, errors
                    print('PASS admin: real admin login and all seven data modules, responsive widths, no private finance exposure; no browser JS errors', flush=True)
                    browser.close()
            finally:
                stop(frontend); stop(backend)


def verify_member(req, owner, browser, person, headers, scratch, expect):
    member = req.post(WEB + '/api/auth/register', data={'full_name': 'Browser Member', 'email': 'browser-member@example.com', 'password': PASSWORD, 'confirm_password': PASSWORD}).json()
    member_headers = {'Authorization': 'Bearer ' + member['access_token']}
    for step, data in [('about-you', {'full_name': 'Browser Member', 'currency': 'LKR'}), ('income', {'sources': [{'name': 'PRIVATE salary plan', 'amount': '10000'}]}), ('accounts', {'accounts': [{'name': 'Member private cash', 'kind': 'cash', 'opening_balance': '1000'}]}), ('budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '500'}]}), ('goals', {'goals': []})]:
        assert req.post(WEB + '/api/onboarding/' + step, headers=member_headers, data=data).ok
    with sqlite3.connect(Path(scratch) / 'flow.db') as db:
        db.execute('PRAGMA synchronous=OFF')
        db.execute('UPDATE subscriptions SET expires_at=? WHERE user_id=?', ('2000-01-01', member['user']['id']))
    owner.goto(WEB + '/dashboard/family/members', wait_until='domcontentloaded')
    owner.get_by_label('Invited email', exact=True).fill('browser-member@example.com')
    owner.get_by_role('button', name='Create secure invitation', exact=True).click()
    link = owner.get_by_label('Invitation link', exact=True)
    expect(link).to_be_visible()
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    page.goto(WEB + '/login', wait_until='domcontentloaded')
    page.get_by_label('Email Address', exact=True).fill('browser-member@example.com')
    page.get_by_label('Password', exact=True).fill(PASSWORD)
    page.get_by_role('button', name='Sign In', exact=False).click()
    page.wait_for_url('**/dashboard', wait_until='domcontentloaded')
    page.goto(link.input_value(), wait_until='domcontentloaded')
    page.get_by_role('button', name='Accept invitation', exact=True).click()
    page.get_by_role('link', name='Manage Goals', exact=True).click()
    page.get_by_role('button', name='Contribute to Shared Travel', exact=True).click()
    page.get_by_label('Contribution amount (LKR)', exact=True).fill('200')
    with page.expect_response(lambda r: r.url.endswith('/contribute') and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Record contribution', exact=True).click()
    assert response.value.ok, response.value.text()
    goal = response.value.json()
    assert goal['saved_amount'] == '200.00'
    assert goal['history'][0]['user_id'] == member['user']['id']
    owner.goto(WEB + '/dashboard/family/goals', wait_until='domcontentloaded')
    expect(owner.locator('.family-goal-numbers')).to_contain_text('LKR 200')
    rights = req.get(WEB + '/api/subscriptions', headers=member_headers).json()
    assert rights['plan'] == 'read_only' and rights['limits']['advisor_messages'] == 0 and rights['household_allowed']
    assert req.post(WEB + '/api/accounts', headers=member_headers, data={'name': 'Forbidden', 'kind': 'cash'}).status == 403
    wallet = req.post(WEB + '/api/family/wallets', headers=headers, data={'name': 'Common cash'}).json()
    assert req.post(WEB + '/api/family/income', headers=headers, data={'account_id': wallet['id'], 'category': 'Common earnings', 'amount': '1000', 'request_id': 'owner-common-income'}).status == 201
    page.goto(WEB + '/dashboard/family/wallets', wait_until='domcontentloaded')
    page.get_by_role('button', name='Contribute to wallet', exact=True).click()
    page.get_by_label('Amount (LKR)', exact=True).fill('100')
    page.get_by_label('Payment account', exact=True).select_option(label='Personal: Member private cash')
    with page.expect_response(lambda r: r.url.endswith('/contribute') and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Save shared record', exact=True).click()
    assert response.value.ok, response.value.text()
    page.goto(WEB + '/dashboard/family/expenses', wait_until='domcontentloaded')
    page.get_by_role('button', name='Add shared expense', exact=True).click()
    page.get_by_label('Amount (LKR)', exact=True).fill('150')
    page.get_by_label('Shared note', exact=True).fill('Shared groceries')
    page.get_by_label('Payment account', exact=True).select_option(label='Shared: Common cash')
    with page.expect_response(lambda r: r.url.endswith('/family/expenses') and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Save shared record', exact=True).click()
    assert response.value.status == 201, response.value.text()
    page.reload(wait_until='domcontentloaded')
    expect(page.get_by_role('cell', name='Shared groceries', exact=True)).to_be_visible()
    bill = req.post(WEB + '/api/family/bills', headers=headers, data={'name': 'Shared electricity', 'category': 'Food', 'amount': '10', 'account_id': wallet['id'], 'due_date': '2026-11-17', 'recurrence': 'none'})
    assert bill.status == 201
    notifications = req.get(WEB + '/api/notifications', headers=member_headers).json()
    assert any('Shared electricity' in row['message'] for row in notifications)
    page.goto(WEB + '/dashboard/family/bills', wait_until='domcontentloaded')
    with page.expect_response(lambda r: r.url.endswith('/pay') and r.request.method == 'POST') as response:
        page.get_by_role('button', name='Mark household bill paid', exact=True).click()
    assert response.value.ok, response.value.text()
    page.goto(WEB + '/dashboard/family/reports', wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='Member contributions', exact=True)).to_be_visible()
    expect(page.locator('main')).not_to_contain_text('PRIVATE salary plan')
    expect(page.locator('main')).not_to_contain_text('Member private cash')
    report = req.get(WEB + '/api/dashboard?scope=family', headers=member_headers).json()
    assert (report['monthly_income'], report['monthly_expenses'], report['monthly_wallet_funding'], report['total_balance']) == ('1000.00', '160.00', '100.00', '940.00')
    page.goto(WEB + '/dashboard/family/activity', wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='Shared financial activity', exact=True)).to_be_visible()
    expect(page.locator('main')).to_contain_text('Goal allocation')
    expect(page.locator('main')).to_contain_text('Wallet contribution (transfer)')
    expect(page.locator('main')).not_to_contain_text('Member private cash')
    owner.goto(WEB + '/dashboard/family/members', wait_until='domcontentloaded')
    owner.get_by_label('Allow shared editing for Browser Member', exact=True).uncheck()
    expect(owner.get_by_label('Allow shared editing for Browser Member', exact=True)).not_to_be_checked()
    page.goto(WEB + '/dashboard/family/goals', wait_until='domcontentloaded')
    expect(page.get_by_role('button', name='Contribute to Shared Travel', exact=True)).to_be_disabled()
    assert req.post(WEB + f"/api/goals/{goal['id']}/contribute", headers=member_headers, data={'amount': '1', 'request_id': 'revoked'}).status == 403
    page.screenshot(path='/tmp/maxbud-polish-member-permissions.png', full_page=True)
    context.close()
    print('PASS member browser: expired personal trial stays read-only/zero AI; shared goal 200, wallet transfer 100, expense 150 and bill 10 save; notifications/activity/reports private and exact; owner permission revocation enforced', flush=True)


if __name__ == '__main__':
    serve() if '--serve' in sys.argv else run()
