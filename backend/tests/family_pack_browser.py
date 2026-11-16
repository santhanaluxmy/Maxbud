"""Family Pack UI acceptance using temporary SQLite and clearly labeled demo checkout.
Run from backend: .venv/bin/python tests/family_pack_browser.py
"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from core_flow_browser import ROOT, PASSWORD, stop

API = 'http://127.0.0.1:8793'
WEB = 'http://127.0.0.1:5183'


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=30000)
    with tempfile.TemporaryDirectory(prefix='maxbud-core-flow-') as scratch:
        env = os.environ | {
            'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1',
            'CORE_FLOW_DIRECTORY': scratch, 'CORE_FLOW_API_PORT': '8793',
            'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false', 'DEMO_PAYMENTS_ENABLED': 'true',
            'GROQ_API_KEY': '', 'GROQ_CHAT_MODEL': '', 'GROQ_VISION_MODEL': '',
            'VITE_API_URL': '', 'VITE_BACKEND_URL': '', 'VITE_GOOGLE_CLIENT_ID': '', 'API_PROXY_TARGET': API,
        }
        backend = frontend = None
        with open(Path(scratch) / 'services.log', 'w+') as log:
            try:
                backend = subprocess.Popen([sys.executable, str(ROOT / 'backend/tests/core_flow_browser.py'), '--serve'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
                frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5183', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, start_new_session=True)
                with sync_playwright() as pw:
                    request = pw.request.new_context()
                    for _ in range(200):
                        try:
                            if request.get(WEB + '/api/health', timeout=1000).ok:
                                break
                        except Exception:
                            pass
                        if backend.poll() is not None or frontend.poll() is not None:
                            raise RuntimeError('Family test service stopped')
                        time.sleep(.2)
                    else:
                        raise RuntimeError('Family test services did not become ready')

                    def register(name):
                        response = request.post(WEB + '/api/auth/register', data={'full_name': name, 'email': name.lower() + '@example.com', 'password': PASSWORD, 'confirm_password': PASSWORD})
                        assert response.status == 201
                        return response.json()

                    owner, member = register('Sponsor'), register('Member')
                    with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                        db.execute('UPDATE users SET onboarding_completed=1')
                    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                    errors = []

                    def session(person):
                        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                        saved = {'token': person['access_token'], 'user': person['user'], 'onboarding_completed': True}
                        context.add_init_script('sessionStorage.setItem("maxbud_auth", ' + json.dumps(json.dumps(saved)) + ');')
                        page = context.new_page()
                        page.set_default_timeout(30000)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        return context, page

                    owner_context, page = session(owner)
                    member_context, member_page = session(member)

                    def api(path, person, body=None):
                        response = request.get(WEB + '/api' + path, headers={'Authorization': 'Bearer ' + person['access_token']}) if body is None else request.post(WEB + '/api' + path, headers={'Authorization': 'Bearer ' + person['access_token']}, data=body)
                        assert response.ok, f'{path}: {response.status}'
                        return response.json()

                    def purchase(plan_name):
                        page.goto(WEB + '/dashboard/upgrade')
                        card = page.locator('.subscription-plan').filter(has=page.get_by_role('heading', name=plan_name, exact=True))
                        card.get_by_role('button', name='Open demo checkout', exact=True).click()
                        dialog = page.get_by_role('dialog')
                        expect(dialog).to_contain_text('No real money will be charged')
                        dialog.get_by_role('button', name='Simulate Successful Payment', exact=True).click()
                        expect(dialog).not_to_be_visible()

                    page.goto(WEB + '/dashboard/family')
                    expect(page.get_by_role('link', name='View Family Pack', exact=True)).to_be_visible()
                    expect(page.get_by_role('button', name='Create household', exact=True)).to_have_count(0)
                    purchase('Premium Individual')
                    page.goto(WEB + '/dashboard/family')
                    expect(page.get_by_role('button', name='Create household', exact=True)).to_have_count(0)
                    purchase('Family Pack')
                    page.goto(WEB + '/dashboard/family')
                    page.get_by_label('Household name', exact=True).fill('Our Shared Household')
                    page.get_by_role('button', name='Create household', exact=True).click()
                    expect(page.get_by_role('heading', name='Our Shared Household', exact=True)).to_be_visible()
                    print('PASS: Free and Premium do not unlock household creation; Family Pack demo checkout does', flush=True)

                    page.get_by_label('Invited email', exact=True).fill('member@example.com')
                    page.get_by_role('button', name='Create secure invitation', exact=True).click()
                    link = page.get_by_label('Invitation link', exact=True)
                    expect(link).to_be_visible()
                    member_page.goto(link.input_value())
                    member_page.get_by_role('button', name='Accept invitation', exact=True).click()
                    expect(member_page.get_by_role('heading', name='Our Shared Household', exact=True)).to_be_visible()
                    page.reload()
                    expect(page.get_by_role('cell', name='member@example.com', exact=True).first).to_be_visible()
                    print('PASS: secure owner invitation and member acceptance through separate browser sessions', flush=True)

                    page.get_by_role('button', name='New shared wallet', exact=True).click()
                    dialog = page.get_by_role('dialog')
                    dialog.get_by_label('Name', exact=True).fill('Common Wallet')
                    dialog.get_by_role('button', name='Save shared record', exact=True).click()
                    expect(dialog).not_to_be_visible()
                    page.get_by_role('button', name='New shared budget', exact=True).click()
                    dialog = page.get_by_role('dialog')
                    dialog.get_by_label('Category', exact=True).fill('Food')
                    dialog.get_by_label('Monthly limit (LKR)', exact=True).fill('500')
                    dialog.get_by_role('button', name='Save shared record', exact=True).click()
                    expect(dialog).not_to_be_visible()

                    member_page.reload()
                    member_page.get_by_role('button', name='Add shared income', exact=True).click()
                    dialog = member_page.get_by_role('dialog')
                    dialog.get_by_label('Category', exact=True).fill('Common earnings')
                    dialog.get_by_label('Amount (LKR)', exact=True).fill('1000')
                    dialog.get_by_label('Income wallet', exact=True).select_option(label='Common Wallet')
                    dialog.get_by_label('Shared note', exact=True).fill('Common rental income')
                    dialog.get_by_role('button', name='Save shared record', exact=True).click()
                    expect(dialog).not_to_be_visible()
                    expect(member_page.get_by_role('cell', name='Common rental income', exact=True)).to_be_visible()
                    member_page.get_by_role('button', name='Add shared expense', exact=True).click()
                    dialog = member_page.get_by_role('dialog')
                    dialog.get_by_label('Amount (LKR)', exact=True).fill('200')
                    dialog.get_by_label('Category', exact=True).fill('Food')
                    dialog.get_by_label('Payment account', exact=True).select_option(label='Shared: Common Wallet')
                    dialog.get_by_label('Shared note', exact=True).fill('Shared groceries')
                    dialog.get_by_role('button', name='Save shared record', exact=True).click()
                    expect(dialog).not_to_be_visible()
                    expect(member_page.get_by_role('cell', name='Shared groceries', exact=True)).to_be_visible()
                    summary = api('/dashboard?scope=family', member)
                    assert tuple(Decimal(summary[k]) for k in ['monthly_income', 'monthly_expenses', 'total_balance']) == (1000, 200, 800)
                    assert Decimal(summary['budgets'][0]['spent']) == 200
                    assert Decimal(api('/dashboard', member)['monthly_income']) == 0
                    print('PASS: member shared income/expense, wallet balance and owner-created budget reconcile without private income', flush=True)

                    private = api('/accounts', member, {'name': 'PRIVATE MEMBER WALLET', 'kind': 'cash', 'opening_balance': '500'})
                    api('/transactions', member, {'account_id': private['id'], 'kind': 'income', 'category': 'Salary', 'amount': '3000', 'description': 'PRIVATE SALARY NOTE'})
                    page.reload()
                    expect(page.locator('main')).not_to_contain_text('PRIVATE SALARY NOTE')
                    expect(page.locator('main')).not_to_contain_text('PRIVATE MEMBER WALLET')
                    page.goto(WEB + '/dashboard?scope=family')
                    expect(page.locator('.ov-metrics')).to_contain_text('Shared Income')
                    expect(page.locator('.ov-metrics')).to_contain_text('1,000')
                    assert Decimal(api('/dashboard?scope=family', owner)['monthly_income']) == 1000
                    assert Decimal(api('/dashboard', member)['monthly_income']) == 3000
                    print('PASS: private salary/account isolation and shared dashboard income display', flush=True)

                    page.goto(WEB + '/dashboard/family')
                    page.route('**/api/family/members/*/permissions', lambda route: route.fulfill(status=503, json={'detail': 'Synthetic permission save failure'}))
                    page.get_by_label('Allow shared editing for Member', exact=True).click()
                    expect(page.get_by_role('alert')).to_contain_text('Synthetic permission save failure')
                    expect(page.get_by_label('Allow shared editing for Member', exact=True)).to_be_checked()
                    page.unroute('**/api/family/members/*/permissions')
                    with page.expect_response(lambda response: '/permissions' in response.url and response.request.method == 'PATCH') as saved_permission:
                        page.get_by_label('Allow shared editing for Member', exact=True).uncheck()
                    assert saved_permission.value.status == 200
                    expect(page.get_by_label('Allow shared editing for Member', exact=True)).not_to_be_checked()
                    member_page.reload()
                    expect(member_page.get_by_role('button', name='Add shared income', exact=True)).to_be_disabled()
                    denied = request.post(WEB + '/api/family/income', headers={'Authorization': 'Bearer ' + member['access_token']}, data={'account_id': api('/family/wallets', member)[0]['id'], 'category': 'Blocked', 'amount': '1', 'request_id': 'revoked'})
                    assert denied.status == 403
                    with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                        db.execute('UPDATE subscriptions SET plan=? WHERE user_id=?', ('premium_individual', owner['user']['id']))
                    page.reload()
                    expect(page.get_by_role('heading', name='Family Pack required', exact=True)).to_be_visible()
                    expect(page.get_by_role('cell', name='Common rental income', exact=True)).to_be_visible()
                    expect(page.get_by_role('button', name='Add shared income', exact=True)).to_be_disabled()
                    assert Decimal(api('/accounts/' + str(private['id']), member)['current_balance']) == 3500
                    assert not errors, errors
                    print('PASS: permission revocation and downgrade disable editing, preserve shared history and personal accounts; no browser errors', flush=True)
                    owner_context.close(); member_context.close(); browser.close()
            finally:
                stop(frontend); stop(backend)
                log.seek(0)
                Path('/tmp/maxbud-family-services-last.log').write_text(log.read())


if __name__ == '__main__':
    run()
