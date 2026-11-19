"""Opt-in real-schema MySQL verification with no committed test records or DDL.

Run from backend: PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/savings_transfers_mysql.py --run
Uses configured MySQL credentials without printing them. API commits release
savepoints inside one outer transaction; finally rolls that transaction back.
Existing row contents and table definitions are fingerprinted before/after.
"""
import argparse
from datetime import date
from decimal import Decimal
import hashlib
import re
import sys
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import make_token, session_version
from app.database import engine, get_db
from app.main import app
from app.models.finance import AccountTransfer, Goal, GoalContribution, Transaction
from app.models.user import User


TABLES = ('users', 'auth_identities', 'subscriptions', 'accounts', 'goals',
          'goal_contributions', 'account_transfer_records', 'transactions', 'budgets')


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def snapshot(connection):
    """Keep only digests/counts in memory; never output existing row contents."""
    result = {}
    for table in TABLES:
        quoted = connection.dialect.identifier_preparer.quote(table)
        ddl = connection.execute(text(f'SHOW CREATE TABLE {quoted}')).one()[1]
        # Rolled-back inserts can legitimately advance InnoDB ID counters.
        ddl = re.sub(r'\bAUTO_INCREMENT=\d+\s*', '', ddl)
        digest, count = hashlib.sha256(), 0
        for row in connection.execute(text(f'SELECT * FROM {quoted} ORDER BY id')):
            digest.update(repr(tuple(row)).encode('utf-8'))
            digest.update(b'\n')
            count += 1
        result[table] = (count, digest.hexdigest(), hashlib.sha256(ddl.encode('utf-8')).hexdigest())
    return result


def run():
    check(engine.dialect.name == 'mysql', 'This integration requires MySQL')
    tag = uuid4().hex
    emails = [f'maxbud-savings-verify-{tag}-{name}@example.com' for name in ('owner', 'other')]
    user_ids = []
    baseline = None
    # This connection alone owns every test write. No production lifespan runs.
    with engine.connect() as connection:
        outer = connection.begin()
        db = client = None
        previous_override = app.dependency_overrides.get(get_db)
        try:
            check(connection.execute(text('SELECT COUNT(*) FROM information_schema.TRIGGERS '
                  'WHERE TRIGGER_SCHEMA=DATABASE()')).scalar() == 0,
                  'Review schema triggers before running rollback-only integration')
            for table in TABLES:
                storage = connection.execute(text('SELECT ENGINE FROM information_schema.TABLES '
                    'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:name'), {'name': table}).scalar()
                check(storage == 'InnoDB', f'{table} must exist and use InnoDB')
            baseline = snapshot(connection)
            db = Session(connection, expire_on_commit=False, autoflush=False,
                         join_transaction_mode='create_savepoint')
            app.dependency_overrides[get_db] = lambda: db
            client = TestClient(app)
            # No external mail, AI or billing endpoints are invoked.
            with patch.object(get_settings(), 'RATE_LIMIT_ENABLED', False):
                def api(method, path, payload=None, person=None, expected=200):
                    headers = {'Authorization': 'Bearer ' + person['access_token']} if person else {}
                    response = client.request(method, path, json=payload, headers=headers)
                    check(outer.is_active, 'An API request escaped the outer transaction')
                    check(response.status_code == expected,
                          f'{method} {path}: expected HTTP {expected}, got {response.status_code}')
                    return response.json() if response.content else None

                # Exercise real pre-existing data too: synthetic, valid goals
                # alone cannot catch serialization failures in legacy records.
                existing_users = db.scalars(select(User).join(Goal, Goal.user_id == User.id)
                    .where(User.is_active.is_(True), Goal.family_id.is_(None)).distinct()).all()
                existing_count = 0
                for user in existing_users:
                    person = {'access_token': make_token(user.id, session_version(db, user.id))}
                    expected = {row.id: row.saved_amount for row in db.scalars(select(Goal).where(
                        Goal.user_id == user.id, Goal.family_id.is_(None)))}
                    for _ in range(3):
                        rows = api('GET', '/goals', person=person)
                        check({row['id']: Decimal(row['saved_amount']) for row in rows} == expected,
                              'Existing goal listing omitted or changed recorded savings')
                    existing_count += len(expected)
                print(f'PASS: repeated GET /goals for {existing_count} existing goals '
                      f'across {len(existing_users)} active owners', flush=True)

                people = []
                for email in emails:
                    person = api('POST', '/auth/register', {
                        'full_name': 'Isolated Savings Verification', 'email': email,
                        'password': 'Verify1!' + tag, 'confirm_password': 'Verify1!' + tag,
                    }, expected=201)
                    people.append(person)
                    user_ids.append(person['user']['id'])
                owner, other = people
                source = api('POST', '/accounts', {'name': 'Isolated savings source', 'kind': 'bank',
                    'opening_balance': '1000'}, owner, 201)['id']
                foreign = api('POST', '/accounts', {'name': 'Isolated other source', 'kind': 'cash',
                    'opening_balance': '77'}, other, 201)['id']
                goal = api('POST', '/goals', {'name': 'Isolated verification goal',
                    'target_amount': '5000', 'saved_amount': '125'}, owner, 201)['id']
                api('POST', '/budgets', {'category': 'Food', 'monthly_limit': '100'}, owner, 201)
                for kind, amount, category in [('income', '50', 'Salary'), ('expense', '20', 'Food')]:
                    api('POST', '/transactions', {'account_id': source, 'kind': kind,
                        'category': category, 'amount': amount}, owner, 201)

                def balance():
                    return Decimal(api('GET', f'/accounts/{source}', person=owner)['current_balance'])

                def records(model):
                    return db.scalars(select(model).where(model.user_id == user_ids[0])).all()

                def financial_snapshot():
                    dashboard = api('GET', '/dashboard?include_cash_flow=true', person=owner)
                    accounts = api('GET', '/accounts', person=owner)
                    check(Decimal(accounts['total_balance']) == Decimal(dashboard['total_balance']),
                          'Account and dashboard asset totals disagree')
                    return {
                        'assets': dashboard['total_balance'], 'income': dashboard['monthly_income'],
                        'expense': dashboard['monthly_expenses'], 'net': dashboard['monthly_net_cash_flow'],
                        'cash_flow': {key: dashboard['cash_flow'][key] for key in
                                      ('income', 'expense', 'net_cash_flow', 'closing_balance')},
                        'budgets': dashboard['budgets'],
                    }

                before = financial_snapshot()
                check(balance() == Decimal('1030'), 'Unexpected source opening ledger balance')
                payload = {'account_id': source, 'amount': '125.50', 'request_id': str(uuid4())}
                result = api('POST', f'/goals/{goal}/contribute', payload, owner)
                check(balance() == Decimal('904.50'), 'Source was not debited exactly once')
                check(Decimal(result['saved_amount']) == Decimal('250.50'), 'Goal was not credited')
                check(Decimal(result['account_backed_amount']) == Decimal('125.50'), 'Funded balance incorrect')
                check(Decimal(result['legacy_allocated_amount']) == Decimal('125'), 'Legacy allocation changed')
                transfers, contributions = records(AccountTransfer), records(GoalContribution)
                check(len(transfers) == len(contributions) == 1, 'Missing or duplicate linked ledger record')
                transfer, contribution = transfers[0], contributions[0]
                entries = [row for row in records(Transaction) if row.transfer_id == transfer.id]
                check(len(entries) == 2 and {row.kind for row in entries} == {'transfer_in', 'transfer_out'},
                      'Savings transfer must have two internal ledger entries')
                check(transfer.client_request_id == f'goal:{contribution.id}', 'Contribution link missing')
                check(transfer.from_account_id == source and all(row.amount == Decimal('125.50') for row in entries),
                      'Transfer source or amounts incorrect')
                history = api('GET', '/goals/transfers', person=owner)
                check(len(history) == 1 and history[0]['source_account_id'] == source
                      and history[0]['goal_id'] == goal and history[0]['txn_date'] == date.today().isoformat(),
                      'Savings transfer missing from transaction history')
                check(len(api('GET', '/transactions?kind=transfer_out', person=owner)) == 1,
                      'Transfer-out entry missing from transaction ledger')
                check(len(api('GET', '/transactions', person=owner)) == 2,
                      'Internal savings transfer counted as normal income/expense')
                check(financial_snapshot() == before, 'Assets, income, expense, budgets or cash flow changed')
                print('PASS: real MySQL debit/goal credit, linked history, preserved legacy allocation, '
                      'unchanged tracked wealth/income/expense/budgets/cash flow', flush=True)

                api('POST', f'/goals/{goal}/contribute', payload, owner)
                api('POST', f'/goals/{goal}/contribute', payload | {'amount': '1'}, owner, 409)
                for amount, expected in [('2000', 409), ('0', 422), ('-1', 422)]:
                    api('POST', f'/goals/{goal}/contribute', payload | {
                        'amount': amount, 'request_id': str(uuid4())}, owner, expected)
                api('POST', f'/goals/{goal}/contribute', payload | {
                    'account_id': foreign, 'request_id': str(uuid4())}, owner, 404)
                check(balance() == Decimal('904.50') and len(records(AccountTransfer)) == 1,
                      'Retries or rejected transfers changed balances/records')
                # Verify the actual MySQL unique constraints inside nested savepoints.
                for duplicate in [
                    GoalContribution(user_id=user_ids[0], current_goal_id=goal,
                        request_id=payload['request_id'], amount=Decimal('125.50')),
                    AccountTransfer(user_id=user_ids[0], from_account_id=source,
                        to_account_id=transfer.to_account_id, amount=Decimal('125.50'), currency='LKR',
                        txn_date=date.today(), client_request_id=transfer.client_request_id),
                ]:
                    rejected = False
                    try:
                        with db.begin_nested():
                            db.add(duplicate)
                            db.flush()
                    except IntegrityError as exc:
                        check(getattr(exc.orig, 'args', (None,))[0] == 1062,
                              'Expected a MySQL duplicate-key error, not another integrity failure')
                        rejected = True
                    check(rejected and outer.is_active, 'MySQL duplicate constraint failed')
                print('PASS: retry idempotency, conflicting keys, MySQL uniqueness, overdraft/nonpositive '
                      'and foreign-account rejection', flush=True)

                reverse_path = f'/goals/{goal}/contributions/{contribution.id}/reverse'
                api('POST', reverse_path, person=other, expected=404)
                result = api('POST', reverse_path, person=owner)
                check(balance() == Decimal('1030') and Decimal(result['saved_amount']) == Decimal('125'),
                      'Reversal did not restore source/goal')
                check(Decimal(result['account_backed_amount']) == 0, 'Reversed funds remain allocated')
                api('POST', reverse_path, person=owner, expected=409)
                api('POST', f'/goals/{goal}/contribute', payload, owner)
                check(len(records(AccountTransfer)) == 2 and len(records(GoalContribution)) == 1
                      and len(records(Transaction)) == 6,
                      'Reversal/replay produced extra records')
                check(api('GET', '/goals/transfers', person=owner)[0]['status'] == 'reversed',
                      'Reversal not shown in history')
                check(balance() == Decimal('1030') and financial_snapshot() == before,
                      'Reversal/replay changed assets, source or income/expense')
                print('PASS: reversal, preserved original history, double-reversal prevention and '
                      'original-request replay after reversal', flush=True)

                from app.services.personal_savings import post_transfer
                def fail_after_post(*args, **kwargs):
                    post_transfer(*args, **kwargs)
                    raise RuntimeError('isolated injected failure')
                failed = False
                with patch('app.services.personal_savings.post_transfer', side_effect=fail_after_post):
                    try:
                        api('POST', f'/goals/{goal}/contribute', payload | {'request_id': str(uuid4())}, owner)
                    except RuntimeError as exc:
                        check(str(exc) == 'isolated injected failure', 'Unexpected failure type')
                        failed = True
                check(failed and outer.is_active, 'Failure injection did not exercise rollback')
                check(balance() == Decimal('1030') and len(records(AccountTransfer)) == 2
                      and len(records(GoalContribution)) == 1 and len(records(Transaction)) == 6,
                      'Failure left a partial debit/contribution/transfer')
                check(financial_snapshot() == before, 'Failed transfer changed tracked wealth or reports')
                check(Decimal(api('GET', '/goals', person=owner)[0]['saved_amount']) == Decimal('125'),
                      'Failed transfer changed goal saved amount')
                with engine.connect() as observer:
                    visible = observer.execute(text('SELECT COUNT(*) FROM users WHERE email IN (:one,:two)'),
                                               {'one': emails[0], 'two': emails[1]}).scalar()
                    check(visible == 0, 'Test records became visible outside the outer transaction')
                print('PASS: atomic rollback after actual ledger writes; fixtures invisible to other connections', flush=True)
        finally:
            if client is not None:
                client.close()
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
            if db is not None:
                db.close()
            if outer.is_active:
                outer.rollback()
            # Check cleanup even if a preceding assertion raised.
            if baseline is not None:
                check(snapshot(connection) == baseline,
                      'Post-rollback row/schema fingerprints differ; inspect concurrent application changes')
                print('PASS: safe cleanup; existing row counts/content and table definitions unchanged', flush=True)
    print('REAL_MYSQL_INTEGRATION=PASS (rollback-isolated actual configured schema)', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', required=True,
                        help='Explicitly authorize rollback-isolated tests in configured MySQL')
    parser.parse_args()
    try:
        run()
    except SQLAlchemyError as exc:
        original = getattr(exc, 'orig', None)
        code = original.args[0] if original is not None and original.args else type(exc).__name__
        print(f'REAL_MYSQL_INTEGRATION=FAIL (database error code {code}; credentials/parameters suppressed)', flush=True)
        sys.exit(1)
    except Exception as exc:
        # Only our assertion messages are safe to print; never dump tokens or SQL.
        detail = str(exc) if isinstance(exc, AssertionError) else type(exc).__name__
        print(f'REAL_MYSQL_INTEGRATION=FAIL ({detail})', flush=True)
        sys.exit(1)
    finally:
        engine.dispose()
