"""Browser -> real FastAPI -> disposable SQLite. Stripe responses are mocked.
No real Stripe payments, customer changes, genuine MySQL access, or migrations.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from core_flow_browser import ROOT, PASSWORD, stop

API = 'http://127.0.0.1:8891'
WEB = 'http://127.0.0.1:5191'


def serve():
    import sqlite3
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    @event.listens_for(Engine,'connect')
    def temporary_sqlite_only(connection,_):
        if isinstance(connection,sqlite3.Connection):
            connection.execute('PRAGMA synchronous=OFF')
            connection.execute('PRAGMA journal_mode=MEMORY')
    from fastapi import Depends
    from app.main import app
    from app.core.deps import current_user
    from app.database import get_db
    from app.models.access import StripeAccount
    from app.models.ai import AIScan, AIUsage, AdvisorMessage
    from app.services import stripe_test as stripe
    from core_flow_browser import serve as core_serve
    sessions, subscriptions = {}, {}

    def price(plan):
        return {'id':'price_browser_family' if plan=='family_pack' else 'price_browser_premium', 'livemode':False,
                'active':True,'currency':'lkr','unit_amount':90000 if plan=='family_pack' else 65000,
                'recurring':{'interval':'month','interval_count':1}}

    def provider(method,path,data=None,key=None):
        if path.startswith('prices/'):
            return price('family_pack' if path.endswith('family') else 'premium_individual')
        if path=='customers':
            return {'id':'cus_browser_'+data['metadata[maxbud_user_id]'],'livemode':False}
        if path=='checkout/sessions':
            session_id='cs_test_browser_'+data['client_reference_id']
            sessions[session_id]={'id':session_id,'livemode':False,'customer':data['customer'],
                'mode':'subscription','status':'open','payment_status':'unpaid','subscription':None,
                'client_reference_id':data['client_reference_id'],'plan':'family_pack' if data['line_items[0][price]'].endswith('family') else 'premium_individual',
                'success_url':data['success_url'],'cancel_url':data['cancel_url'],
                'url':'https://checkout.stripe.com/c/'+session_id}
            return deepcopy(sessions[session_id])
        if path.startswith('checkout/sessions/'):
            return deepcopy(sessions[path.split('/')[2]])
        if path.startswith('subscriptions/'):
            return deepcopy(subscriptions[path.split('/')[1]])
        if path.startswith('billing_portal/configurations/'):
            return {'id':'bpc_browser','livemode':False,'active':True,'features':{'subscription_update':{'enabled':False}}}
        if path=='billing_portal/sessions':
            return {'livemode':False,'url':'https://billing.stripe.com/mock-portal'}
        raise RuntimeError('Unexpected mock Stripe request')

    stripe.call=provider

    @app.post('/__stripe_test__/seed-usage')
    def seed(user=Depends(current_user),db=Depends(get_db)):
        for _ in range(3):
            scan=AIScan(user_id=user.id,status='review');db.add(scan);db.flush()
            db.add(AIUsage(user_id=user.id,scan_id=scan.id))
        for index in range(2):
            db.add(AdvisorMessage(user_id=user.id,question='Test history',answer='Preserved answer',request_id='browser-'+str(index)))
        db.commit()
        return {'seeded':True}

    @app.post('/__stripe_test__/complete')
    def complete(body:dict,user=Depends(current_user),db=Depends(get_db)):
        account=db.get(StripeAccount,user.id)
        session=sessions[account.checkout_id]
        key='sub_browser_'+str(user.id)
        paid=body.get('paid') is True
        session.update(status='complete',payment_status='paid' if paid else 'unpaid',subscription=key)
        now=int(time.time())
        subscriptions[key]={'id':key,'livemode':False,'customer':account.customer_id,'status':'active' if paid else 'incomplete',
            'metadata':{'maxbud_user_id':str(user.id)},'cancel_at_period_end':False,
            'items':{'data':[{'quantity':1,'price':price(session['plan']),'current_period_start':now,'current_period_end':now+2592000}]},
            'latest_invoice':{'livemode':False,'paid':paid,'status':'paid' if paid else 'open','customer':account.customer_id,
                'parent':{'subscription_details':{'subscription':key}}}}
        return {'success_url':session['success_url']}

    core_serve()


def run():
    from playwright.sync_api import sync_playwright, expect
    expect.set_options(timeout=20000)
    with tempfile.TemporaryDirectory(prefix='maxbud-core-flow-') as scratch:
        env=os.environ | {'CORE_FLOW_DIRECTORY':scratch,'CORE_FLOW_API_PORT':'8891','ENVIRONMENT':'test','RATE_LIMIT_ENABLED':'false',
            'PYTHONPATH':str(ROOT/'backend'),'PYTHONDONTWRITEBYTECODE':'1','RECEIPT_STORAGE_DIR':scratch+'/receipts',
            'STRIPE_SECRET_KEY':'sk_test_browser','STRIPE_WEBHOOK_SECRET':'whsec_browser','STRIPE_PRICE_PREMIUM_MONTHLY':'price_browser_premium',
            'STRIPE_PRICE_FAMILY_MONTHLY':'price_browser_family','STRIPE_PORTAL_CONFIGURATION':'bpc_browser','DEMO_PAYMENTS_ENABLED':'false',
            'GROQ_API_KEY':'','OPENAI_API_KEY':'','FRONTEND_ORIGIN':WEB,'API_PROXY_TARGET':API,
            'VITE_API_URL':'','VITE_BACKEND_URL':'','VITE_GOOGLE_CLIENT_ID':''}
        backend=frontend=None
        with open('/tmp/maxbud-stripe-browser-services.log','w+') as log:
            def start_backend():
                return subprocess.Popen([sys.executable,__file__,'--serve'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log,start_new_session=True)
            try:
                backend=start_backend()
                frontend=subprocess.Popen(['npm','run','dev','--','--host','127.0.0.1','--port','5191','--strictPort'],cwd=ROOT/'frontend',env=env,stdout=log,stderr=log,start_new_session=True)
                with sync_playwright() as pw:
                    req=pw.request.new_context()
                    def ready():
                        for _ in range(240):
                            try:
                                if req.get(WEB+'/api/health',timeout=1000).ok:return
                            except Exception:pass
                            time.sleep(.25)
                        raise RuntimeError('Disposable browser services did not start; see /tmp/maxbud-stripe-browser-services.log')
                    ready()
                    def create(name):
                        email=name.replace(' ','').lower()+'@example.com'
                        result=req.post(WEB+'/api/auth/register',data={'full_name':name,'email':email,'password':PASSWORD,'confirm_password':PASSWORD})
                        assert result.status==201
                        person=result.json();headers={'Authorization':'Bearer '+person['access_token']}
                        for path,body in [('about-you',{'full_name':name,'currency':'LKR'}),('income',{'sources':[{'name':'Salary','amount':'1000'}]}),('accounts',{'accounts':[{'name':'Cash','kind':'cash'}]}),('budgets',{'budgets':[{'category':'Food','monthly_limit':'100'}]}),('goals',{'goals':[]})]:
                            assert req.post(WEB+'/api/onboarding/'+path,data=body,headers=headers).ok
                        return email,headers
                    browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
                    context=browser.new_context(viewport={'width':1440,'height':1000})
                    page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.route('https://checkout.stripe.com/**',lambda route:route.fulfill(content_type='text/html',body='<h1>Mock Stripe Checkout</h1>'))
                    def login(target,email):
                        target.goto(WEB+'/login')
                        target.locator('input[type="email"]').fill(email)
                        target.locator('input[type="password"]').fill(PASSWORD)
                        target.get_by_role('button',name='Sign In',exact=False).click()
                        expect(target).to_have_url(WEB+'/dashboard')
                    email,headers=create('Premium Browser')
                    assert req.post(WEB+'/api/__stripe_test__/seed-usage',headers=headers).ok
                    login(page,email)
                    page.goto(WEB+'/dashboard/upgrade')
                    expect(page.get_by_role('button',name='Upgrade to Premium',exact=True)).to_be_visible()
                    expect(page.get_by_text('3 / 5',exact=True)).to_be_visible()
                    assert page.get_by_text('Demo checkout disabled',exact=True).count()==0
                    assert page.get_by_role('combobox',name='Billing period').count()==0
                    page.get_by_role('button',name='Upgrade to Premium',exact=True).click()
                    expect(page.get_by_role('heading',name='Mock Stripe Checkout')).to_be_visible()
                    result=req.post(WEB+'/api/__stripe_test__/complete',data={'paid':False},headers=headers).json()
                    page.goto(result['success_url'])
                    expect(page.get_by_role('heading',name='Activating your subscription…')).to_be_visible()
                    assert page.get_by_role('heading',name='Premium Active',exact=True).count()==0
                    assert req.get(WEB+'/api/subscriptions',headers=headers).json()['plan']=='trial'
                    assert req.post(WEB+'/api/__stripe_test__/complete',data={'paid':True},headers=headers).ok
                    expect(page.get_by_role('heading',name='Premium Active',exact=True)).to_be_visible()
                    page.get_by_role('link',name='Go to Dashboard',exact=True).click()
                    page.goto(WEB+'/dashboard/upgrade')
                    expect(page.get_by_text('3 / 100',exact=True)).to_be_visible()
                    expect(page.get_by_text('2 / 200',exact=True)).to_be_visible()
                    premium=page.locator('.subscription-plan').filter(has=page.get_by_role('heading',name='Premium Individual',exact=True))
                    expect(premium.get_by_role('button',name='Current Plan',exact=True)).to_be_disabled()
                    page.screenshot(path='/tmp/maxbud-stripe-desktop.png',full_page=True)
                    page.reload();expect(page.get_by_text('3 / 100',exact=True)).to_be_visible()
                    page.get_by_role('button',name='Sign out',exact=True).first.click()
                    login(page,email);page.goto(WEB+'/dashboard/ai-scan')
                    expect(page.locator('.ai-usage-line')).to_contain_text('3 of 100 scans used this month')
                    other=browser.new_context(viewport={'width':390,'height':844});device=other.new_page()
                    login(device,email);device.goto(WEB+'/dashboard/upgrade')
                    expect(device.get_by_text('3 / 100',exact=True)).to_be_visible()
                    assert device.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    stop(backend);backend=start_backend();ready()
                    device.reload();expect(device.get_by_text('3 / 100',exact=True)).to_be_visible()
                    print('PASS: Premium checkout, delayed verified activation, usage preservation, refresh, logout/login, second browser, API restart',flush=True)
                    family_email,family_headers=create('Family Browser')
                    login(page,family_email);page.set_viewport_size({'width':390,'height':844})
                    page.goto(WEB+'/dashboard/upgrade')
                    page.get_by_role('button',name='Choose Family Pack',exact=True).click()
                    expect(page.get_by_role('heading',name='Mock Stripe Checkout')).to_be_visible()
                    result=req.post(WEB+'/api/__stripe_test__/complete',data={'paid':True},headers=family_headers).json()
                    page.goto(result['success_url']);expect(page.get_by_role('heading',name='Family Pack Active',exact=True)).to_be_visible()
                    page.get_by_role('link',name='View subscription',exact=True).click()
                    family=page.locator('.subscription-plan').filter(has=page.get_by_role('heading',name='Family Pack',exact=True))
                    expect(family.get_by_role('button',name='Current Plan',exact=True)).to_be_disabled()
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                    page.screenshot(path='/tmp/maxbud-stripe-mobile.png',full_page=True)
                    page.goto(WEB+'/dashboard/family')
                    expect(page.get_by_role('button',name='Create household',exact=True)).to_be_visible()
                    assert not errors,errors
                    print('PASS: mobile Family Pack activation, current-plan protection, household entitlement, accessible controls, no page errors',flush=True)
                    browser.close();req.dispose()
            finally:
                stop(frontend);stop(backend)


if __name__=='__main__':
    serve() if '--serve' in sys.argv else run()
