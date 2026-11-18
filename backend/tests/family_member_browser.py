"""Owner/Roommate 2 acceptance against the existing, marked local sandbox only.

Session fixtures use the sandbox signing key; passwords/subscriptions are never changed.
All financial writes create uniquely named QA records, never edit pre-existing records.
"""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
WEB = 'http://127.0.0.1:5186'
API = 'http://127.0.0.1:8796'


def serve():
    from scripts.local_family_test import Sandbox, ROOT as SANDBOX_ROOT, load_settings
    import uvicorn
    app = Sandbox(SANDBOX_ROOT, load_settings()).prepare_app()
    uvicorn.run(app, host='127.0.0.1', port=8796, log_level='warning')


def sessions():
    from scripts.local_family_test import Sandbox, ROOT as SANDBOX_ROOT, load_settings
    from app.models.user import User
    from app.core.security import make_token
    from app.services.subscriptions import entitlement
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    settings = load_settings()
    sandbox = Sandbox(SANDBOX_ROOT, settings)
    settings.JWT_SECRET = sandbox.manifest()['jwt_secret']
    engine = sandbox.engine()
    result = []
    with Session(engine) as db:
        for email in ['family-owner@maxbud.example.com', 'roommate2@maxbud.example.com']:
            user = db.scalar(select(User).where(User.email == email))
            assert user and user.is_active and user.onboarding_completed
            assert entitlement(db, user)['household_allowed'], 'Existing local test entitlement must be active; use the private grant CLI to renew.'
            result.append({'token': make_token(user.id), 'user': {'id': user.id, 'full_name': user.full_name, 'email': user.email, 'role': user.role}, 'onboarding_completed': True})
    engine.dispose()
    return result


def run(inspect=False):
    from playwright.sync_api import sync_playwright, expect
    from core_flow_browser import stop
    people = sessions()
    env = os.environ | {'PYTHONPATH': str(ROOT / 'backend'), 'PYTHONDONTWRITEBYTECODE': '1', 'VITE_API_URL': '', 'VITE_BACKEND_URL': '', 'VITE_GOOGLE_CLIENT_ID': '', 'API_PROXY_TARGET': API}
    backend = frontend = None
    with open('/tmp/maxbud-member-services.log', 'w+') as log:
        try:
            backend = subprocess.Popen([sys.executable, __file__, '--serve'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log, start_new_session=True)
            frontend = subprocess.Popen(['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5186', '--strictPort'], cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, start_new_session=True)
            with sync_playwright() as pw:
                request = pw.request.new_context()
                for _ in range(100):
                    try:
                        if request.get(WEB + '/api/health', timeout=1000).ok:
                            break
                    except Exception:
                        pass
                    assert backend.poll() is None and frontend.poll() is None, 'Test server exited'
                    time.sleep(.2)
                else:
                    raise AssertionError('Test server readiness timeout')
                browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox'])
                pages = []
                errors = []
                next_request_at = 0
                def pace(route):
                    # Respect the real per-IP limit instead of disabling it.
                    nonlocal next_request_at
                    time.sleep(max(0, next_request_at - time.monotonic()))
                    next_request_at = time.monotonic() + .35
                    route.continue_()
                for person in people:
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    context.route('**/api/**', pace)
                    context.add_init_script('sessionStorage.setItem("maxbud_auth", ' + json.dumps(json.dumps(person)) + ');')
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(WEB + '/dashboard/family', wait_until='domcontentloaded')
                    expect(page.get_by_role('heading', name='Family Management', exact=True)).to_be_visible()
                    expect(page.get_by_text('Loading family membership…', exact=True)).not_to_be_visible(timeout=30000)
                    pages.append(page)
                if inspect:
                    for role, page in zip(['owner', 'member'], pages):
                        if '--inspect-after' in sys.argv:
                            expect(page.get_by_text('You can record shared income and expenses, fund wallets, contribute to goals and repay your own split obligations.', exact=True)).to_be_visible()
                        page.screenshot(path=f'/tmp/maxbud-member-{'after' if '--inspect-after' in sys.argv else 'before'}-{role}.png', full_page=True)
                        print(role, page.locator('main').inner_text(), flush=True)
                    pages[1].goto(WEB + '/dashboard?scope=family', wait_until='domcontentloaded')
                    pages[1].get_by_role('link', name='Manage goals', exact=False).click()
                    print('CURRENT Manage goals destination:', pages[1].url, flush=True)
                else:
                    verify(request, pages, people, expect)
                assert not errors, errors
                browser.close()
        finally:
            stop(frontend)
            stop(backend)


def verify(request, pages, people, expect):
    import app.main  # Register every ledger model for pre-existing-row checks; no lifespan runs.
    from decimal import Decimal
    from scripts.local_family_test import Sandbox, ROOT as SANDBOX_ROOT, load_settings
    from sqlalchemy import select
    from app.database import Base
    owner, member = pages
    tag = 'UX QA ' + uuid4().hex[:8]
    print('QA record prefix:', tag, flush=True)
    sandbox = Sandbox(SANDBOX_ROOT, load_settings())
    engine = sandbox.engine()
    financial_tables = [table for table in Base.metadata.sorted_tables if table.name in {
        'accounts', 'transactions', 'budgets', 'goals', 'goal_contributions',
        'account_transfer_records', 'household_expense_shares', 'household_settlements', 'payment_reminders', 'reminder_payments'}]
    assert len(financial_tables) == 10, 'All financial tables must be included in preservation checks'
    with engine.connect() as db:
        baseline = {table.name: {row.id: tuple(row) for row in db.execute(select(table))} for table in financial_tables}

    def api(person, path, data=None, method=None, status=200):
        response = request.fetch(WEB + '/api' + path, method=method or ('POST' if data is not None else 'GET'),
                                 headers={'Authorization': 'Bearer ' + people[person]['token']}, data=data)
        assert response.status == status, (path, response.status, response.text())
        return response.json()

    def go(page, section):
        page.get_by_role('navigation', name='Shared household sections').get_by_role('link', name={
            'overview': 'Shared household', 'wallets': 'Shared wallets', 'income': 'Shared income',
            'expenses': 'Shared expenses & splitting', 'budgets': 'Shared budgets', 'goals': 'Shared goals',
            'reimbursements': 'Reimbursements', 'reports': 'Shared reports', 'bills': 'Household bills', 'members': 'Household membership'}[section], exact=True).click()
        assert page.url.endswith('/family' if section == 'overview' else '/family/' + section)
        expect(page.get_by_text('Loading shared finances…', exact=True)).not_to_be_visible()

    def card(page, name):
        return page.locator('article').filter(has=page.get_by_role('heading', name=name, exact=True))

    def save(page, path, button='Save shared record', method='POST'):
        with page.expect_response(lambda response: response.url.split('?')[0].endswith(path) and response.request.method == method) as result:
            page.get_by_role('dialog').get_by_role('button', name=button, exact=True).click()
        assert result.value.ok, (path, result.value.status, result.value.text())
        body = result.value.json()
        expect(page.get_by_role('dialog')).not_to_be_visible()
        return body

    def refresh(page):
        page.reload(wait_until='domcontentloaded')
        expect(page.get_by_text('Loading family membership…', exact=True)).not_to_be_visible()
        expect(page.get_by_text('Loading shared finances…', exact=True)).not_to_be_visible()

    owner_account = api(0, '/accounts', {'name': tag + ' Owner private', 'kind': 'cash', 'opening_balance': '5000'}, status=201)
    member_account = api(1, '/accounts', {'name': tag + ' Roommate private', 'kind': 'cash', 'opening_balance': '5000'}, status=201)
    before_report = api(0, '/dashboard?scope=family')
    member_name = people[1]['user']['full_name']
    if '--finance-only' in sys.argv:
        # Run remaining flows independently after navigation/goals have passed.
        goal_id = api(0, '/goals?scope=family', {'name': tag + ' Goal', 'target_amount': '1000'}, status=201)['id']
    else:
        for page in pages:
            for label, section in [('Manage Goals', 'goals'), ('Manage Wallets', 'wallets'), ('View Shared Budget', 'budgets'), ('Shared Reports', 'reports')]:
                go(page, 'overview')
                page.get_by_role('link', name=label, exact=True).click()
                assert page.url.endswith('/family/' + section)
                refresh(page)
        member.goto(WEB + '/dashboard?scope=family', wait_until='domcontentloaded')
        member.get_by_role('link', name='Manage goals', exact=False).click()
        assert member.url.endswith('/family/goals')
        print('PASS navigation: task links and dashboard Manage goals open exact shared routes, retained on refresh', flush=True)

        go(owner, 'goals')
        owner.get_by_role('button', name='New shared goal', exact=True).click()
        owner.get_by_label('Goal name', exact=True).fill(tag + ' Goal')
        owner.get_by_label('Target amount (LKR)', exact=True).fill('1000')
        goal = save(owner, '/goals', 'Save shared goal')
        goal_id = goal['id']
        for page, amount in [(member, '200'), (owner, '300')]:
            refresh(page)
            page.get_by_role('button', name='Contribute to ' + tag + ' Goal', exact=True).click()
            page.get_by_label('Contribution amount (LKR)', exact=True).fill(amount)
            save(page, f'/goals/{goal_id}/contribute', 'Record contribution')
        for page in pages:
            refresh(page)
            goal_card = card(page, tag + ' Goal')
            expect(goal_card.locator('.family-goal-numbers strong').first).to_have_text(re.compile(r'LKR\s*500(?:\.00)?$'))
            goal_card.locator('summary').filter(has_text='Contribution history').click()
            expect(goal_card.locator('tbody')).to_contain_text(member_name)
            expect(goal_card.locator('tbody')).to_contain_text(re.compile(r'LKR\s*200(?:\.00)?'))
        assert api(0, '/accounts/' + str(owner_account['id']))['current_balance'] == '5000.00'
        assert api(1, '/accounts/' + str(member_account['id']))['current_balance'] == '5000.00'
        expect(member.get_by_role('button', name='New shared goal', exact=True)).to_have_count(0)
        expect(member.get_by_role('button', name='Edit ' + tag + ' Goal', exact=True)).to_have_count(0)
        goal_card = card(owner, tag + ' Goal')
        goal_card.locator('summary').filter(has_text='Manage goal').click()
        goal_card.get_by_role('button', name='Edit ' + tag + ' Goal', exact=True).click()
        owner.get_by_label('Target amount (LKR)', exact=True).fill('1200')
        save(owner, f'/goals/{goal_id}', 'Save shared goal', 'PUT')
        for action in ['Archive', 'Restore']:
            goal_card = card(owner, tag + ' Goal')
            if not goal_card.get_by_role('button', name=action + ' ' + tag + ' Goal', exact=True).is_visible():
                goal_card.locator('summary').filter(has_text='Manage goal').click()
            with owner.expect_response(lambda response: response.url.endswith(f'/goals/{goal_id}') and response.request.method == 'PATCH') as result:
                goal_card.get_by_role('button', name=action + ' ' + tag + ' Goal', exact=True).click()
            assert result.value.ok
            expect(goal_card).to_contain_text('archived' if action == 'Archive' else 'active')
        refresh(member)
        assert next(row for row in api(1, '/goals?scope=family') if row['id'] == goal_id)['saved_amount'] == '500.00'
        print('PASS goals: member 200 + owner 300, identity/history/persistence/private balances, owner edit/archive/restore', flush=True)

    go(owner, 'wallets')
    owner.get_by_role('button', name='New shared wallet', exact=True).click()
    owner.get_by_role('dialog').get_by_label('Name', exact=True).fill(tag + ' Wallet')
    wallet = save(owner, '/family/wallets')
    wallet_id = wallet['id']
    for page, person, account, amount in [(owner, 0, owner_account, '1000'), (member, 1, member_account, '500')]:
        go(page, 'wallets')
        refresh(page)
        card(page, tag + ' Wallet').get_by_role('button', name='Contribute to wallet', exact=True).click()
        page.get_by_label('Amount (LKR)', exact=True).fill(amount)
        page.get_by_label('Payment account', exact=True).select_option(str(account['id']))
        save(page, f'/family/wallets/{wallet_id}/contribute')
        refresh(page)
    expect(card(member, tag + ' Wallet').locator('strong').first).to_have_text(re.compile(r'LKR\s*1,500(?:\.00)?$'))
    expect(member.get_by_role('button', name='New shared wallet', exact=True)).to_have_count(0)
    wallet_card = card(owner, tag + ' Wallet')
    wallet_card.locator('summary').filter(has_text='Manage wallet').click()
    wallet_card.get_by_role('button', name='Rename', exact=True).click()
    owner.get_by_role('dialog').get_by_label('Name', exact=True).fill(tag + ' Shared wallet')
    save(owner, f'/family/wallets/{wallet_id}', method='PATCH')
    for action in ['Archive', 'Restore']:
        wallet_card = card(owner, tag + ' Shared wallet')
        expect(wallet_card).to_be_visible()
        if not wallet_card.get_by_role('button', name=action, exact=True).is_visible():
            wallet_card.locator('summary').filter(has_text='Manage wallet').click()
        with owner.expect_response(lambda response: response.url.endswith(f'/family/wallets/{wallet_id}/archive')) as result:
            wallet_card.get_by_role('button', name=action, exact=True).click()
        assert result.value.ok
        expect(wallet_card.get_by_role('button', name='Contribute to wallet', exact=True)).to_be_disabled() if action == 'Archive' else expect(wallet_card.get_by_role('button', name='Contribute to wallet', exact=True)).to_be_enabled()
    print('PASS wallets: owner/member funding, persisted balance, owner rename/archive/restore, member administration hidden', flush=True)

    for page, person, amount in [(owner, 0, '400'), (member, 1, '300')]:
        go(page, 'income')
        page.get_by_role('button', name='Add shared income', exact=True).click()
        page.get_by_label('Amount (LKR)', exact=True).fill(amount)
        page.get_by_label('Income wallet', exact=True).select_option(str(wallet_id))
        page.get_by_label('Shared note', exact=True).fill(tag + f' Income {person}')
        save(page, '/family/income')
        refresh(page)
        expect(page.get_by_role('cell', name=tag + f' Income {person}', exact=True)).to_be_visible()

    go(owner, 'budgets')
    owner.get_by_role('button', name='New shared budget', exact=True).click()
    owner.get_by_label('Category', exact=True).fill(tag + ' Food')
    owner.get_by_label('Monthly limit (LKR)', exact=True).fill('2000')
    budget = save(owner, '/family/budgets')
    budget_id = budget['id']
    budget_card = card(owner, tag + ' Food')
    budget_card.locator('summary').filter(has_text='Manage budget limit').click()
    budget_card.get_by_role('button', name='Edit budget', exact=True).click()
    owner.get_by_label('Monthly limit (LKR)', exact=True).fill('2500')
    save(owner, f'/family/budgets/{budget_id}', method='PUT')

    go(owner, 'expenses')
    owner.get_by_role('button', name='Add shared expense', exact=True).click()
    owner.get_by_label('Amount (LKR)', exact=True).fill('300')
    owner.get_by_label('Category', exact=True).fill(tag + ' Food')
    owner.get_by_label('Shared note', exact=True).fill(tag + ' Split meal')
    owner.get_by_label('Agreed split', exact=True).select_option('equal')
    owner.get_by_label('Payment account', exact=True).select_option(str(owner_account['id']))
    for name in [people[0]['user']['full_name'], member_name]:
        owner.get_by_role('dialog').get_by_label(name, exact=True).check()
    split_expense = save(owner, '/family/expenses')
    go(member, 'expenses')
    member.get_by_role('button', name='Add shared expense', exact=True).click()
    member.get_by_label('Amount (LKR)', exact=True).fill('120')
    member.get_by_label('Category', exact=True).fill(tag + ' Food')
    member.get_by_label('Shared note', exact=True).fill(tag + ' Shared groceries')
    member.get_by_label('Payment account', exact=True).select_option(str(wallet_id))
    save(member, '/family/expenses')
    refresh(member)
    expect(member.get_by_role('row').filter(has_text=tag + ' Shared groceries')).to_contain_text(member_name)
    for page in pages:
        go(page, 'budgets')
        expect(card(page, tag + ' Food')).to_contain_text(re.compile(r'LKR\s*420(?:\.00)?'))
        expect(card(page, tag + ' Food')).to_contain_text(re.compile(r'LKR\s*2,080(?:\.00)?'))
    expect(member.get_by_role('button', name='New shared budget', exact=True)).to_have_count(0)
    print('PASS income/expenses/budgets: both enter income; owner splits personal expense; member pays shared expense; limits/spending persist for both', flush=True)

    debt = next(row for row in api(1, '/family/reimbursements') if row['expense_id'] == split_expense['id'])
    assert debt['debtor_id'] == people[1]['user']['id'] and Decimal(debt['remaining']) == 150
    go(member, 'reimbursements')
    for amount, remaining in [('50', '100.00'), ('100', '0.00')]:
        debt_card = member.locator('article').filter(has=member.get_by_text('Expense #' + str(split_expense['id']), exact=True))
        debt_card.get_by_role('button', name='Record partial or full settlement', exact=True).click()
        member.get_by_label('Amount (LKR)', exact=True).fill(amount)
        member.get_by_label('Payment account', exact=True).select_option(str(member_account['id']))
        save(member, f"/family/reimbursements/{debt['share_id']}/settle")
        refresh(member)
        expect(debt_card).to_contain_text('Outstanding:')
        actual = next(row for row in api(1, '/family/reimbursements') if row['share_id'] == debt['share_id'])
        assert Decimal(actual['remaining']) == Decimal(remaining)
    go(owner, 'reimbursements')
    expect(owner.locator('article').filter(has=owner.get_by_text('Expense #' + str(split_expense['id']), exact=True))).to_contain_text(re.compile(r'LKR\s*150(?:\.00)?'))
    print('PASS reimbursements: own debt only, partial 50 and full 100 persist, both see settled obligation', flush=True)

    go(owner, 'bills')
    owner.get_by_role('button', name='New household bill', exact=True).click()
    owner.get_by_role('dialog').get_by_label('Name', exact=True).fill(tag + ' Bill')
    owner.get_by_label('Category', exact=True).fill(tag + ' Food')
    owner.get_by_label('Amount (LKR)', exact=True).fill('50')
    owner.get_by_label('Payment account', exact=True).select_option(str(wallet_id))
    owner.get_by_label('Repeat', exact=True).select_option('none')
    bill = save(owner, '/family/bills')
    go(member, 'bills')
    with member.expect_response(lambda response: response.url.endswith(f"/family/bills/{bill['id']}/pay")) as result:
        card(member, tag + ' Bill').get_by_role('button', name='Mark household bill paid', exact=True).click()
    assert result.value.ok
    refresh(member)
    expect(card(member, tag + ' Bill')).to_have_count(0)
    expect(member.get_by_role('button', name='New household bill', exact=True)).to_have_count(0)

    report = api(0, '/dashboard?scope=family')
    assert Decimal(report['monthly_income']) - Decimal(before_report['monthly_income']) == 700
    assert Decimal(report['monthly_expenses']) - Decimal(before_report['monthly_expenses']) == 470
    assert Decimal(report['monthly_wallet_funding']) - Decimal(before_report['monthly_wallet_funding']) == 1500
    assert Decimal(report['total_balance']) - Decimal(before_report['total_balance']) == 2030
    for page in pages:
        go(page, 'reports')
        refresh(page)
        expect(page.get_by_role('heading', name='Shared reports', exact=True)).to_be_visible()
        expect(page.locator('main')).not_to_contain_text(tag + ' Owner private')
        expect(page.locator('main')).not_to_contain_text(tag + ' Roommate private')
    assert all(row['id'] != owner_account['id'] for row in api(1, '/accounts')['items'])
    assert all(row['id'] != member_account['id'] for row in api(0, '/accounts')['items'])
    api(1, '/accounts/' + str(owner_account['id']), status=404)
    api(0, '/accounts/' + str(member_account['id']), status=404)
    for path, data, method in [('/family/wallets', {'name': tag + ' Forbidden'}, 'POST'),
                              (f'/family/wallets/{wallet_id}', {'name': 'Forbidden'}, 'PATCH'),
                              (f'/family/budgets/{budget_id}', {'category': tag + ' Food', 'monthly_limit': '1'}, 'PUT'),
                              (f'/goals/{goal_id}', {'name': 'Forbidden', 'target_amount': '1200'}, 'PUT')]:
        api(1, path, data, method, status=403)
    api(0, f"/family/reimbursements/{debt['share_id']}/settle", {'account_id': owner_account['id'], 'amount': '1', 'request_id': uuid4().hex}, status=403)
    go(member, 'members')
    expect(member.get_by_role('button', name='Create secure invitation', exact=True)).to_have_count(0)
    expect(member.get_by_role('button', name='Remove', exact=False)).to_have_count(0)

    # Permission denial checks restore the exact original membership even on failure.
    members = api(0, '/family/members')
    original = next(row for row in members if row['id'] == people[1]['user']['id'])
    permission_path = f"/family/members/{people[1]['user']['id']}/permissions"
    try:
        go(owner, 'members')
        with owner.expect_response(lambda response: response.url.endswith(permission_path) and response.request.method == 'PATCH') as result:
            owner.get_by_label('Allow shared editing for ' + member_name, exact=True).uncheck()
        assert result.value.ok
        refresh(owner)
        expect(owner.get_by_label('Allow shared editing for ' + member_name, exact=True)).not_to_be_checked()
        go(member, 'goals')
        refresh(member)
        expect(member.get_by_role('button', name='Contribute to ' + tag + ' Goal', exact=True)).to_be_disabled()
        expect(member.locator('main')).to_contain_text('owner’s shared editing permission')
        api(1, f'/goals/{goal_id}/contribute', {'amount': '1', 'request_id': uuid4().hex}, status=403)
        go(member, 'expenses')
        expect(member.get_by_role('button', name='Add shared expense', exact=True)).to_be_disabled()
        api(1, '/family/expenses', {'account_id': wallet_id, 'amount': '1', 'category': tag + ' Food', 'request_id': uuid4().hex}, status=403)
        for path, payload in [('/family/income', {'account_id': wallet_id, 'amount': '1', 'category': 'Forbidden', 'request_id': uuid4().hex}),
                              (f'/family/wallets/{wallet_id}/contribute', {'account_id': member_account['id'], 'amount': '1', 'request_id': uuid4().hex}),
                              (f"/family/reimbursements/{debt['share_id']}/settle", {'account_id': member_account['id'], 'amount': '1', 'request_id': uuid4().hex})]:
            api(1, path, payload, status=403)
        with owner.expect_response(lambda response: response.url.endswith(permission_path) and response.request.method == 'PATCH') as result:
            owner.get_by_label('Allow shared reports for ' + member_name, exact=True).uncheck()
        assert result.value.ok
        refresh(owner)
        expect(owner.get_by_label('Allow shared reports for ' + member_name, exact=True)).not_to_be_checked()
        go(member, 'reports')
        refresh(member)
        expect(member.locator('main')).to_contain_text('has not granted your account access')
        api(1, '/dashboard?scope=family', status=403)
    finally:
        api(0, permission_path, {'can_view_shared': original['can_view_shared'], 'can_add_shared': original['can_add_shared']}, 'PATCH')
    print('PASS authorization/privacy: member owner-only APIs forbidden; other personal accounts 404; view-only and no-view denied with accurate UI; original permissions restored', flush=True)

    # Exercise definition deletion only on this run's new budget, retaining all expenses.
    go(owner, 'budgets')
    budget_card = card(owner, tag + ' Food')
    budget_card.locator('summary').filter(has_text='Manage budget limit').click()
    owner.once('dialog', lambda dialog: dialog.accept())
    with owner.expect_response(lambda response: response.url.endswith(f'/family/budgets/{budget_id}') and response.request.method == 'DELETE') as result:
        budget_card.get_by_role('button', name='Delete budget', exact=True).click()
    assert result.value.ok
    refresh(owner)
    expect(card(owner, tag + ' Food')).to_have_count(0)
    assert any(row['id'] == split_expense['id'] for row in api(0, '/family/expenses'))
    with engine.connect() as db:
        for table in financial_tables:
            current = {row.id: tuple(row) for row in db.execute(select(table))}
            for key, values in baseline[table.name].items():
                assert current.get(key) == values, ('Pre-existing financial row changed', table.name, key)
    engine.dispose()
    for role, page in zip(['owner', 'member'], pages):
        go(page, 'overview')
        expect(page.get_by_text('You can record shared income and expenses, fund wallets, contribute to goals and repay your own split obligations.', exact=True)).to_be_visible()
        page.screenshot(path=f'/tmp/maxbud-member-after-{role}.png', full_page=True)
    print('PASS reports/accounting: income +700, expenses +470, funding +1500, wallet +2030; settlements create neither income nor expenses; ALL pre-existing financial rows unchanged', flush=True)


if __name__ == '__main__':
    serve() if '--serve' in sys.argv else run('--inspect' in sys.argv or '--inspect-after' in sys.argv)
