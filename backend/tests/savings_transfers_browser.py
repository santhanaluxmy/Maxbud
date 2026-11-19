"""Production React + real FastAPI savings flow; disposable SQLite only.

Run after frontend build: .venv/bin/python tests/savings_transfers_browser.py
No MySQL connections, external services, provider calls or persistent test data.
"""
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def run():
    with tempfile.TemporaryDirectory(prefix='maxbud-savings-browser-') as scratch:
        os.environ.update({
            'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false', 'JWT_SECRET': secrets.token_urlsafe(48),
            'DB_USER': 'isolated_unused', 'DB_PASSWORD': 'unused',
            'SMTP_HOST': '', 'SMTP_USERNAME': '', 'SMTP_PASSWORD': '', 'SMTP_FROM': '',
            'STRIPE_SECRET_KEY': '', 'STRIPE_WEBHOOK_SECRET': '', 'GROQ_API_KEY': '', 'OPENAI_API_KEY': '',
            'DEMO_PAYMENTS_ENABLED': 'false', 'RECEIPT_STORAGE_DIR': scratch,
        })
        from fastapi.testclient import TestClient
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from playwright.sync_api import sync_playwright, expect
        from app.main import app
        import app.main as main
        from app.database import Base, get_db
        from app.models.user import User

        engine = create_engine('sqlite:///' + str(Path(scratch) / 'isolated.db'), connect_args={'check_same_thread': False})
        main.engine = engine
        Base.metadata.create_all(engine)
        def sessions():
            with Session(engine, expire_on_commit=False, autoflush=False) as db:
                yield db
        app.dependency_overrides[get_db] = sessions
        client = TestClient(app)
        calls = []
        lock = threading.Lock()
        dist = ROOT / 'frontend' / 'dist'
        assert (dist / 'index.html').is_file(), 'Run npm run build first'

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def handle_request(self):
                try:
                    if self.path.startswith('/api/'):
                        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                        headers = {key: value for key, value in self.headers.items() if key.lower() not in {'host', 'connection', 'content-length'}}
                        with lock:
                            calls.append((self.command, self.path))
                            response = client.request(self.command, self.path[4:], content=body, headers=headers)
                        data = response.content
                        self.send_response(response.status_code)
                        self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                    else:
                        path = (dist / unquote(self.path.split('?')[0]).lstrip('/')).resolve()
                        if dist not in path.parents or not path.is_file():
                            path = dist / 'index.html'
                        data = path.read_bytes()
                        self.send_response(200)
                        self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request

        result = client.post('/auth/register', json={'full_name': 'Savings Tester', 'email': 'savings-browser@example.com',
            'password': 'IsolatedBrowser1!', 'confirm_password': 'IsolatedBrowser1!'}).json()
        headers = {'Authorization': 'Bearer ' + result['access_token']}
        with Session(engine) as db:
            db.get(User, result['user']['id']).onboarding_completed = True
            db.commit()
        def api(path, payload=None):
            response = client.get(path, headers=headers) if payload is None else client.post(path, headers=headers, json=payload)
            assert response.is_success, response.text
            return response.json()
        source = api('/accounts', {'name': 'Savings Bank', 'kind': 'bank', 'opening_balance': '500'})['id']
        api('/accounts', {'name': 'Wallet', 'kind': 'wallet', 'opening_balance': '100'})
        archived = api('/accounts', {'name': 'Archived cash', 'kind': 'cash', 'opening_balance': '999'})['id']
        client.post(f'/accounts/{archived}/archive', headers=headers, json={'archived': True})
        goal = api('/goals', {'name': 'Emergency fund', 'target_amount': '1000', 'saved_amount': '20'})['id']
        web = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        url = 'http://127.0.0.1:' + str(web.server_address[1])
        threading.Thread(target=web.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
                session = {'token': result['access_token'], 'user': result['user'], 'onboarding_completed': True, 'has_household': False}
                context.add_init_script('sessionStorage.setItem("maxbud_auth", ' + json.dumps(json.dumps(session)) + ')')
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                def open_modal():
                    page.goto(url + '/dashboard/goals')
                    page.get_by_role('button', name='Contribute', exact=False).click()
                    return page.get_by_role('dialog', name='Add to savings goal')
                def assert_balances(balance, saved):
                    assert Decimal(api(f'/accounts/{source}')['current_balance']) == balance
                    assert Decimal(api('/goals')[0]['saved_amount']) == saved
                    assert Decimal(api('/accounts')['total_balance']) == 1599
                    dashboard = api('/dashboard?include_cash_flow=true')
                    assert Decimal(dashboard['monthly_income']) == Decimal(dashboard['monthly_expenses']) == 0

                dialog = open_modal()
                selector = dialog.get_by_label('Transfer From Account')
                expect(selector.locator('option')).to_have_count(3)
                expect(selector).to_contain_text('500')
                assert 'Archived' not in selector.inner_text()
                dialog.get_by_label('Contribution amount', exact=False).fill('30')
                assert not selector.evaluate('(element) => element.checkValidity()')
                selector.select_option(str(source))
                with page.expect_response(lambda response: response.url.endswith('/contribute')) as response:
                    dialog.locator('form').evaluate('(form) => { form.requestSubmit(); form.requestSubmit(); }')
                assert response.value.status == 200
                expect(dialog).not_to_be_visible()
                assert sum(method == 'POST' and path.endswith('/contribute') for method, path in calls) == 1
                assert_balances(470, 50)
                print('PASS: required eligible source with balances; rapid duplicate submit posts once; assets and income/expense unchanged', flush=True)

                page.goto(url + '/dashboard/transactions')
                page.get_by_role('button', name='Transfers', exact=True).click()
                table = page.get_by_role('table', name='Savings transfers')
                expect(table).to_contain_text('Savings Bank')
                expect(table).to_contain_text('Emergency fund')
                page.get_by_label('Search transactions').fill('Emergency')
                expect(table.locator('tbody tr')).to_have_count(1)
                page.on('dialog', lambda popup: popup.accept())
                table.get_by_role('button', name='Reverse', exact=True).click()
                expect(table).to_contain_text('Reversed')
                expect(table.get_by_role('button', name='Reverse', exact=True)).to_have_count(0)
                assert_balances(500, 20)
                print('PASS: Transactions Transfers view, search and reversal; original and legacy amounts preserved', flush=True)

                dialog = open_modal()
                dialog.get_by_label('Transfer From Account').select_option(str(source))
                dialog.get_by_label('Contribution amount', exact=False).fill('25')
                requests = []
                def lose_response(route):
                    requests.append(route.request.post_data_json)
                    actual = route.fetch()
                    assert actual.status == 200
                    route.fulfill(status=503, content_type='application/json', body='{"detail":"Response lost; retry safely"}')
                page.route('**/api/goals/*/contribute', lose_response)
                dialog.get_by_role('button', name='Add contribution', exact=True).click()
                expect(dialog).to_contain_text('Response lost')
                page.unroute('**/api/goals/*/contribute', lose_response)
                with page.expect_request('**/api/goals/*/contribute') as retry:
                    dialog.get_by_role('button', name='Add contribution', exact=True).click()
                expect(dialog).not_to_be_visible()
                assert requests[0]['request_id'] == retry.value.post_data_json['request_id']
                assert_balances(475, 45)
                assert len(api('/goals/transfers')) == 2
                print('PASS: lost response retry reuses request key without a duplicate debit', flush=True)

                page.set_viewport_size({'width': 375, 'height': 812})
                dialog = open_modal()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                dialog.get_by_role('button', name='Close', exact=True).click()
                page.goto(url + '/dashboard/transactions')
                page.get_by_role('button', name='Transfers', exact=True).click()
                expect(page.get_by_role('table', name='Savings transfers').locator('tbody tr')).to_have_count(2)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                assert not errors, errors
                print('PASS: mobile goals modal/history, no page overflow or JavaScript errors', flush=True)
                browser.close()
        finally:
            web.shutdown()
            web.server_close()
            client.close()
            app.dependency_overrides.clear()
            engine.dispose()


if __name__ == '__main__':
    run()
