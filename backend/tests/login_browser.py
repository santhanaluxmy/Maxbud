"""Login-only browser regression against a disposable SQLite API.

Run from backend: .venv/bin/python tests/login_browser.py
No genuine database records, OAuth accounts or external providers are used.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))


def run():
    import requests
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    with tempfile.TemporaryDirectory(prefix='maxbud-login-only-') as scratch:
        directory = Path(scratch)
        output = directory / 'dist'
        api_socket = socket.socket()
        api_socket.bind(('127.0.0.1', 0)); api_socket.listen()
        api_url = 'http://127.0.0.1:' + str(api_socket.getsockname()[1])

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass

            def handle_request(self):
                try:
                    if self.path.startswith('/api/'):
                        body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                        headers = {k:v for k,v in self.headers.items() if k.lower() not in {'host','connection','content-length','accept-encoding'}}
                        with requests.Session() as client:
                            client.trust_env = False
                            response = client.request(self.command, api_url + self.path[4:], headers=headers, data=body, timeout=25)
                        body = response.content
                        self.send_response(response.status_code)
                        content_type = response.headers.get('Content-Type', 'application/json')
                    else:
                        path = (output / unquote(self.path.split('?')[0]).lstrip('/')).resolve()
                        if output not in path.parents or not path.is_file(): path = output / 'index.html'
                        body = path.read_bytes()
                        content_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                        self.send_response(200)
                    self.send_header('Content-Type', content_type)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers(); self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError): pass

            do_GET = do_POST = do_OPTIONS = handle_request

        web = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        origin = 'http://127.0.0.1:' + str(web.server_address[1])
        os.environ.update(ENVIRONMENT='test', RATE_LIMIT_ENABLED='false', JWT_SECRET=secrets.token_urlsafe(48),
                          DB_USER='unused_test', DB_PASSWORD='unused_test', FRONTEND_ORIGIN=origin,
                          SMTP_HOST='', GROQ_API_KEY='', STRIPE_SECRET_KEY='', STRIPE_WEBHOOK_SECRET='')
        from sqlalchemy import create_engine, event
        from sqlalchemy.orm import Session
        from app.main import app
        import app.main as main
        from app.database import Base, get_db
        from app.models.user import User, AuthIdentity
        from app.core.security import hash_password
        from app.services.subscriptions import start_trial
        import uvicorn
        engine = create_engine('sqlite:///' + str(directory / 'test.db'), connect_args={'check_same_thread':False})

        @event.listens_for(engine, 'connect')
        def sqlite_only(connection, _):
            connection.execute('PRAGMA foreign_keys=ON'); connection.execute('PRAGMA synchronous=OFF')

        Base.metadata.create_all(engine)
        password = 'SyntheticLoginPassword1!'
        with Session(engine) as db:
            person = User(full_name='Login Tester', email='login-test@example.com', onboarding_completed=True)
            db.add(person); db.flush()
            db.add(AuthIdentity(user_id=person.id, provider='password', password_hash=hash_password(password)))
            start_trial(db, person); db.commit()

        def sessions():
            with Session(engine, expire_on_commit=False) as db: yield db

        app.dependency_overrides[get_db] = sessions; main.engine = engine
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off', access_log=False))
        api_thread = threading.Thread(target=lambda: server.run(sockets=[api_socket]), daemon=True)
        api_thread.start(); web_thread = None
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(.05)
            else: raise RuntimeError('Temporary API did not start')
            env = os.environ | {'VITE_API_URL':'/api', 'VITE_BACKEND_URL':'', 'VITE_GOOGLE_CLIENT_ID':''}
            with (directory / 'build.log').open('w') as log:
                built = subprocess.run(['npm','run','build','--','--outDir',str(output)], cwd=ROOT/'frontend', env=env, stdout=log, stderr=log, timeout=180)
                assert built.returncode == 0, 'Temporary frontend build failed'
            web_thread = threading.Thread(target=web.serve_forever, daemon=True); web_thread.start()
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]; page.on('pageerror', lambda error: errors.append(str(error)))

                def go(path): page.goto(origin+path, wait_until='domcontentloaded', timeout=60000)
                def submit(secret=password):
                    page.get_by_label('Email Address',exact=True).fill('login-test@example.com')
                    page.get_by_label('Password',exact=True).fill(secret)
                    page.get_by_role('button',name='Sign In',exact=False).click()
                def ready(): expect(page.get_by_role('button',name='Sign In',exact=False)).to_be_enabled()
                def no_session():
                    assert page.evaluate('!sessionStorage.getItem("maxbud_auth") && !localStorage.getItem("maxbud_auth")')

                go('/login'); submit('WrongPassword1!')
                expect(page.get_by_role('alert')).to_contain_text('Invalid email or password'); ready(); no_session()
                print('PASS: wrong password displays 401 feedback and releases the submit button',flush=True)

                held=[]
                def stall(route): held.append(route)
                page.route('**/api/auth/login', stall)
                submit()
                expect(page.get_by_role('button',name='Signing In...',exact=True)).to_be_disabled()
                expect(page.get_by_role('alert')).to_contain_text('Sign-in timed out',timeout=20000)
                ready(); no_session()
                for route in held:
                    try: route.abort()
                    except Exception: pass  # The AbortController may already have canceled it.
                page.unroute('**/api/auth/login', stall)
                submit(); expect(page).to_have_url(origin+'/dashboard')
                expect(page.locator('main')).to_be_visible()
                print('PASS: stalled login times out at 15s; retry succeeds through FastAPI and redirects to dashboard',flush=True)

                page.get_by_role('button',name='Sign out',exact=True).first.click()
                expect(page).to_have_url(origin+'/login'); no_session()
                go('/dashboard'); expect(page).to_have_url(origin+'/login')
                page.get_by_role('checkbox').check(); submit()
                expect(page).to_have_url(origin+'/dashboard')
                assert page.evaluate('!!localStorage.getItem("maxbud_auth") && !sessionStorage.getItem("maxbud_auth")')
                page.reload(wait_until='domcontentloaded'); expect(page.locator('main')).to_be_visible()
                page.get_by_role('button',name='Sign out',exact=True).first.click()
                expect(page).to_have_url(origin+'/login'); no_session()
                print('PASS: logout clears storage, protected URL redirects, remembered login survives reload and logs out cleanly',flush=True)

                page.route('**/api/auth/login', lambda route: route.fulfill(status=503,json={'detail':'Sign-in service unavailable. Please try again.'}))
                submit(); expect(page.get_by_role('alert')).to_contain_text('Sign-in service unavailable'); ready(); no_session()
                page.unroute('**/api/auth/login')
                page.route('**/api/auth/login', lambda route: route.abort('connectionfailed'))
                submit(); expect(page.get_by_role('alert')).to_contain_text('Cannot connect'); ready(); no_session()
                page.unroute('**/api/auth/login')
                page.route('**/api/auth/login', lambda route: route.fulfill(status=200,json={}))
                submit(); expect(page.get_by_role('alert')).to_contain_text('Authentication token not received'); ready(); no_session()
                assert not errors, 'Unexpected browser JavaScript errors'
                print('PASS: 503, network failure and invalid success payload all release loading; no page errors',flush=True)
                browser.close()
        finally:
            if web_thread and web_thread.is_alive(): web.shutdown(); web_thread.join(timeout=5)
            web.server_close(); server.should_exit=True; api_thread.join(timeout=10); api_socket.close()
            app.dependency_overrides.clear(); engine.dispose()


if __name__ == '__main__': run()
