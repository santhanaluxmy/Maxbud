from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import now_utc


class IncomeSource(Base):
    __tablename__ = "income_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    frequency: Mapped[str] = mapped_column(
        String(20),
        default="monthly",
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(30))
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        default=0,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="LKR",
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("0"),
        nullable=False,
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    category: Mapped[str] = mapped_column(String(60))
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "category",
            name="uq_user_budget_category",
        ),
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    saved_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    target_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
    )


def transaction_name(context):
    values = context.get_current_parameters()

    return str(
        values.get("description")
        or values.get("category")
        or "Transaction"
    )[:150]


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(
        String(255),
        default="",
    )

    # Keep the API's txn_date name while using the existing DB column.
    txn_date: Mapped[date] = mapped_column("occurred_on", Date)

    name: Mapped[str] = mapped_column(
        String(150),
        default=transaction_name,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    legacy_financial_account_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now_utc,
    )
    transfer_id: Mapped[int | None] = mapped_column(
        ForeignKey("account_transfer_records.id"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "transfer_id",
            "kind",
            name="uq_transaction_transfer_kind",
        ),
    )


class AccountTransfer(Base):
    __tablename__ = "account_transfer_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    from_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
    )
    to_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    txn_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(
        String(255),
        default="",
    )
    client_request_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    legacy_transfer_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=now_utc,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "client_request_id",
            name="uq_transfer_user_request",
        ),
    )