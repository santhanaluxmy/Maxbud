"""Account-backed personal savings, using the existing double-entry transfer ledger.

The reserved transfer keys link contributions without changing legacy rows/schema.
An archived, system-owned account holds savings assets: they remain in account
totals but cannot be spent through normal account/transaction APIs.
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import LargeBinary, String, cast, literal, select

from app.models.finance import Account, AccountTransfer, Goal, GoalContribution, Transaction
from app.models.user import now_utc
from app.services.account import account_balance, owned_account, usable_account

RESERVE_KIND = "goal_savings"


def transfer_key(contribution_id, reversal=False):
    # Normal account transfers accept UUIDs only, so cannot use this namespace.
    return f"{'goal-reversal' if reversal else 'goal'}:{contribution_id}"


def contribution_link():
    # MySQL may store the key in utf8mb4_unicode_ci while CAST(id AS CHAR)
    # uses the connection's utf8mb4_0900_ai_ci. Compare the ASCII keys as bytes
    # so the link works with either collation, without altering stored data.
    return (AccountTransfer.user_id == GoalContribution.user_id) & (
        cast(AccountTransfer.client_request_id, LargeBinary)
        == cast(literal("goal:") + cast(GoalContribution.id, String), LargeBinary)
    )


def backed_amount(db, goal, lock=True):
    statement = (select(GoalContribution.amount)
        .join(AccountTransfer, contribution_link())
        .where(GoalContribution.current_goal_id == goal.id,
               GoalContribution.user_id == goal.user_id,
               GoalContribution.reversed_at.is_(None)))
    # Writes must use current locking reads after waiting for the user/goal
    # locks, rather than MySQL REPEATABLE READ's earlier consistent snapshot.
    if lock:
        statement = statement.with_for_update()
    return sum(db.scalars(statement), Decimal("0.00"))


def has_backed_history(db, goal, lock=True):
    statement = (select(AccountTransfer.id).join(GoalContribution, contribution_link())
        .where(GoalContribution.current_goal_id == goal.id,
               GoalContribution.user_id == goal.user_id).limit(1))
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement) is not None


def post_transfer(db, user, source, destination, amount, key, description):
    """Post both entries in the caller's transaction; never commit here."""
    transfer = AccountTransfer(user_id=user.id, from_account_id=source.id,
        to_account_id=destination.id, amount=amount, currency=source.currency,
        txn_date=date.today(), description=description[:255], client_request_id=key)
    db.add(transfer)
    db.flush()
    for account, kind in ((source, "transfer_out"), (destination, "transfer_in")):
        db.add(Transaction(user_id=user.id, account_id=account.id, kind=kind,
            category="Savings transfer", amount=amount, txn_date=transfer.txn_date,
            description=description[:255], transfer_id=transfer.id))
    db.flush()
    return transfer


def contribute(db, user, goal, data):
    # The caller holds the user and goal locks, also serializing reserve creation.
    if not data.request_id or data.account_id is None:
        raise HTTPException(422, "Transfer From Account and a submission request_id are required")
    previous = db.scalar(select(GoalContribution).where(
        GoalContribution.user_id == user.id,
        GoalContribution.request_id == data.request_id).with_for_update())
    if previous is not None:
        transfer = db.scalar(select(AccountTransfer).where(
            AccountTransfer.user_id == user.id,
            AccountTransfer.client_request_id == transfer_key(previous.id)).with_for_update())
        if (previous.current_goal_id != goal.id or previous.amount != data.amount
                or transfer is None or transfer.from_account_id != data.account_id):
            raise HTTPException(409, "Contribution request_id was already used with different details")
        # A retry after completion, archiving or reversal must never debit again.
        return
    if goal.status != "active":
        raise HTTPException(409, "Only active goals accept contributions")
    if goal.saved_amount + data.amount > goal.target_amount:
        raise HTTPException(422, "Contribution exceeds the remaining goal amount")

    source = owned_account(db, user, data.account_id, lock=True)
    usable_account(source, user)
    other_currency = db.scalar(select(AccountTransfer.id).join(GoalContribution, contribution_link())
        .where(GoalContribution.current_goal_id == goal.id,
               GoalContribution.reversed_at.is_(None),
               AccountTransfer.currency != source.currency).limit(1).with_for_update())
    if other_currency is not None:
        raise HTTPException(422, "Reverse this goal's existing transfers before changing its currency")
    if account_balance(db, source, lock_entries=True) < data.amount:
        raise HTTPException(409, "Insufficient available balance in the source account")

    reserve = db.scalar(select(Account).where(Account.user_id == user.id,
        Account.family_id.is_(None), Account.kind == RESERVE_KIND,
        Account.currency == source.currency).with_for_update().execution_options(populate_existing=True))
    if reserve is None:
        reserve = Account(user_id=user.id, name="Goal savings reserve", kind=RESERVE_KIND,
            opening_balance=Decimal("0.00"), currency=source.currency, is_archived=True)
        db.add(reserve)
        db.flush()
    contribution = GoalContribution(current_goal_id=goal.id, user_id=user.id,
        request_id=data.request_id, amount=data.amount)
    db.add(contribution)
    db.flush()
    post_transfer(db, user, source, reserve, data.amount, transfer_key(contribution.id),
                  f"Savings transfer to {goal.name}")
    goal.saved_amount += data.amount
    if goal.saved_amount == goal.target_amount:
        goal.status = "completed"
    db.flush()


def reverse(db, user, goal, contribution_id):
    contribution = db.scalar(select(GoalContribution).where(
        GoalContribution.id == contribution_id, GoalContribution.current_goal_id == goal.id,
        GoalContribution.user_id == user.id).with_for_update().execution_options(populate_existing=True))
    transfer = db.scalar(select(AccountTransfer).where(AccountTransfer.user_id == user.id,
        AccountTransfer.client_request_id == transfer_key(contribution_id)).with_for_update())
    if contribution is None or transfer is None:
        raise HTTPException(404, "Account-backed savings transfer not found")
    if contribution.reversed_at is not None:
        raise HTTPException(409, "This savings transfer has already been reversed")
    accounts = {a.id: a for a in db.scalars(select(Account).where(
        Account.id.in_([transfer.from_account_id, transfer.to_account_id]),
        Account.user_id == user.id, Account.family_id.is_(None))
        .order_by(Account.id).with_for_update().execution_options(populate_existing=True))}
    source, reserve = accounts.get(transfer.from_account_id), accounts.get(transfer.to_account_id)
    if (source is None or reserve is None or reserve.kind != RESERVE_KIND
            or source.currency != transfer.currency or reserve.currency != transfer.currency
            or goal.saved_amount < contribution.amount
            or account_balance(db, reserve, lock_entries=True) < contribution.amount):
        raise HTTPException(409, "Savings ledger cannot be reversed consistently; contact support")
    # Append a compensating transfer: preserve the original transaction/date.
    # Refunds to archived source accounts remain allowed; they are still assets.
    post_transfer(db, user, reserve, source, contribution.amount,
        transfer_key(contribution.id, reversal=True), f"Savings transfer reversal: {goal.name}")
    contribution.reversed_at = now_utc()
    goal.saved_amount -= contribution.amount
    if goal.status == "completed":
        goal.status = "active"
    db.flush()


def history(db, user, limit, offset):
    rows = db.execute(select(GoalContribution, AccountTransfer, Goal, Account)
        .join(AccountTransfer, contribution_link())
        .join(Goal, Goal.id == GoalContribution.current_goal_id)
        .join(Account, Account.id == AccountTransfer.from_account_id)
        .where(GoalContribution.user_id == user.id, Goal.user_id == user.id,
               Goal.family_id.is_(None), Account.user_id == user.id,
               Account.family_id.is_(None))
        .order_by(AccountTransfer.id.desc()).limit(limit).offset(offset)).all()
    return [{"id": transfer.id, "contribution_id": contribution.id,
             "goal_id": goal.id, "goal_name": goal.name,
             "source_account_id": source.id, "source_account_name": source.name,
             "amount": str(transfer.amount), "currency": transfer.currency,
             "txn_date": transfer.txn_date, "reversed_at": contribution.reversed_at,
             "status": "reversed" if contribution.reversed_at else "completed"}
            for contribution, transfer, goal, source in rows]
