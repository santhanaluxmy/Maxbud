"""Isolated local TEST ACCESS acceptance; no payment or configured MySQL writes."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
API = 'http://127.0.0.1:8795'
WEB = 'http://127.0.0.1:5185'
PASSWORD = 'IsolatedBrowserTest1!'


def serve(root):
    from app.core.config import get_settings
    from scripts.local_family_test import Sandbox
    import uvicorn
    root = Path(root).resolve()
    if root.parent.parent != Path(tempfile.gettempdir()).resolve() or not root.parent.name.startswith('maxbud-local-browser-'):
        raise RuntimeError('Browser harness only accepts its temporary sandbox')
    app = Sandbox(root, get_settings()).prepare_app()
    uvicorn.run(app, host='127.0.0.1', port=8795, log_level='warning')


def run():
    import jwt
    from playwright.sync_api import sync_playwright, expect
    from app.core.config import get_settings
    from scripts.local_family_test import Sandbox, OWNER_EMAIL, MEMBER_EMAILS
    from core_flow_browser import stop
    expect.set_options(timeout=30000)
    with tempfile.TemporaryDirectory(prefix='maxbud-local-browser-') as directory:
        normal_signing_key = get_settings().JWT_SECRET
        sandbox = Sandbox(Path(directory) / '.local-family-test', get_settings())
        sandbox.initialize(PASSWORD)
        sandbox.change('grant', OWNER_EMAIL, OWNER_EMAIL, PASSWORD, hours=24)
        env = os.environ | {'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1',
                            'ENVIRONMENT': 'test', 'DEMO_PAYMENTS_ENABLED': 'false', 'RATE_LIMIT_ENABLED': 'false',
                            'VITE_API_URL': '', 'VITE_BACKEND_URL': '', 'VITE_GOOGLE_CLIENT_ID': '',
                            'API_PROXY_TARGET': API}
        backend = frontend = None
        with open(Path(directory) / 'services.log', 'w+') as log:
            try:
                backend = subprocess.Popen([sys.executable, __file__, '--serve', str(sandbox.root)], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
                frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5185', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, start_new_session=True)
                with sync_playwright() as pw:
                    request = pw.request.new_context()
                    for _ in range(240):
                        try:
                            if request.get(WEB + '/api/health', timeout=1000).ok:
                                break
                        except Exception:
                            pass
                        if backend.poll() is not None or frontend.poll() is not None:
                            raise RuntimeError('Local test server stopped')
                        time.sleep(.2)
                    else:
                        raise RuntimeError('Local test server readiness timeout')

                    people = []
                    for index, email in enumerate([OWNER_EMAIL, *MEMBER_EMAILS]):
                        response = request.post(WEB + '/api/auth/login', data={'email': email, 'password': PASSWORD})
                        assert response.ok
                        person = response.json()
                        headers = {'Authorization': 'Bearer ' + person['access_token']}
                        if index == 0:
                            try:
                                jwt.decode(person['access_token'], normal_signing_key, algorithms=['HS256'])
                            except jwt.InvalidSignatureError:
                                pass
                            else:
                                raise AssertionError('Sandbox must use its own signing key')
                        steps = [('about-you', {'full_name': 'Local Test Owner' if index == 0 else f'Local Roommate {index}', 'currency': 'LKR'}),
                                 ('income', {'sources': [{'name': 'Planned salary', 'amount': '100000'}]}),
                                 ('accounts', {'accounts': [{'name': 'Private cash', 'kind': 'cash', 'opening_balance': '50000'}]}),
                                 ('budgets', {'budgets': [{'category': 'Food', 'monthly_limit': '20000'}]}),
                                 ('goals', {'goals': []})]
                        for step, body in steps:
                            saved = request.post(WEB + '/api/onboarding/' + step, headers=headers, data=body)
                            assert saved.ok, (step, saved.status)
                        person = request.post(WEB + '/api/auth/login', data={'email': email, 'password': PASSWORD}).json()
                        people.append(person)
                    print('PASS: five synthetic users onboard through the real API; sandbox JWT cannot authenticate against the normal signing key', flush=True)
                    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'], timeout=60000)
                    print('PASS: isolated browser launched', flush=True)
                    contexts = []
                    errors = []
                    def page_for(person):
                        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                        contexts.append(context)
                        context.add_init_script('sessionStorage.setItem("maxbud_auth", ' + json.dumps(json.dumps({'token': person['access_token'], 'user': person['user'], 'onboarding_completed': person['onboarding_completed']})) + ');')
                        page = context.new_page()
                        page.set_default_timeout(30000)
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        return page
                    owner = page_for(people[0])
                    owner.goto(WEB + '/dashboard/family', wait_until='domcontentloaded')
                    expect(owner.get_by_role('note')).to_contain_text('TEST ACCESS')
                    owner.get_by_label('Household name', exact=True).fill('Unpaid Local Household')
                    owner.get_by_role('button', name='Create household', exact=True).click()
                    expect(owner.get_by_role('heading', name='Unpaid Local Household', exact=True)).to_be_visible()
                    print('PASS: owner creates household with TEST ACCESS label', flush=True)
                    owner.goto(WEB + '/dashboard/family/members', wait_until='domcontentloaded')
                    member_pages = []
                    for email, person in zip(MEMBER_EMAILS, people[1:]):
                        owner.get_by_label('Invited email', exact=True).fill(email)
                        with owner.expect_response(lambda response: response.url.endswith('/family/invitations') and response.request.method == 'POST') as invitation:
                            owner.get_by_role('button', name='Create secure invitation', exact=True).click()
                        expect(owner.get_by_label('Invitation link', exact=True)).to_have_value(re.compile(re.escape(invitation.value.json()['token'])))
                        link = owner.get_by_label('Invitation link', exact=True).input_value()
                        member = page_for(person)
                        member.goto(link, wait_until='domcontentloaded')
                        member.get_by_role('button', name='Accept invitation', exact=True).click()
                        expect(member.get_by_role('heading', name='Unpaid Local Household', exact=True)).to_be_visible()
                        expect(member.get_by_role('note')).to_contain_text('TEST ACCESS')
                        member_pages.append(member)
                    owner.reload(wait_until='domcontentloaded')
                    expect(owner.get_by_role('button', name='Create secure invitation', exact=True)).to_be_disabled()
                    print('PASS: owner invites all four, each accepts and sees TEST ACCESS; sixth seat is unavailable', flush=True)
                    headers = {'Authorization': 'Bearer ' + people[0]['access_token']}
                    state = request.get(WEB + '/api/subscriptions', headers=headers).json()
                    assert state['test_access'] and not state['catalog']['demo_enabled']
                    wallet_response = request.post(WEB + '/api/family/wallets', headers=headers, data={'name': 'Local shared wallet'})
                    assert wallet_response.status == 201
                    wallet = wallet_response.json()['id']
                    member_headers = {'Authorization': 'Bearer ' + people[1]['access_token']}
                    body = {'account_id': wallet, 'category': 'Common', 'amount': '1000', 'request_id': 'local-income'}
                    assert request.post(WEB + '/api/family/income', headers=member_headers, data=body).status == 201
                    owner.goto(WEB + '/dashboard/family/income', wait_until='domcontentloaded')
                    owner.reload(wait_until='domcontentloaded')
                    expect(owner.get_by_role('cell', name='Common', exact=True)).to_be_visible()
                    sandbox.change('revoke', OWNER_EMAIL, OWNER_EMAIL, PASSWORD)
                    for person in people:
                        headers = {'Authorization': 'Bearer ' + person['access_token']}
                        denied = request.post(WEB + '/api/family/income', headers=headers, data=body | {'request_id': 'revoked'})
                        assert denied.status == 403
                    owner.reload(wait_until='domcontentloaded')
                    expect(owner.get_by_role('heading', name='Family Pack required', exact=True)).to_be_visible()
                    expect(owner.get_by_role('cell', name='Common', exact=True)).to_be_visible()
                    expect(owner.get_by_role('button', name='Add shared income', exact=True)).to_be_disabled()
                    assert not errors, errors
                    print('PASS: CLI-service revocation blocks existing tokens for all five users, preserves history, and locks shared controls; demo remains off', flush=True)
                    for context in contexts:
                        context.close()
                    browser.close()
            finally:
                stop(frontend); stop(backend)
                log.seek(0)
                Path('/tmp/maxbud-local-family-browser-services.log').write_text(log.read())


if __name__ == '__main__':
    serve(sys.argv[2]) if '--serve' in sys.argv else run()
