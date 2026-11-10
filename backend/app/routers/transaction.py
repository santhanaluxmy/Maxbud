from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.database import get_db
from app.models.finance import Account, Transaction
from app.models.user import User, now_utc
from app.schemas.transaction import TransactionIn, TransactionOut
from app.services.account import (
    account_balance,
    owned_account,
    usable_account,
)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
)


def find_account(
    db: Session,
    user: User,
    account_id: int,
) -> Account:
    account = owned_account(
        db,
        user,
        account_id,
        lock=True,
    )

    usable_account(account, user)

    return account


def find_transaction(
    db: Session,
    user: User,
    transaction_id: int,
    lock: bool = False,
) -> Transaction:
    statement = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.user_id == user.id,
        Transaction.deleted_at.is_(None),
    )

    if lock:
        statement = statement.with_for_update().execution_options(
            populate_existing=True,
        )

    transaction = db.scalar(statement)

    if transaction is None:
        raise HTTPException(404, "Transaction not found")

    return transaction


def available_balance(
    db: Session,
    account: Account,
    exclude_transaction_id: int | None = None,
) -> Decimal:
    return account_balance(
        db,
        account,
        exclude_transaction_id,
        lock_entries=True,
    )


def validate_expense_balance(
    db: Session,
    account: Account,
    data: TransactionIn,
    exclude_transaction_id: int | None = None,
) -> None:
    if (
        data.kind == "expense"
        and available_balance(
            db,
            account,
            exclude_transaction_id,
        ) < data.amount
    ):
        raise HTTPException(
            422,
            "Insufficient tracked account balance",
        )


def editable(transaction: Transaction) -> None:
    if transaction.transfer_id is not None:
        raise HTTPException(
            409,
            "A linked transfer entry cannot be edited or deleted separately",
        )


@router.post(
    "",
    response_model=TransactionOut,
    status_code=201,
)
def create_transaction(
    data: TransactionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        account = find_account(db, user, data.account_id)
        validate_expense_balance(db, account, data)

        transaction = Transaction(
            user_id=user.id,
            **data.model_dump(),
        )

        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    kind: Literal[
        "income",
        "expense",
        "transfer_in",
        "transfer_out",
    ] | None = None,
    category: str | None = None,
    account_id: int | None = Query(default=None, gt=0),
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            422,
            "start_date must be before end_date",
        )

    statement = select(Transaction).where(
        Transaction.user_id == user.id,
        Transaction.deleted_at.is_(None),
    )

    if account_id:
        owned_account(db, user, account_id)
        statement = statement.where(
            Transaction.account_id == account_id,
        )

    if kind:
        statement = statement.where(
            Transaction.kind == kind,
        )
    elif account_id is None:
        statement = statement.where(
            Transaction.kind.in_(["income", "expense"]),
        )

    if category and category.strip():
        statement = statement.where(
            func.lower(Transaction.category)
            == category.strip().lower(),
        )

    if start_date:
        statement = statement.where(
            Transaction.txn_date >= start_date,
        )

    if end_date:
        statement = statement.where(
            Transaction.txn_date <= end_date,
        )

    return db.scalars(
        statement
        .order_by(
            Transaction.txn_date.desc(),
            Transaction.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()


@router.get(
    "/{transaction_id}",
    response_model=TransactionOut,
)
def get_transaction(
    transaction_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return find_transaction(
        db,
        user,
        transaction_id,
    )


@router.put(
    "/{transaction_id}",
    response_model=TransactionOut,
)
def update_transaction(
    transaction_id: int,
    data: TransactionIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        initial = find_transaction(
            db,
            user,
            transaction_id,
        )
        editable(initial)

        locked_ids = sorted(
            {initial.account_id, data.account_id}
        )

        accounts = {
            key: owned_account(
                db,
                user,
                key,
                lock=True,
            )
            for key in locked_ids
        }

        transaction = find_transaction(
            db,
            user,
            transaction_id,
            lock=True,
        )
        editable(transaction)

        if transaction.account_id not in locked_ids:
            raise HTTPException(
                409,
                "Transaction changed; refresh and retry",
            )

        account = accounts[data.account_id]
        usable_account(account, user)

        validate_expense_balance(
            db,
            account,
            data,
            exclude_transaction_id=transaction_id,
        )

        for name, value in data.model_dump().items():
            setattr(transaction, name, value)

        db.commit()
        db.refresh(transaction)

        return transaction

    except Exception:
        db.rollback()
        raise


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        initial = find_transaction(
            db,
            user,
            transaction_id,
        )
        editable(initial)

        account_id = initial.account_id

        owned_account(
            db,
            user,
            account_id,
            lock=True,
        )

        transaction = find_transaction(
            db,
            user,
            transaction_id,
            lock=True,
        )
        editable(transaction)

        if transaction.account_id != account_id:
            raise HTTPException(
                409,
                "Transaction changed; refresh and retry",
            )

        # Preserve references from existing transaction audit records.
        transaction.deleted_at = now_utc()
        db.commit()

        return {
            "message": "Transaction deleted",
            "id": transaction_id,
        }

    except Exception:
        db.rollback()
        raise