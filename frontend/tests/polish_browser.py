"""UI-only checks using the existing API with an isolated temporary database.
Run from frontend: ../backend/.venv/bin/python tests/ui_browser.py
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
API = 'http://127.0.0.1:8766'
WEB = 'http://127.0.0.1:5175'
ARTIFACTS = ROOT / 'frontend' / 'ui-artifacts'


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    ARTIFACTS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='maxbud-ui-') as scratch:
        env = os.environ | {'PYTHONPATH': str(ROOT / 'backend'), 'FRONTEND_ORIGIN': WEB,
                            'FAMILY_BROWSER_DB': f'sqlite:///{scratch}/test.db', 'ENVIRONMENT': 'test', 'RATE_LIMIT_ENABLED': 'false', 'GROQ_API_KEY': '', 'BROWSER_API_PORT': '8766', 'BROWSER_ADMIN': 'true'}
        with open(f'{scratch}/server.log', 'w+') as log:
            backend = subprocess.Popen([sys.executable, str(ROOT / 'backend/tests/family_browser.py'), '--serve'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
            frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5175', '--strictPort'], cwd=ROOT / 'frontend', env=env | {'VITE_API_URL': API}, stdout=log, stderr=log, start_new_session=True)
            try:
                with sync_playwright() as pw:
                    request = pw.request.new_context()
                    for address in [API + '/openapi.json', WEB]:
                        for _ in range(480):
                            try:
                                if request.get(address, timeout=1000).ok:
                                    break
                            except Exception:
                                pass
                            time.sleep(.25)
                        else:
                            log.seek(0)
                            raise RuntimeError(log.read()[-4000:])
                    browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                    page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
                    page_errors = []
                    page.on('pageerror', lambda error: page_errors.append(str(error)))
                    for width, columns in [(1440,3),(1024,3),(768,2),(360,1)]:
                        page.set_viewport_size({'width':width,'height':1000})
                        page.goto(WEB)
                        expect(page.locator('.showcase-card')).to_have_count(6)
                        grid = page.locator('.showcase-grid')
                        assert grid.evaluate('(el) => getComputedStyle(el).gridTemplateColumns.split(" ").length') == columns
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Landing overflow at {width}'
                    for visual in page.locator('.feature-art-frame .visual-area').all():
                        bounds=visual.bounding_box();frame=visual.locator('..').bounding_box()
                        assert bounds['y']>=frame['y']-1 and bounds['y']+bounds['height']<=frame['y']+frame['height']+1
                    page.goto(WEB+'/login')
                    expect(page.get_by_role('link',name='MaxBud home',exact=True)).to_be_visible()
                    brand=page.locator('.auth-brand').bounding_box();card=page.locator('.auth-card').bounding_box()
                    assert abs(brand['x']+brand['width']/2-card['x']-card['width']/2)<2
                    page.screenshot(path=str(ARTIFACTS/'polish-login-360.png'),full_page=True)
                    page.goto(WEB)
                    faq = page.locator('#faq button').first
                    initial = faq.get_attribute('aria-expanded')
                    faq.click()
                    expect(faq).to_have_attribute('aria-expanded', 'false' if initial == 'true' else 'true')
                    faq.click()
                    expect(faq).to_have_attribute('aria-expanded', initial)
                    page.screenshot(path=str(ARTIFACTS / 'landing-360.png'), full_page=True)
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.goto(WEB)
                    page.screenshot(path=str(ARTIFACTS / 'landing-desktop.png'), full_page=True)
                    auth = request.post(API + '/auth/login', data={'email':'browser@example.com','password':'SecurePassword1!'}).json()
                    headers={'Authorization':'Bearer '+auth['access_token']}
                    def post(path,body):
                        result=request.post(API+path,data=body,headers=headers)
                        assert result.ok,result.text()
                        return result.json()
                    cash=post('/accounts',{'name':'Report Cash','kind':'cash','opening_balance':'1000'})
                    bank=post('/accounts',{'name':'Report Bank','kind':'bank','opening_balance':'200'})
                    from datetime import date
                    month=date.today().strftime('%Y-%m')
                    post('/transactions',{'account_id':cash['id'],'kind':'income','category':'Salary','amount':'800','description':'Browser salary','txn_date':month+'-01'})
                    post('/transactions',{'account_id':cash['id'],'kind':'expense','category':'Food','amount':'50','description':'Browser groceries','txn_date':month+'-03'})
                    session = {'token':auth['access_token'], 'user':auth['user'], 'onboarding_completed':True}
                    page.add_init_script(f'sessionStorage.setItem("maxbud_auth", {json.dumps(json.dumps(session))});')
                    paths = ['', 'accounts', 'transactions', 'budgets', 'goals', 'reminders', 'reports', 'family', 'ai-scan', 'ai-advisor', 'upgrade', 'settings']
                    for width in [1440,1024,768,360]:
                        page.set_viewport_size({'width':width,'height':1000})
                        for path in paths:
                            page.goto(WEB + '/dashboard' + ('/' + path if path else ''))
                            expect(page.locator('main')).to_be_visible()
                            expect(page.locator('main h1')).to_be_visible()
                            page.wait_for_timeout(180)
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'{path or "overview"} overflow at {width}'
                        print(f'PASS: all 12 dashboard pages at {width}px', flush=True)
                    page.set_viewport_size({'width':1440,'height':1000})
                    page.goto(WEB + '/dashboard')
                    pig=page.locator('.ov-piggy').bounding_box();welcome=page.locator('.ov-welcome').bounding_box()
                    assert pig['y']>=welcome['y']-1
                    expect(page.locator('.ov-metrics .ov-metric').first).to_contain_text('Safe to Spend')
                    expect(page.get_by_role('heading',name='Budget Progress',exact=True)).to_be_visible()
                    expect(page.get_by_role('heading',name='Upcoming Bills',exact=True)).to_be_visible()
                    page.screenshot(path=str(ARTIFACTS / 'overview-desktop.png'), full_page=True)
                    page.get_by_role('button',name='Toggle navigation',exact=True).click()
                    expect(page.locator('.db-app')).to_have_class('db-app db-collapsed')
                    page.get_by_role('link',name='Subscription',exact=True).click()
                    expect(page.get_by_role('heading',name='Subscription',exact=True)).to_be_visible()
                    expect(page.get_by_text('Price not configured',exact=False).first).to_be_visible()
                    expect(page.get_by_text('3 calendar months for new registrations',exact=True)).to_be_visible()
                    expect(page.locator('.subscription-status')).to_contain_text('Free')
                    page.screenshot(path=str(ARTIFACTS / 'subscription-desktop.png'), full_page=True)
                    page.goto(WEB+'/dashboard/transactions')
                    summary=page.get_by_role('region',name='Current cash flow summary')
                    expect(summary).to_contain_text('LKR 1,950.00')
                    expect(summary).to_contain_text('LKR 750.00')
                    page.goto(WEB+'/dashboard/reports')
                    table=page.locator('.cash-flow-table')
                    expect(table).to_contain_text('Browser salary')
                    expect(table).to_contain_text('Browser groceries')
                    expect(table).to_contain_text('LKR 1,950.00')
                    page.get_by_label('Report month',exact=True).fill('2025-01')
                    expect(page.get_by_text('No account movements recorded for this month.',exact=False)).to_be_visible()
                    page.get_by_label('Report month',exact=True).fill(month)
                    expect(table).to_be_visible()
                    page.screenshot(path=str(ARTIFACTS/'polish-report-1440.png'),full_page=True)
                    page.goto(WEB + '/dashboard/ai-advisor')
                    expect(page.get_by_text('Make room for a clearer plan',exact=True)).to_be_visible()
                    page.get_by_role('button',name='How can I improve my monthly budget?',exact=False).click()
                    expect(page.get_by_label('Your question',exact=True)).to_have_value('How can I improve my monthly budget?')
                    page.screenshot(path=str(ARTIFACTS / 'advisor-desktop.png'), full_page=True)
                    # Existing backend has no provider configured: show its real error, never a fake answer.
                    page.get_by_role('button',name='Send question',exact=True).click()
                    expect(page.get_by_role('alert')).to_contain_text('AI is not available yet')
                    expect(page.get_by_role('button',name='Send question',exact=True)).to_be_enabled()
                    def advisor_history(route):
                        if route.request.method=='GET':
                            route.fulfill(json=[{'id':1,'question':'Help me budget','answer':'{"answer":"## Your plan\\n\\n- Keep **LKR 5000** available.\\n- சேமிப்பு திட்டம்"}'}])
                        else:route.continue_()
                    page.route('**/ai/advisor',advisor_history)
                    page.reload()
                    expect(page.locator('.advisor-prose h3')).to_have_text('Your plan')
                    expect(page.locator('.advisor-prose li')).to_have_count(2)
                    expect(page.locator('.advisor-prose')).to_contain_text('LKR 5,000.00')
                    assert page.locator('.advisor-prose img').count()==0
                    page.set_viewport_size({'width':360,'height':800})
                    page.reload()
                    page.get_by_role('button',name='Toggle navigation',exact=True).click()
                    expect(page.locator('.db-sidebar')).to_have_class('db-sidebar open')
                    expect(page.locator('.db-sidebar')).to_have_attribute('aria-modal','true')
                    page.get_by_role('link',name='Subscription',exact=True).click()
                    expect(page.get_by_role('heading',name='Subscription',exact=True)).to_be_visible()
                    expect(page.locator('.db-sidebar')).not_to_have_class('db-sidebar open')
                    page.goto(WEB + '/dashboard/ai-advisor')
                    page.screenshot(path=str(ARTIFACTS / 'advisor-360.png'), full_page=True)
                    page.get_by_role('button',name='Toggle navigation',exact=True).click()
                    expect(page.locator('.db-sidebar')).to_have_class('db-sidebar open')
                    page.set_viewport_size({'width':1280,'height':900})
                    expect(page.locator('.db-sidebar')).not_to_have_class('db-sidebar open')
                    assert page.evaluate('document.body.style.overflow') != 'hidden', 'Drawer kept desktop scroll locked'
                    page.goto(WEB + '/dashboard/admin')
                    expect(page.get_by_role('heading',name='Administration',exact=True)).to_be_visible()
                    for title in ['User Management','Subscriptions','Demo Billing Reports','AI Usage Monitoring','Support / Activity','Admin Settings','Dashboard']:
                        page.get_by_role('button',name=title,exact=True).click()
                        expect(page.get_by_role('alert')).to_have_count(0)
                        page.wait_for_timeout(180)
                    assert not page_errors, page_errors
                    print('PASS: landing grids/FAQ, navigation/collapse/mobile drawer, overview hierarchy, subscription data/prices, advisor suggestion/send/error, no page errors', flush=True)
                    browser.close()
            finally:
                for process in [frontend,backend]:
                    if process.poll() is None:
                        os.killpg(process.pid,signal.SIGTERM)
                for process in [frontend,backend]:
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL)


if __name__ == '__main__':
    run()
