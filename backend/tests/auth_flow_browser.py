"""Login/register browser checks against the disposable core-flow server.
Run from backend: .venv/bin/python tests/auth_flow_browser.py
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

API = 'http://127.0.0.1:8791'
WEB = 'http://127.0.0.1:5181'


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=45000)
    with tempfile.TemporaryDirectory(prefix='maxbud-core-flow-') as scratch:
        env = os.environ | {
            'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1',
            'CORE_FLOW_DIRECTORY': scratch, 'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false',
            'CORE_FLOW_API_PORT': '8791',
            'CORE_FLOW_LOG_LEVEL': 'info',
            'GROQ_API_KEY': '', 'GROQ_CHAT_MODEL': '', 'GROQ_VISION_MODEL': '',
            'VITE_API_URL': '', 'VITE_BACKEND_URL': '', 'VITE_GOOGLE_CLIENT_ID': '',
            'API_PROXY_TARGET': API,
        }
        backend = frontend = None
        with open(Path(scratch) / 'services.log', 'w+') as log:
            try:
                backend = subprocess.Popen([sys.executable, str(ROOT / 'backend/tests/core_flow_browser.py'), '--serve'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
                frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5181', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, start_new_session=True)
                with sync_playwright() as pw:
                    request = pw.request.new_context()
                    for _ in range(160):
                        try:
                            if request.get(WEB + '/api/health', timeout=1000).ok:
                                break
                        except Exception:
                            pass
                        if backend.poll() is not None or frontend.poll() is not None:
                            log.seek(0)
                            raise RuntimeError('Authentication test services stopped unexpectedly: ' + log.read()[-2000:])
                        time.sleep(.2)
                    else:
                        log.seek(0)
                        raise RuntimeError('Authentication test services did not become ready: ' + log.read()[-2000:])
                    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                    context = browser.new_context(viewport={'width': 1280, 'height': 900})
                    page = context.new_page()
                    page.set_default_timeout(45000)
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('response', lambda response: print(f'AUTH HTTP {response.status}: {response.url.split("/api", 1)[-1]}', flush=True) if '/api/auth/' in response.url else None)

                    def storage():
                        return page.evaluate('({session: sessionStorage.getItem("maxbud_auth"), remembered: localStorage.getItem("maxbud_auth")})')

                    def login(remember=False, password=PASSWORD):
                        page.goto(WEB + '/login')
                        page.get_by_label('Email Address', exact=True).fill(' AUTH@EXAMPLE.COM ')
                        page.get_by_label('Password', exact=True).fill(password)
                        page.get_by_role('checkbox').set_checked(remember)
                        page.get_by_role('button', name='Sign In', exact=False).click()

                    page.goto(WEB + '/dashboard/accounts')
                    expect(page).to_have_url(WEB + '/login')
                    page.get_by_role('button', name='Sign In', exact=False).click()
                    expect(page.get_by_role('alert')).to_contain_text('email')
                    print('PASS: signed-out route protection and empty login validation', flush=True)

                    page.goto(WEB + '/register')
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page.get_by_role('alert')).to_contain_text('Full name')
                    page.locator('input[name="name"]').fill('Auth Tester')
                    page.locator('input[name="email"]').fill('bad-email')
                    page.locator('input[name="password"]').fill(PASSWORD)
                    page.locator('input[name="confirmPassword"]').fill(PASSWORD)
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page.get_by_role('alert')).to_contain_text('valid email')
                    page.locator('input[name="email"]').fill(' AUTH@EXAMPLE.COM ')
                    page.locator('input[name="password"]').fill('weak')
                    page.locator('input[name="confirmPassword"]').fill('weak')
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page.get_by_role('alert')).to_contain_text('Password')
                    page.locator('input[name="password"]').fill(PASSWORD)
                    page.locator('input[name="confirmPassword"]').fill('DifferentPassword1!')
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page.get_by_role('alert')).to_contain_text('Passwords do not match')
                    page.locator('input[name="confirmPassword"]').fill(PASSWORD)
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page).to_have_url(WEB + '/onboarding')
                    assert storage()['session'] and storage()['remembered'] is None
                    page.reload()
                    expect(page.get_by_role('heading', name='Tell us about yourself')).to_be_visible()
                    print('PASS: registration validation, successful account creation, session-only storage and onboarding redirect/reload', flush=True)

                    page.goto(WEB + '/register')
                    for name, value in [('name', 'Replacement Name'), ('email', 'auth@example.com'), ('password', PASSWORD), ('confirmPassword', PASSWORD)]:
                        page.locator(f'input[name="{name}"]').fill(value)
                    page.get_by_role('button', name='Create Account', exact=False).click()
                    expect(page.get_by_role('alert')).to_contain_text('Email already registered')
                    login(password='WrongPassword1!')
                    expect(page.get_by_role('alert')).to_contain_text('Invalid email or password')
                    assert storage() == {'session': None, 'remembered': None}
                    expect(page.get_by_role('button', name='Sign In', exact=False)).to_be_enabled()
                    login(remember=True)
                    expect(page).to_have_url(WEB + '/onboarding')
                    assert storage()['remembered'] and storage()['session'] is None
                    tab = context.new_page()
                    tab.goto(WEB + '/dashboard')
                    expect(tab).to_have_url(WEB + '/onboarding')
                    tab.close()
                    print('PASS: duplicate email, wrong-password errors, remember-me storage/new tab and incomplete-user redirect', flush=True)

                    page.route('**/api/auth/login', lambda route: route.abort())
                    login()
                    expect(page.get_by_role('alert')).to_contain_text('Cannot connect to MaxBud')
                    expect(page.get_by_role('button', name='Sign In', exact=False)).to_be_enabled()
                    page.unroute('**/api/auth/login')
                    login()
                    expect(page).to_have_url(WEB + '/onboarding')
                    assert storage()['session'] and storage()['remembered'] is None
                    saved = json.loads(storage()['session'])
                    # Fixture-only state change to test login destinations independently
                    # of onboarding forms, already exercised in core_flow_browser.py.
                    with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                        db.execute('UPDATE users SET onboarding_completed=1 WHERE email=?', ('auth@example.com',))
                    login()
                    expect(page).to_have_url(WEB + '/dashboard')
                    expect(page.get_by_role('heading', name='Budget Progress', exact=True)).to_be_visible()
                    page.get_by_role('button', name='Sign out', exact=True).first.click()
                    expect(page).to_have_url(WEB + '/login')
                    assert storage() == {'session': None, 'remembered': None}
                    print('PASS: network failure/retry, session-only login, completed-user dashboard and logout', flush=True)

                    with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                        db.execute('UPDATE users SET role=? WHERE email=?', ('admin', 'auth@example.com'))
                    login()
                    expect(page).to_have_url(WEB + '/dashboard/admin')
                    expect(page.get_by_role('heading', name='Administration', exact=True)).to_be_visible()
                    with sqlite3.connect(Path(scratch) / 'flow.db') as db:
                        db.execute('UPDATE users SET is_active=0 WHERE email=?', ('auth@example.com',))
                    login()
                    expect(page.get_by_role('alert')).to_contain_text('Account disabled')
                    assert storage() == {'session': None, 'remembered': None}
                    print('PASS: admin login destination and suspended-account denial', flush=True)

                    expired = saved | {'onboarding_completed': True}
                    expired['token'] = 'header.eyJleHAiOjF9.signature'
                    page.evaluate('value => localStorage.setItem("maxbud_auth", JSON.stringify(value))', expired)
                    page.goto(WEB + '/dashboard/accounts')
                    expect(page).to_have_url(WEB + '/login')
                    assert storage() == {'session': None, 'remembered': None}
                    assert not errors, errors
                    print('PASS: expired-session cleanup and redirect; no browser JavaScript errors', flush=True)
                    browser.close()
            finally:
                stop(frontend)
                stop(backend)
                # Synthetic test-service diagnostics only; no credentials or
                # authentication response bodies are logged by this harness.
                log.seek(0)
                Path('/tmp/maxbud-auth-services-last.log').write_text(log.read())


if __name__ == '__main__':
    run()
