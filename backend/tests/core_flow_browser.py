"""Real browser -> Vite /api proxy -> FastAPI -> disposable SQLite flow.

Run from backend: .venv/bin/python tests/core_flow_browser.py
No provider calls, migrations or genuine MySQL writes. All services and data are
created in a temporary directory and stopped afterward, including on failure.
"""
from contextlib import asynccontextmanager
from decimal import Decimal
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
API = 'http://127.0.0.1:8768'
WEB = 'http://127.0.0.1:5178'
PASSWORD = 'BrowserFlowPassword1!'


def serve():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.database import Base, get_db
    from app.main import app
    import app.main as main
    import uvicorn

    # This harness can only create a database inside its temporary directory.
    directory = Path(os.environ['CORE_FLOW_DIRECTORY']).resolve()
    if not directory.name.startswith('maxbud-core-flow-') or directory.parent != Path(tempfile.gettempdir()).resolve():
        raise RuntimeError('Core browser tests require their own temporary directory')
    engine = create_engine(f'sqlite:///{directory / "flow.db"}', connect_args={'check_same_thread': False})
    main.engine = engine  # /health must also use the disposable database.
    Base.metadata.create_all(engine)

    def session():
        with Session(engine, expire_on_commit=False) as db:
            yield db

    @asynccontextmanager
    async def lifespan(_):
        yield
        engine.dispose()

    app.router.lifespan_context = lifespan
    app.dependency_overrides[get_db] = session
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('CORE_FLOW_API_PORT', '8768')), log_level=os.environ.get('CORE_FLOW_LOG_LEVEL', 'warning'))


def stop(process):
    if process is not None and process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=15000)
    with tempfile.TemporaryDirectory(prefix='maxbud-core-flow-') as scratch:
        env = os.environ | {
            'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1',
            'CORE_FLOW_DIRECTORY': scratch, 'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false',
            'GROQ_API_KEY': '', 'GROQ_CHAT_MODEL': '', 'GROQ_VISION_MODEL': '', 'OPENAI_API_KEY': '',
            'RECEIPT_STORAGE_DIR': scratch + '/receipts', 'DEMO_PAYMENTS_ENABLED': 'false',
            'VITE_API_URL': '', 'VITE_BACKEND_URL': '', 'VITE_GOOGLE_CLIENT_ID': '',
            'API_PROXY_TARGET': API,
        }
        backend = frontend = None
        with open(Path(scratch) / 'services.log', 'w+') as log:
            def start_backend():
                return subprocess.Popen([sys.executable, __file__, '--serve'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)

            try:
                backend = start_backend()
                frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5178', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, start_new_session=True)
                with sync_playwright() as pw:
                    request = pw.request.new_context()

                    def ready(url):
                        for _ in range(160):
                            try:
                                if request.get(url, timeout=1000).ok:
                                    return
                            except Exception:
                                pass
                            if backend.poll() is not None or frontend.poll() is not None:
                                break
                            time.sleep(.2)
                        log.seek(0)
                        raise RuntimeError('Test services failed to start: ' + log.read()[-2000:])

                    ready(WEB + '/api/health')
                    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    errors = []
                    unexpected = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('request', lambda req: unexpected.append(req.url) if req.url.startswith(API) else None)

                    def go(path):
                        page.goto(WEB + path)
                        expect(page.locator('main h1')).to_be_visible()

                    def submit(dialog, name):
                        dialog.get_by_role('button', name=name, exact=True).click()
                        expect(dialog).not_to_be_visible()

                    def data(path):
                        token = page.evaluate('JSON.parse(sessionStorage.getItem("maxbud_auth")).token')
                        response = context.request.get(WEB + '/api' + path, headers={'Authorization': 'Bearer ' + token})
                        assert response.ok, f'{path}: HTTP {response.status}'
                        return response.json()

                    page.goto(WEB + '/register')
                    page.locator('input[name="name"]').fill('Flow Tester')
                    page.locator('input[name="email"]').fill('flow@example.com')
                    page.locator('input[name="password"]').fill(PASSWORD)
                    page.locator('input[name="confirmPassword"]').fill(PASSWORD)
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page).to_have_url(WEB + '/onboarding')
                    page.get_by_role('button', name='Save & Continue').click()
                    expect(page.get_by_role('heading', name='Your income sources')).to_be_visible()
                    page.get_by_label('Amount', exact=True).fill('1000')
                    page.get_by_role('button', name='Save & Continue').click()
                    expect(page.get_by_role('heading', name='Where do you keep money?')).to_be_visible()
                    page.get_by_label('Account name', exact=True).fill('Flow Cash')
                    page.get_by_label('Opening balance', exact=True).fill('100')
                    page.get_by_role('button', name='Save & Continue').click()
                    expect(page.get_by_role('heading', name='Set monthly spending limits')).to_be_visible()
                    page.get_by_label('Food', exact=True).fill('100')
                    page.get_by_role('button', name='Save & Continue').click()
                    expect(page.get_by_role('heading', name='Make a savings goal')).to_be_visible()
                    page.get_by_label('Goal name', exact=True).fill('Flow Emergency')
                    page.get_by_label('Target amount', exact=True).fill('200')
                    page.get_by_role('button', name='Open my dashboard').click()
                    expect(page).to_have_url(WEB + '/dashboard')
                    expect(page.get_by_role('heading', name='Budget Progress', exact=True)).to_be_visible()
                    print('PASS: browser registration and all five onboarding steps via /api', flush=True)

                    go('/dashboard/accounts')
                    page.get_by_role('button', name='Add account', exact=True).click()
                    dialog = page.get_by_role('dialog')
                    dialog.get_by_label('Account name', exact=True).fill('Flow Bank')
                    dialog.get_by_label('Account type', exact=True).select_option('bank')
                    submit(dialog, 'Create account')
                    expect(page.get_by_role('heading', name='Flow Bank', exact=True)).to_be_visible()

                    go('/dashboard/transactions')
                    for kind, amount, note in [('Income', '1000', 'Flow salary'), ('Expense', '40', 'Flow groceries')]:
                        page.get_by_role('button', name='Add transaction', exact=True).click()
                        dialog = page.get_by_role('dialog')
                        dialog.get_by_role('button', name=kind, exact=True).click()
                        dialog.get_by_label('Account', exact=True).select_option(label='Flow Cash · LKR')
                        dialog.get_by_label('Amount (LKR)', exact=True).fill(amount)
                        dialog.get_by_label('Note (optional)', exact=True).fill(note)
                        submit(dialog, 'Save transaction')
                        expect(page.get_by_role('cell', name=note, exact=False)).to_be_visible()
                    go('/dashboard/accounts')
                    page.get_by_role('button', name='Transfer money', exact=True).click()
                    dialog = page.get_by_role('dialog')
                    dialog.get_by_label('From account', exact=True).select_option(label='Flow Cash')
                    dialog.get_by_label('To account', exact=True).select_option(label='Flow Bank')
                    dialog.get_by_label('Transfer amount (LKR)', exact=True).fill('100')
                    submit(dialog, 'Transfer money')
                    accounts = {a['name']: a for a in data('/accounts')['items']}
                    assert Decimal(accounts['Flow Cash']['current_balance']) == 960
                    assert Decimal(accounts['Flow Bank']['current_balance']) == 100
                    print('PASS: accounts, income, expense and paired transfer persist through real API calls', flush=True)

                    go('/dashboard/goals')
                    page.get_by_role('button', name='Contribute', exact=False).click()
                    dialog = page.get_by_role('dialog')
                    dialog.get_by_label('Contribution amount (LKR)', exact=True).fill('25')
                    requests = []

                    def lost_response(route):
                        requests.append(route.request.post_data_json)
                        if len(requests) == 1:
                            result = route.fetch()
                            assert result.ok
                            route.fulfill(status=502, json={'detail': 'Synthetic lost response; retry the same contribution.'})
                        else:
                            route.continue_()

                    page.route('**/api/goals/*/contribute', lost_response)
                    dialog.get_by_role('button', name='Add contribution', exact=True).click()
                    expect(dialog.locator('.db-error')).to_contain_text('Synthetic lost response')
                    submit(dialog, 'Add contribution')
                    assert len(requests) == 2 and requests[0]['request_id'] == requests[1]['request_id']
                    assert Decimal(data('/goals')[0]['saved_amount']) == 25
                    page.unroute('**/api/goals/*/contribute', lost_response)
                    print('PASS: frontend contribution retry reuses its key and allocates once', flush=True)

                    go('/dashboard/reminders')
                    page.get_by_role('button', name='New reminder', exact=True).click()
                    dialog = page.get_by_role('dialog')
                    dialog.get_by_label('Name', exact=True).fill('Flow Rent')
                    dialog.get_by_label('Amount', exact=True).fill('50')
                    dialog.get_by_label('Account', exact=True).select_option(label='Flow Cash')
                    dialog.get_by_label('Repeat', exact=True).select_option('none')
                    submit(dialog, 'Save reminder')
                    expect(page.get_by_role('heading', name='Flow Rent', exact=True)).to_be_visible()
                    page.get_by_role('button', name='Mark paid', exact=True).click()
                    expect(page.get_by_role('heading', name='Flow Rent', exact=True)).not_to_be_visible()
                    go('/dashboard/budgets')
                    food = page.locator('.db-budget-grid article').filter(has=page.get_by_role('heading', name='Food', exact=True))
                    expect(food).to_contain_text('40')
                    summary = data('/dashboard?include_cash_flow=true')
                    assert Decimal(summary['total_balance']) == 1010
                    assert Decimal(summary['monthly_income']) == 1000
                    assert Decimal(summary['monthly_expenses']) == 90
                    assert Decimal(summary['total_savings_allocated']) == 25
                    assert Decimal(summary['safe_to_spend_estimate']) == 925
                    go('/dashboard/reports')
                    expect(page.locator('.cash-flow-table')).to_contain_text('Flow salary')
                    expect(page.locator('.cash-flow-table')).to_contain_text('Flow groceries')
                    expect(page.locator('.cash-flow-table')).to_contain_text('Flow Rent')
                    expect(page.locator('.cash-flow-table')).to_contain_text('1,010')
                    print('PASS: goal, budget, paid bill, dashboard and report totals reconcile', flush=True)

                    # Restart the API against the same temporary file to prove persistence.
                    stop(backend)
                    backend = start_backend()
                    ready(WEB + '/api/health')
                    page.reload()
                    expect(page.locator('.cash-flow-table')).to_contain_text('Flow salary')
                    assert Decimal(data('/dashboard')['total_balance']) == 1010
                    page.get_by_role('button', name='Sign out', exact=True).first.click()
                    expect(page).to_have_url(WEB + '/login')
                    page.get_by_label('Email Address', exact=True).fill('flow@example.com')
                    page.get_by_label('Password', exact=True).fill(PASSWORD)
                    page.locator('form button[type="submit"]').click()
                    expect(page).to_have_url(WEB + '/dashboard')
                    assert Decimal(data('/goals')[0]['saved_amount']) == 25
                    assert not unexpected, 'Frontend bypassed the /api proxy'
                    assert not errors, errors
                    print('PASS: database persists across backend restart, reload and sign-out/sign-in; no browser errors', flush=True)
                    browser.close()
            finally:
                stop(frontend)
                stop(backend)


if __name__ == '__main__':
    serve() if '--serve' in sys.argv else run()
