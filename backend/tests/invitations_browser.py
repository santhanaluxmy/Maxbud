"""React -> local HTTP -> FastAPI -> temporary SQLite invitation acceptance.

Run from backend: .venv/bin/python tests/invitations_browser.py
Builds an isolated frontend artifact. No genuine MySQL, SMTP, Stripe or AI calls.
All names/accounts/money are synthetic. No invitation tokens are printed.
"""
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
PASSWORD = 'SyntheticInvitationPassword1!'


def run():
    import requests
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    with tempfile.TemporaryDirectory(prefix='maxbud-invitations-browser-') as scratch:
        directory = Path(scratch)
        output = directory / 'dist'
        api_socket = socket.socket()
        api_socket.bind(('127.0.0.1', 0))
        api_socket.listen()
        api_url = 'http://127.0.0.1:' + str(api_socket.getsockname()[1])

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def handle_request(self):
                try:
                    if self.path.startswith('/api/'):
                        content = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                        headers = {k:v for k,v in self.headers.items() if k.lower() not in {'host','connection','accept-encoding','content-length'}}
                        with requests.Session() as client:
                            client.trust_env = False
                            response = client.request(self.command, api_url + self.path[4:], headers=headers, data=content, timeout=30)
                        self.send_response(response.status_code)
                        self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                        body = response.content
                    else:
                        path = (output / unquote(self.path.split('?')[0]).lstrip('/')).resolve()
                        if output not in path.parents or not path.is_file():
                            path = output / 'index.html'
                        body = path.read_bytes()
                        self.send_response(200)
                        self.send_header('Content-Type', mimetypes.guess_type(path)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = do_POST = do_PATCH = do_PUT = do_DELETE = handle_request

        web = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        web_url = 'http://127.0.0.1:' + str(web.server_address[1])
        os.environ.update({
            'ENVIRONMENT':'test', 'RATE_LIMIT_ENABLED':'false', 'JWT_SECRET':secrets.token_urlsafe(48),
            'DB_USER':'isolated_test_unused', 'DB_PASSWORD':'unused',
            'FRONTEND_ORIGIN':web_url, 'PUBLIC_FRONTEND_URL':web_url,
            'SMTP_HOST':'', 'SMTP_USERNAME':'', 'SMTP_PASSWORD':'', 'SMTP_FROM':'',
            'STRIPE_SECRET_KEY':'', 'STRIPE_WEBHOOK_SECRET':'', 'GROQ_API_KEY':'', 'OPENAI_API_KEY':'',
            'DEMO_PAYMENTS_ENABLED':'false', 'RECEIPT_STORAGE_DIR':str(directory / 'receipts'),
        })
        from sqlalchemy import create_engine, event, select
        from sqlalchemy.orm import Session
        from app.main import app
        import app.main as main
        from app.database import Base, get_db
        from app.models.family import Subscription
        from app.models.platform import FamilyInvitation
        from app.models.user import User, now_utc
        import uvicorn

        engine = create_engine('sqlite:///' + str(directory / 'test.db'), connect_args={'check_same_thread':False})

        @event.listens_for(engine, 'connect')
        def sqlite_only(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA synchronous=OFF')

        Base.metadata.create_all(engine)

        def sessions():
            with Session(engine, expire_on_commit=False) as db:
                yield db

        app.dependency_overrides[get_db] = sessions
        main.engine = engine
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False, lifespan='off'))
        api_thread = threading.Thread(target=lambda: server.run(sockets=[api_socket]), daemon=True)
        api_thread.start()
        client = requests.Session()
        client.trust_env = False
        web_thread = None

        def api(path, data=None, person=None, method=None):
            response = client.request(method or ('GET' if data is None else 'POST'), api_url + path,
                                      headers={'Authorization':'Bearer ' + person['access_token']} if person else {},
                                      json=data, timeout=20)
            assert response.ok, f'{path}: HTTP {response.status_code}'
            return response.json()

        def credentials(name):
            return {'full_name':name.title(), 'email':name+'@example.com', 'password':PASSWORD, 'confirm_password':PASSWORD}

        try:
            for _ in range(200):
                try:
                    if client.get(api_url + '/health', timeout=1).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.05)
            else:
                raise RuntimeError('Disposable API did not start')
            owner = api('/auth/register', credentials('mathy-invitation'))
            with Session(engine) as db:
                db.get(User, owner['user']['id']).onboarding_completed = True
                subscription = db.scalar(select(Subscription).where(Subscription.user_id == owner['user']['id']))
                subscription.plan='family_pack'; subscription.status='active'; subscription.source='test_access'
                subscription.expires_at=now_utc()+timedelta(hours=1)
                db.commit()
            api('/family', {'name':'Mathy Household'}, owner)
            owner_account = api('/accounts', {'name':'PRIVATE MATHY BANK','kind':'bank','opening_balance':'5000'}, owner)['id']
            wallet = api('/family/wallets', {'name':'Common Wallet'}, owner)['id']
            env = os.environ | {'VITE_API_URL':'/api','VITE_BACKEND_URL':'','VITE_GOOGLE_CLIENT_ID':''}
            with (directory / 'build.log').open('w') as log:
                result=subprocess.run(['npm','run','build','--','--outDir',str(output)], cwd=ROOT/'frontend', env=env, stdout=log, stderr=log, timeout=180)
                assert result.returncode == 0, 'Isolated frontend build failed'
            web_thread = threading.Thread(target=web.serve_forever, daemon=True)
            web_thread.start()

            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                owner_context = browser.new_context(viewport={'width':1440,'height':1000}, permissions=['clipboard-read','clipboard-write'])
                member_context = browser.new_context(viewport={'width':390,'height':900})
                errors=[]
                pages=[owner_context.new_page(),member_context.new_page()]
                page,member_page=pages
                for current in pages:
                    current.set_default_timeout(20000)
                    current.on('pageerror', lambda error: errors.append(str(error)))

                def go(current,path):
                    current.goto(path if path.startswith('http') else web_url+path, wait_until='domcontentloaded', timeout=60000)

                def login(current,email):
                    current.get_by_label('Email Address',exact=True).fill(email)
                    current.get_by_label('Password',exact=True).fill(PASSWORD)
                    current.get_by_role('button',name='Sign In',exact=False).click()

                go(page,'/login');login(page,'mathy-invitation@example.com')
                expect(page).to_have_url(web_url+'/dashboard')
                go(page,'/dashboard/family/members')
                expect(page.get_by_role('heading',name='Household members',exact=True)).to_be_visible()

                def create_invite(email):
                    page.get_by_label('Invited email',exact=True).fill(email)
                    page.get_by_role('button',name='Create Invitation',exact=True).click()
                    link=page.get_by_role('textbox',name='Invitation link',exact=True)
                    expect(link).to_be_visible()
                    expect(link).to_contain_text(web_url+'/invite#invite=')
                    return link.inner_text()

                invitation=create_invite('yathis-invitation@example.com')
                expect(page.get_by_text('Invitation created — email not sent.',exact=False)).to_be_visible()
                page.get_by_role('button',name='Copy Link',exact=True).click()
                expect(page.get_by_text('Invitation link copied.',exact=True)).to_be_visible()
                assert page.evaluate('navigator.clipboard.readText()')==invitation
                for width in [360,1440]:
                    page.set_viewport_size({'width':width,'height':1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Invitation page overflow'
                    box=page.get_by_role('textbox',name='Invitation link').bounding_box()
                    assert box and box['width']>200
                    page.screenshot(path=f'/tmp/maxbud-invitation-{width}.png',mask=[page.get_by_role('textbox',name='Invitation link')])
                page.set_viewport_size({'width':1440,'height':1000})
                print('PASS: full-width link, real clipboard copy, honest missing-SMTP status, 360/1440 layouts',flush=True)

                go(member_page,invitation)
                expect(member_page.get_by_role('heading',name='Mathy Household',exact=True)).to_be_visible()
                member_page.get_by_role('link',name='Sign in to accept',exact=True).click()
                login(member_page,'mathy-invitation@example.com')
                expect(member_page).to_have_url(web_url+'/invite')
                expect(member_page.get_by_text('This invitation is for',exact=False)).to_be_visible()
                member_page.get_by_role('button',name='Switch account',exact=True).click()
                member_page.get_by_role('link',name='Create an account',exact=True).click()
                for name,value in [('name','Yathis'),('email','yathis-invitation@example.com'),('password',PASSWORD),('confirmPassword',PASSWORD)]:
                    member_page.locator('input[name="'+name+'"]').fill(value)
                member_page.get_by_role('button',name='Create Account',exact=False).click()
                expect(member_page).to_have_url(web_url+'/invite')
                member_page.reload(wait_until='domcontentloaded')
                member_page.get_by_role('button',name='Accept Invitation',exact=True).click()
                expect(member_page).to_have_url(web_url+'/dashboard/family')
                expect(member_page.get_by_role('heading',name='Mathy Household',exact=True)).to_be_visible()
                expect(page.get_by_text('yathis-invitation@example.com',exact=True).first).to_be_visible(timeout=12000)
                overview=page.locator('.family-overview div').filter(has=page.get_by_text('Active members',exact=True))
                expect(overview.locator('dd')).to_have_text('2',timeout=12000)
                member=api('/auth/login',{'email':'yathis-invitation@example.com','password':PASSWORD})
                assert member['has_household'] and not member['onboarding_completed']
                print('PASS: token survives login, wrong-account switch, registration and refresh; acceptance activates two memberships without personal onboarding',flush=True)

                member_account=api('/accounts',{'name':'PRIVATE YATHIS CASH','kind':'cash','opening_balance':'4000'},member)['id']
                for person,account,amount,key in [(owner,owner_account,'3000','mathy-fund'),(member,member_account,'2000','yathis-fund')]:
                    api(f'/family/wallets/{wallet}/contribute',{'account_id':account,'amount':amount,'request_id':key},person)
                api('/family/expenses',{'account_id':wallet,'category':'Food','amount':'1000','request_id':'groceries'},member)
                for current in pages:
                    go(current,'/dashboard/family/wallets')
                    expect(current.locator('main')).to_contain_text('4,000')
                    expect(current.locator('main')).not_to_contain_text('PRIVATE MATHY BANK')
                    expect(current.locator('main')).not_to_contain_text('PRIVATE YATHIS CASH')
                denied=client.get(api_url+f'/accounts/{owner_account}',headers={'Authorization':'Bearer '+member['access_token']})
                assert denied.status_code==404
                for person in [owner,member]:
                    assert api('/dashboard?scope=family',person=person)['total_balance']=='4000.00'
                print('PASS: both users see the LKR 4,000 shared wallet; private accounts remain inaccessible',flush=True)
                member_page.get_by_role('button',name='Toggle navigation',exact=True).click()
                member_page.get_by_role('button',name='Sign out',exact=True).first.click()
                expect(member_page).to_have_url(web_url+'/login')
                login(member_page,'yathis-invitation@example.com')
                expect(member_page).to_have_url(web_url+'/dashboard/family')
                go(member_page,invitation)
                member_page.get_by_role('button',name='Continue to household',exact=True).click()
                expect(member_page).to_have_url(web_url+'/dashboard/family')
                assert api('/family',person=owner)['total_active_members']==2
                print('PASS: both contexts access shared wallet/report, wallet is 4000, private accounts are isolated, logout/login and duplicate acceptance preserve membership',flush=True)

                go(page,'/dashboard/family/members')
                revoked=create_invite('revoked-invitation@example.com')
                revoke=page.get_by_role('button',name='Revoke invitation for revoked-invitation@example.com',exact=True)
                revoke.click();dialog=page.get_by_role('dialog',name='Revoke invitation?',exact=True)
                expect(dialog).to_be_visible();page.keyboard.press('Escape');expect(dialog).not_to_be_visible()
                revoke.click();dialog.get_by_role('button',name=re.compile('^Revoke invitation$',re.I)).click();expect(dialog).not_to_be_visible()
                history=page.locator('details.family-invite-history')
                assert not history.evaluate('(node)=>node.open')
                go(member_page,revoked);expect(member_page.get_by_text('The owner has revoked',exact=False)).to_be_visible()
                expect(member_page.get_by_role('button',name='Accept Invitation',exact=True)).to_have_count(0)
                expired=create_invite('expired-invitation@example.com')
                with Session(engine) as db:
                    row=db.scalar(select(FamilyInvitation).where(FamilyInvitation.email=='expired-invitation@example.com'))
                    row.expires_at=now_utc()-timedelta(seconds=1);db.commit()
                go(member_page,expired);expect(member_page.get_by_text('This invitation has expired.',exact=False)).to_be_visible()
                go(member_page,web_url+'/invite#invite='+'x'*43)
                expect(member_page.get_by_role('alert')).to_contain_text('invalid')
                print('PASS: revoke confirmation/cancel, collapsed history, expired/revoked/invalid link states',flush=True)

                # A separate empty-household fixture exercises typed close confirmation.
                empty=api('/auth/register',credentials('empty-household'))
                with Session(engine) as db:
                    user=db.get(User,empty['user']['id']);user.onboarding_completed=True
                    sub=db.scalar(select(Subscription).where(Subscription.user_id==user.id))
                    sub.plan='family_pack';sub.status='active';sub.source='test_access';sub.expires_at=now_utc()+timedelta(hours=1);db.commit()
                api('/family',{'name':'Empty Household'},empty)
                empty_context=browser.new_context(viewport={'width':360,'height':900})
                empty_page=empty_context.new_page();go(empty_page,'/login');login(empty_page,'empty-household@example.com')
                expect(empty_page).to_have_url(web_url+'/dashboard')
                go(empty_page,'/dashboard/family/members')
                empty_page.get_by_role('button',name='Close empty household',exact=True).click()
                close=empty_page.get_by_role('dialog',name='Close this household?',exact=True)
                expect(close.get_by_role('button',name='Close household',exact=True)).to_be_disabled()
                close.get_by_role('textbox').fill('Empty Household')
                expect(close.get_by_role('button',name='Close household',exact=True)).to_be_enabled()
                close.get_by_role('button',name='Cancel',exact=True).click()
                assert api('/family',person=empty)['name']=='Empty Household'
                empty_page.get_by_role('button',name='Close empty household',exact=True).click()
                close.get_by_role('textbox').fill('Empty Household')
                close.get_by_role('button',name='Close household',exact=True).click()
                expect(empty_page.get_by_text('The empty household is closed.',exact=False)).to_be_visible()
                assert not errors, 'Browser page errors occurred'
                print('PASS: typed household-close confirmation, cancellation preserves household; no browser page errors',flush=True)
                browser.close()
        finally:
            if web_thread and web_thread.is_alive():
                web.shutdown()
                web_thread.join(timeout=5)
            web.server_close()
            server.should_exit=True
            api_thread.join(timeout=10)
            api_socket.close()
            app.dependency_overrides.clear()
            client.close()
            engine.dispose()


if __name__=='__main__':
    try:
        run()
    except Exception:
        message=re.sub(r'(#invite=)[^\s\"\)\']+',r'\1[redacted]',traceback.format_exc())
        print(message,file=sys.stderr)
        raise SystemExit(1)
