"""Read-only personal ledger report. No inferred/demo records or money writes."""
from decimal import Decimal
from sqlalchemy import select
from app.models.finance import Transaction

ZERO = Decimal('0.00')
INCOMING = {'income', 'transfer_in'}
OUTGOING = {'expense', 'transfer_out'}


def monthly_cash_flow(db, user, accounts, first, next_first):
    # Accounts have no dated opening-balance field in the existing schema.
    # Explicitly use their recorded opening balances as the ledger baseline.
    # Include archived accounts so archiving cannot erase historical cash flow.
    names = {account.id: account.name for account in accounts}
    opening = sum((Decimal(account.opening_balance) for account in accounts), ZERO)
    statement = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.account_id.in_(names),
        Transaction.deleted_at.is_(None),
        Transaction.txn_date < next_first,
    ).order_by(Transaction.txn_date, Transaction.id)
    rows = []
    income = expense = ZERO
    running = opening
    for txn in db.scalars(statement):
        amount = Decimal(txn.amount)
        movement = amount if txn.kind in INCOMING else -amount if txn.kind in OUTGOING else ZERO
        if txn.txn_date < first:
            opening += movement
            running += movement
            continue
        running += movement
        is_income = txn.kind == 'income'
        is_expense = txn.kind == 'expense'
        if is_income: income += amount
        if is_expense: expense += amount
        rows.append({'id': txn.id, 'date': txn.txn_date.isoformat(),
                     'description': txn.description or txn.category,
                     'account': names[txn.account_id], 'kind': txn.kind,
                     'income': str(amount) if is_income else None,
                     'expense': str(amount) if is_expense else None,
                     'movement': str(movement), 'running_balance': str(running),
                     'shared_payment': txn.family_id is not None})
    return {'month': first.strftime('%Y-%m'), 'opening_balance': str(opening),
            'closing_balance': str(running), 'income': str(income), 'expense': str(expense),
            'net_cash_flow': str(income - expense),
            'balance_movement': str(running - opening), 'rows': rows,
            'basis': 'Combined personal accounts, including archived accounts. Recorded opening balances plus all earlier dated movements form the opening balance; account opening dates are not recorded. Includes shared expenses you paid personally. Household wallets are excluded. Transfers and reimbursements move balances but are not income or expenses. Savings allocations do not move account money.'}
