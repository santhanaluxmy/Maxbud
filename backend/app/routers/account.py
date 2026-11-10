from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.database import get_db
from app.models.finance import Account
from app.models.user import User
from app.schemas.account import (
    AccountArchive,
    AccountCreate,
    AccountListOut,
    AccountOut,
    AccountPatch,
    TransferCreate,
    TransferOut,
)
from app.services.account import (
    account_response,
    owned_account,
    record_transfer,
)

router = APIRouter(tags=["Accounts"])


@router.get("/accounts", response_model=AccountListOut)
def list_accounts(
    include_archived: bool = Query(default=True),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    accounts = db.scalars(
        select(Account)
        .where(Account.user_id == user.id)
        .order_by(Account.id)
    ).all()

    items = [
        account_response(db, account)
        for account in accounts
    ]

    # Archived assets remain part of the total balance.
    total = sum(
        (
            item.current_balance
            for item in items
            if item.currency == user.currency
        ),
        Decimal("0.00"),
    )

    return AccountListOut(
        items=[
            item
            for item in items
            if include_archived or not item.is_archived
        ],
        total_balance=total,
        currency=user.currency,
    )


@router.post(
    "/accounts",
    response_model=AccountOut,
    status_code=201,
)
def create_account(
    data: AccountCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    account = Account(
        user_id=user.id,
        currency=user.currency,
        is_archived=False,
        **data.model_dump(),
    )

    try:
        db.add(account)
        db.flush()

        result = account_response(db, account)
        db.commit()

        return result

    except Exception:
        db.rollback()
        raise


@router.get(
    "/accounts/{account_id}",
    response_model=AccountOut,
)
def get_account(
    account_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return account_response(
        db,
        owned_account(db, user, account_id),
    )


@router.patch(
    "/accounts/{account_id}",
    response_model=AccountOut,
)
def update_account(
    account_id: int,
    data: AccountPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        account = owned_account(
            db,
            user,
            account_id,
            lock=True,
        )

        for key, value in data.model_dump(
            exclude_unset=True,
        ).items():
            setattr(account, key, value)

        db.flush()
        result = account_response(db, account)
        db.commit()

        return result

    except Exception:
        db.rollback()
        raise


@router.post(
    "/accounts/{account_id}/archive",
    response_model=AccountOut,
)
def archive_account(
    account_id: int,
    data: AccountArchive | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    try:
        account = owned_account(
            db,
            user,
            account_id,
            lock=True,
        )

        account.is_archived = (
            True if data is None else data.archived
        )

        db.flush()
        result = account_response(db, account)
        db.commit()

        return result

    except Exception:
        db.rollback()
        raise


@router.post(
    "/transfers",
    response_model=TransferOut,
    status_code=201,
)
def create_transfer(
    data: TransferCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return record_transfer(db, user, data)