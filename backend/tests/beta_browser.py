"""Opt-in real Groq browser integration on temporary SQLite; no real users seeded.
PYTHONPATH=. .venv/bin/python tests/beta_browser.py
"""
import json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[2]
API='http://127.0.0.1:8767';WEB='http://127.0.0.1:5176';PASSWORD='SecurePassword1!'


def run():
    from playwright.sync_api import sync_playwright,expect
    expect.set_options(timeout=25000)
    with tempfile.TemporaryDirectory(prefix='maxbud-beta-browser-') as directory:
        env=os.environ|{'PYTHONPATH':str(ROOT/'backend'),'FRONTEND_ORIGIN':WEB,'FAMILY_BROWSER_DB':f'sqlite:///{directory}/test.db','BROWSER_API_PORT':'8767','BROWSER_ADMIN':'true','RATE_LIMIT_ENABLED':'false','DEMO_PAYMENTS_ENABLED':'true','RECEIPT_STORAGE_DIR':directory+'/receipts'}
        with open(directory+'/server.log','w+') as log:
            backend=subprocess.Popen([sys.executable,str(ROOT/'backend/tests/family_browser.py'),'--serve'],cwd=ROOT/'backend',env=env,stdout=log,stderr=log,start_new_session=True)
            frontend=subprocess.Popen(['npm','run','dev','--','--host','127.0.0.1','--port','5176','--strictPort'],cwd=ROOT/'frontend',env=env|{'VITE_API_URL':API},stdout=log,stderr=log,start_new_session=True)
            try:
                with sync_playwright() as pw:
                    request=pw.request.new_context()
                    for url in [API+'/openapi.json',WEB]:
                        for _ in range(240):
                            try:
                                if request.get(url,timeout=1000).ok:break
                            except Exception:pass
                            time.sleep(.25)
                        else:
                            log.seek(0)
                            raise RuntimeError(log.read()[-4000:])
                    def new_user(name):
                        result=request.post(API+'/auth/register',data={'full_name':name,'email':name.lower()+'@example.com','password':PASSWORD,'confirm_password':PASSWORD})
                        assert result.ok,result.text()
                        auth=result.json();headers={'Authorization':'Bearer '+auth['access_token']}
                        steps=[('about-you',{'full_name':name,'currency':'LKR'}),('income',{'sources':[{'name':'Salary','amount':'100000','frequency':'monthly'}]}),('accounts',{'accounts':[{'name':'Private cash','kind':'cash','opening_balance':'50000'}]}),('budgets',{'budgets':[{'category':'Food','monthly_limit':'5000'}]}),('goals',{'goals':[]})]
                        for path,body in steps:
                            response=request.post(API+'/onboarding/'+path,data=body,headers=headers);assert response.ok,response.text()
                        auth=request.post(API+'/auth/login',data={'email':name.lower()+'@example.com','password':PASSWORD}).json()
                        return auth,headers
                    owner,oh=new_user('Yathis');member,mh=new_user('Sana')
                    browser=pw.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
                    errors=[]
                    def page_for(auth):
                        page=browser.new_page(viewport={'width':1440,'height':1000})
                        stored={'token':auth['access_token'],'user':auth['user'],'onboarding_completed':True}
                        page.add_init_script('sessionStorage.setItem("maxbud_auth",'+json.dumps(json.dumps(stored))+');')
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        return page
                    visitor=browser.new_page()
                    visitor.goto(WEB+'/register')
                    visitor.get_by_placeholder('Enter your full name',exact=True).fill('Browser New')
                    visitor.get_by_placeholder('you@example.com',exact=True).fill('browsernew@example.com')
                    visitor.get_by_placeholder('Create a strong password',exact=True).fill(PASSWORD)
                    visitor.get_by_placeholder('Confirm password',exact=True).fill(PASSWORD)
                    visitor.get_by_role('button',name='Create Account',exact=False).click()
                    expect(visitor.get_by_role('heading',name='Tell us about yourself',exact=True)).to_be_visible()
                    visitor.get_by_role('button',name='Save & Continue',exact=False).click()
                    visitor.get_by_label('Amount',exact=True).fill('100000')
                    visitor.get_by_role('button',name='Save & Continue',exact=False).click()
                    visitor.get_by_label('Opening balance',exact=True).fill('1000')
                    visitor.get_by_role('button',name='Save & Continue',exact=False).click()
                    visitor.get_by_role('button',name='Save & Continue',exact=False).click()
                    visitor.get_by_role('button',name='Open my dashboard',exact=False).click()
                    expect(visitor.get_by_text('Recent Transactions',exact=True)).to_be_visible()
                    visitor.get_by_role('button',name='Sign out',exact=True).click()
                    visitor.goto(WEB+'/login')
                    visitor.get_by_placeholder('you@example.com',exact=True).fill('browsernew@example.com')
                    visitor.get_by_placeholder('Enter your password',exact=True).fill(PASSWORD)
                    visitor.get_by_role('button',name='Sign In',exact=False).click()
                    expect(visitor.get_by_text('Recent Transactions',exact=True)).to_be_visible()
                    visitor.close()
                    print('PASS: browser registration → all five onboarding forms → dashboard → logout/login',flush=True)
                    page=page_for(owner)
                    page.goto(WEB+'/dashboard/upgrade')
                    expect(page.locator('.subscription-status')).to_contain_text('Free Trial')
                    for plan in ['Premium Individual','Family Pack']:
                        card=page.locator('.subscription-plan').filter(has=page.get_by_role('heading',name=plan,exact=True))
                        if card.count()==0:card=page.locator('.db-glass-card').filter(has=page.get_by_role('heading',name=plan,exact=True))
                        card.get_by_role('button',name='Open demo checkout',exact=True).click()
                        page.get_by_role('dialog').get_by_role('button',name='Simulate Successful Payment',exact=True).click()
                        expect(page.locator('.subscription-status')).to_contain_text(plan)
                    print('PASS: browser trial → demo Individual → demo Family Pack',flush=True)
                    page.goto(WEB+'/dashboard/family')
                    page.get_by_label('Household name',exact=True).fill('Yathis and Sana')
                    page.get_by_role('button',name='Create household',exact=True).click()
                    page.get_by_label('Invited email',exact=True).fill('sana@example.com')
                    page.get_by_role('button',name='Create secure invitation',exact=True).click()
                    link=page.get_by_label('Invitation link',exact=True)
                    expect(link).to_be_visible();invite=link.input_value()
                    sana=page_for(member);sana.goto(invite)
                    sana.get_by_role('button',name='Accept invitation',exact=True).click()
                    expect(sana.get_by_text('Invitation accepted. Personal finances remain private.',exact=True)).to_be_visible()
                    assert request.get(API+'/subscriptions',headers=mh).json()['plan']=='premium_individual'
                    page.reload();page.get_by_role('button',name='New shared wallet',exact=True).click()
                    dialog=page.get_by_role('dialog');dialog.get_by_label('Name',exact=True).fill('Household wallet');dialog.get_by_role('button',name='Save shared record',exact=True).click()
                    expect(page.get_by_role('heading',name='Household wallet',exact=True)).to_be_visible()
                    for actor,amount in [(page,'20000'),(sana,'30000')]:
                        actor.reload();actor.get_by_role('button',name='Contribute to wallet',exact=True).click()
                        dialog=actor.get_by_role('dialog');dialog.get_by_label('Amount (LKR)',exact=True).fill(amount);dialog.get_by_label('Payment account',exact=True).select_option(label='Personal: Private cash');dialog.get_by_role('button',name='Save shared record',exact=True).click()
                        expect(actor.get_by_role('dialog')).to_have_count(0)
                    sana.get_by_role('button',name='Add shared expense',exact=True).click()
                    dialog=sana.get_by_role('dialog');dialog.get_by_label('Amount (LKR)',exact=True).fill('8000');dialog.get_by_label('Payment account',exact=True).select_option(label='Shared: Household wallet');dialog.get_by_role('button',name='Save shared record',exact=True).click()
                    expect(sana.get_by_role('dialog')).to_have_count(0)
                    assert Decimal(request.get(API+'/family/wallets',headers=oh).json()[0]['balance'])==42000
                    print('PASS: secure invitation, sponsored member and browser wallet 50000 → 42000',flush=True)
                    page.goto(WEB+'/dashboard/ai-scan');page.get_by_label('Receipt image',exact=True).set_input_files(str(ROOT/'backend/sample_receipt.jpg'))
                    with page.expect_response(lambda r:r.url.endswith('/ai/receipts') and r.request.method=='POST',timeout=65000) as scan:
                        page.get_by_role('button',name='Scan receipt',exact=True).click()
                    if scan.value.status!=201:
                        operator=request.post(API+'/auth/login',data={'email':'browser@example.com','password':PASSWORD}).json()
                        audit=request.get(API+'/admin/activity',headers={'Authorization':'Bearer '+operator['access_token']}).json()
                        print('Receipt diagnostics:',[r['details'] for r in audit if r['kind']=='ai_failure'],flush=True)
                    assert scan.value.status==201,scan.value.text()
                    data=scan.value.json()['data'];assert data['printed_total'] is None and data['category'].casefold()=='food'
                    expect(page.get_by_text('No printed grand total was found.',exact=False)).to_be_visible()
                    page.get_by_label('Reviewed transaction total',exact=True).fill(str(data['calculated_subtotal']))
                    if not data['currency']:page.get_by_label('currency',exact=True).fill('LKR')
                    if not data['date']:page.get_by_label('date',exact=True).fill('2026-11-11')
                    page.get_by_label('Account',exact=True).select_option(label='Private cash')
                    page.get_by_role('button',name='Confirm expense',exact=True).click()
                    expect(page.get_by_text('Receipt transaction saved.',exact=True)).to_be_visible()
                    page.goto(WEB+'/dashboard/ai-advisor');page.get_by_label('Your question',exact=True).fill('Can I spend LKR 5000 on shopping? Use my actual Food budget and tracked cash. Answer briefly in Tamil and English.')
                    with page.expect_response(lambda r:r.url.endswith('/ai/advisor') and r.request.method=='POST',timeout=65000) as answer:page.get_by_role('button',name='Send question',exact=True).click()
                    assert answer.value.ok,answer.value.text()
                    expect(page.locator('.advisor-assistant').first).to_be_visible()
                    page.reload();expect(page.locator('.advisor-assistant').first).to_be_visible()
                    assert request.get(API+'/ai/usage',headers=oh).json()['used']=={'receipt_scans':1,'advisor_messages':1}
                    page.set_viewport_size({'width':390,'height':844});page.goto(WEB+'/dashboard/family');expect(page.get_by_role('heading',name='Family Management',exact=True)).to_be_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert not errors,errors
                    print('PASS: FRONTEND upload → LIVE Groq Tamil receipt → null printed total review → one confirmed transaction; LIVE advisor → persisted history; mobile household; no JS errors',flush=True)
                    browser.close()
            finally:
                for process in [frontend,backend]:
                    if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
                for process in [frontend,backend]:
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL)


if __name__=='__main__':run()
