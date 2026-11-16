"""Admin/card browser regression: temporary SQLite only, no real credentials/data."""
import json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
API='http://127.0.0.1:8768';WEB='http://127.0.0.1:5177'


def run():
    from playwright.sync_api import sync_playwright,expect
    expect.set_options(timeout=20000)
    artifacts=ROOT/'frontend/ui-artifacts';artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='maxbud-admin-browser-') as scratch:
        env=os.environ|{'PYTHONPATH':str(ROOT/'backend'),'ENVIRONMENT':'test','FRONTEND_ORIGIN':WEB,'FAMILY_BROWSER_DB':f'sqlite:///{scratch}/test.db','BROWSER_API_PORT':'8768','BROWSER_ADMIN':'true','RATE_LIMIT_ENABLED':'false','GROQ_API_KEY':''}
        with open(scratch+'/server.log','w+') as log:
            processes=[subprocess.Popen([sys.executable,str(ROOT/'backend/tests/family_browser.py'),'--serve'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log,start_new_session=True),subprocess.Popen(['npm','run','dev','--','--host','127.0.0.1','--port','5177','--strictPort'],cwd=ROOT/'frontend',env=env|{'VITE_API_URL':API},stdout=log,stderr=log,start_new_session=True)]
            try:
                with sync_playwright() as pw:
                    request=pw.request.new_context()
                    for url in [API+'/openapi.json',WEB]:
                        deadline=time.monotonic()+180
                        while time.monotonic()<deadline:
                            try:
                                if request.get(url,timeout=1000).ok:break
                            except Exception:pass
                            time.sleep(.25)
                        else:
                            log.seek(0);raise RuntimeError('Temporary server failed to start: '+log.read()[-2500:])
                    browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
                    page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    for width in [360,768,1024,1440]:
                        page.set_viewport_size({'width':width,'height':1000});page.goto(WEB)
                        expect(page.locator('.showcase-card')).to_have_count(6)
                        colors=page.locator('.showcase-card').evaluate_all('(cards)=>cards.map(c=>getComputedStyle(c).backgroundColor)')
                        assert colors[2]==colors[5]=='rgb(246, 231, 181)',colors
                        assert colors[0]==colors[4] and colors[1]==colors[3]
                        for index in [2,5]:
                            card=page.locator('.showcase-card').nth(index)
                            assert card.locator('.feature-art-frame').evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgba(0, 0, 0, 0)'
                        assert page.locator('#features').evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(238, 234, 215)'
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(artifacts/'admin-cards-desktop.png'),full_page=True)
                    normal=request.post(API+'/auth/register',data={'full_name':'Admin Target','email':'target@example.com','password':'FixturePassword1!','confirm_password':'FixturePassword1!'}).json()
                    target=normal['user']['id']
                    # Fixture-only admin seeded by the isolated server. No real credentials.
                    page.goto(WEB+'/login');page.get_by_role('button',name='Sign In',exact=False).click()
                    expect(page.get_by_text('Please enter your email address.',exact=True)).to_be_visible()
                    page.get_by_placeholder('you@example.com',exact=True).fill('browser@example.com')
                    page.get_by_placeholder('Enter your password',exact=True).fill('incorrect')
                    page.get_by_role('button',name='Sign In',exact=False).click()
                    expect(page.get_by_text('Invalid email or password',exact=False)).to_be_visible()
                    page.get_by_placeholder('Enter your password',exact=True).fill('SecurePassword1!')
                    page.get_by_role('button',name='Sign In',exact=False).click()
                    expect(page).to_have_url(WEB+'/dashboard/admin')
                    expect(page.get_by_role('heading',name='Administration',exact=True)).to_be_visible()
                    expect(page.get_by_text('Total users',exact=True)).to_be_visible()
                    page.get_by_role('button',name='User Management',exact=True).click()
                    page.get_by_label('Search users',exact=True).fill('target@example.com')
                    page.get_by_role('button',name='Search',exact=True).click()
                    expect(page.get_by_role('cell',name='target@example.com',exact=True)).to_be_visible()
                    page.once('dialog',lambda dialog:dialog.accept())
                    page.get_by_role('button',name='Suspend',exact=True).click()
                    expect(page.get_by_role('button',name='Reactivate',exact=True)).to_be_visible()
                    page.get_by_label('User status filter',exact=True).select_option('active')
                    expect(page.get_by_text('No users match these filters.',exact=True)).to_be_visible()
                    page.get_by_label('User status filter',exact=True).select_option('suspended')
                    page.once('dialog',lambda dialog:dialog.accept())
                    page.get_by_role('button',name='Reactivate',exact=True).click()
                    expect(page.get_by_text('No users match these filters.',exact=True)).to_be_visible()
                    page.get_by_label('User status filter',exact=True).select_option('')
                    expect(page.get_by_role('cell',name='target@example.com',exact=True)).to_be_visible()
                    page.get_by_label('Billed plan filter',exact=True).select_option('family_pack')
                    expect(page.get_by_text('No users match these filters.',exact=True)).to_be_visible()
                    page.get_by_label('Billed plan filter',exact=True).select_option('')
                    page.get_by_role('button',name='Subscriptions',exact=True).click()
                    page.get_by_label('Billed plan filter',exact=True).select_option('trial')
                    status=page.get_by_label('Status for subscription',exact=False).first
                    expect(status).to_be_visible()
                    page.once('dialog',lambda dialog:dialog.accept());status.select_option('suspended')
                    expect(page.get_by_role('cell',name='suspended',exact=True)).to_be_visible()
                    page.once('dialog',lambda dialog:dialog.accept());status.select_option('active')
                    expect(page.get_by_role('cell',name='active',exact=True)).to_be_visible()
                    page.get_by_label('Billed plan filter',exact=True).select_option('')
                    page.route('**/admin/settings',lambda route:route.fulfill(status=503,json={'detail':'Temporary settings test error'}),times=1)
                    page.get_by_role('button',name='Admin Settings',exact=True).click()
                    expect(page.get_by_role('alert')).to_contain_text('Temporary settings test error')
                    page.get_by_role('button',name='Retry',exact=True).click()
                    expect(page.get_by_role('alert')).to_have_count(0)
                    for title in ['Subscriptions','Demo Billing Reports','AI Usage Monitoring','Support / Activity','Admin Settings','Dashboard']:
                        page.get_by_role('button',name=title,exact=True).click()
                        expect(page.get_by_text('Loading platform data…',exact=True)).to_have_count(0)
                        expect(page.get_by_role('alert')).to_have_count(0)
                    for width in [360,768,1024,1440]:
                        page.set_viewport_size({'width':width,'height':1000})
                        for title in ['User Management','Subscriptions','Demo Billing Reports','AI Usage Monitoring','Support / Activity','Admin Settings','Dashboard']:
                            page.get_by_role('button',name=title,exact=True).click()
                            expect(page.get_by_text('Loading platform data…',exact=True)).to_have_count(0)
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),title+': '+str(width)
                    page.screenshot(path=str(artifacts/'admin-dashboard-desktop.png'),full_page=True)
                    signed_session=page.evaluate('JSON.parse(sessionStorage.getItem("maxbud_auth"))')
                    page.evaluate('()=>{const value=JSON.parse(sessionStorage.getItem("maxbud_auth"));value.token="e30.eyJleHAiOjB9.signature";sessionStorage.setItem("maxbud_auth",JSON.stringify(value));}')
                    expect(page).to_have_url(WEB+'/login')
                    page.evaluate('(value)=>sessionStorage.setItem("maxbud_auth",JSON.stringify(value))',signed_session)
                    page.goto(WEB+'/dashboard/admin')
                    expect(page.get_by_role('heading',name='Administration',exact=True)).to_be_visible()
                    page.get_by_role('button',name='Sign out',exact=True).click()
                    expect(page).to_have_url(WEB+'/login')
                    page.goto(WEB+'/dashboard/admin');expect(page).to_have_url(WEB+'/login')
                    # A forged frontend role cannot override /auth/me or API authorization.
                    session={'token':normal['access_token'],'user':normal['user']|{'role':'admin'},'onboarding_completed':True}
                    page.evaluate('(value)=>sessionStorage.setItem("maxbud_auth",JSON.stringify(value))',session)
                    page.goto(WEB+'/dashboard/admin')
                    expect(page.get_by_role('alert')).to_contain_text('Platform administrator access is required')
                    assert request.get(API+'/admin/overview',headers={'Authorization':'Bearer '+normal['access_token']}).status==403
                    import sqlite3
                    with sqlite3.connect(scratch+'/test.db') as fixture:
                        fixture.execute("UPDATE users SET is_active=0 WHERE email='browser@example.com'")
                    page.evaluate('(value)=>sessionStorage.setItem("maxbud_auth",JSON.stringify(value))',signed_session)
                    page.goto(WEB+'/dashboard/admin');expect(page).to_have_url(WEB+'/login')
                    assert not errors,errors
                    print('PASS: cards 3/6 colors, full surface and no overflow at 360/768/1024/1440; actual admin login validation/wrong password/redirect; all seven modules; search/status/plan filters; suspend/reactivate; mobile/desktop; subscription status actions; settings error/retry; session expiry; suspended admin; logout/protected routes/forged-role denial; no JS errors')
                    browser.close()
            finally:
                for process in processes:
                    if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
                for process in processes:
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL)


if __name__=='__main__':run()
