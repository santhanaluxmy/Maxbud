from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.finance import Account, AccountTransfer, Transaction
from app.models.user import User
from app.schemas.account import AccountOut, TransferCreate, TransferOut

ZERO = Decimal("0.00")


def owned_account(
    db: Session,
    user: User,
    account_id: int,
    lock: bool = False,
) -> Account:
    statement = select(Account).where(
        Account.id == account_id,
        Account.user_id == user.id,
    )

    if lock:
        statement = statement.with_for_update().execution_options(
            populate_existing=True,
        )

    account = db.scalar(statement)

    if account is None:
        raise HTTPException(404, "Account not found")

    return account


def usable_account(account: Account, user: User) -> None:
    if account.is_archived:
        raise HTTPException(
            409,
            "Restore the archived account before adding entries",
        )

    if account.currency != user.currency:
        raise HTTPException(
            422,
            "Account currency must match your selected currency",
        )


def account_balance(
    db: Session,
    account: Account,
    exclude_transaction_id: int | None = None,
    lock_entries: bool = False,
) -> Decimal:
    statement = select(
        Transaction.kind,
        Transaction.amount,
    ).where(
        Transaction.user_id == account.user_id,
        Transaction.account_id == account.id,
        Transaction.deleted_at.is_(None),
    )

    if exclude_transaction_id is not None:
        statement = statement.where(
            Transaction.id != exclude_transaction_id,
        )

    if lock_entries:
        # Read current committed entries after waiting for an account lock.
        statement = statement.with_for_update()

    result = Decimal(account.opening_balance)

    for kind, amount in db.execute(statement):
        if kind in ("income", "transfer_in"):
            result += amount
        elif kind in ("expense", "transfer_out"):
            result -= amount

    return result.quantize(Decimal("0.01"))


def account_response(db: Session, account: Account) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        kind=account.kind,
        opening_balance=account.opening_balance,
        current_balance=account_balance(db, account),
        currency=account.currency,
        is_archived=account.is_archived,
        status="archived" if account.is_archived else "active",
    )


def transfer_response(
    db: Session,
    user: User,
    transfer: AccountTransfer,
) -> TransferOut:
    entry_ids = list(
        db.scalars(
            select(Transaction.id)
            .where(
                Transaction.user_id == user.id,
                Transaction.transfer_id == transfer.id,
            )
            .order_by(Transaction.id)
        )
    )

    return TransferOut(
        id=transfer.id,
        from_account_id=transfer.from_account_id,
        to_account_id=transfer.to_account_id,
        amount=transfer.amount,
        currency=transfer.currency,
        txn_date=transfer.txn_date,
        description=transfer.description,
        client_request_id=transfer.client_request_id,
        created_at=transfer.created_at,
        entry_ids=entry_ids,
    )


def record_transfer(
    db: Session,
    user: User,
    data: TransferCreate,
) -> TransferOut:
    try:
        # All ledger writers lock accounts in ascending ID order.
        accounts = {
            account_id: owned_account(
                db,
                user,
                account_id,
                lock=True,
            )
            for account_id in sorted(
                [data.from_account_id, data.to_account_id]
            )
        }

        request_id = (
            str(data.client_request_id)
            if data.client_request_id
            else None
        )

        if request_id:
            existing = db.scalar(
                select(AccountTransfer)
                .where(
                    AccountTransfer.user_id == user.id,
                    AccountTransfer.client_request_id == request_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )

            if existing:
                actual = (
                    existing.from_account_id,
                    existing.to_account_id,
                    existing.amount,
                    existing.txn_date,
                    existing.description,
                )
                requested = (
                    data.from_account_id,
                    data.to_account_id,
                    data.amount,
                    data.txn_date,
                    data.description,
                )

                if actual != requested:
                    raise HTTPException(
                        409,
                        "Request ID was already used for a different transfer",
                    )

                return transfer_response(db, user, existing)

        source = accounts[data.from_account_id]
        destination = accounts[data.to_account_id]

        usable_account(source, user)
        usable_account(destination, user)

        if source.currency != destination.currency:
            raise HTTPException(
                422,
                "Transfers require matching account currencies",
            )

        if account_balance(
            db,
            source,
            lock_entries=True,
        ) < data.amount:
            raise HTTPException(
                409,
                "Insufficient source account balance",
            )

        transfer = AccountTransfer(
            user_id=user.id,
            from_account_id=source.id,
            to_account_id=destination.id,
            amount=data.amount,
            currency=source.currency,
            txn_date=data.txn_date,
            description=data.description,
            client_request_id=request_id,
        )

        db.add(transfer)
        db.flush()

        db.add_all(
            [
                Transaction(
                    user_id=user.id,
                    account_id=source.id,
                    kind="transfer_out",
                    category="Transfer",
                    amount=data.amount,
                    txn_date=data.txn_date,
                    description=(
                        data.description
                        or f"Transfer to {destination.name}"
                    ),
                    transfer_id=transfer.id,
                ),
                Transaction(
                    user_id=user.id,
                    account_id=destination.id,
                    kind="transfer_in",
                    category="Transfer",
                    amount=data.amount,
                    txn_date=data.txn_date,
                    description=(
                        data.description
                        or f"Transfer from {source.name}"
                    ),
                    transfer_id=transfer.id,
                ),
            ]
        )

        db.flush()
        result = transfer_response(db, user, transfer)

        # Header and both ledger entries commit together.
        db.commit()

        return result

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Transfer conflicts with an existing record; refresh and retry",
        ) from None

    except Exception:
        db.rollback()
        raise