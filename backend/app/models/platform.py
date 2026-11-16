"""New invitation, checkout, split and audit concepts; finance tables are reused."""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.user import now_utc


class FamilyInvitation(Base):
    __tablename__ = "family_invitations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"), index=True)
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(255), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    can_view_shared: Mapped[bool] = mapped_column(Boolean, default=True)
    can_add_shared: Mapped[bool] = mapped_column(Boolean, default=True)


class DemoCheckout(Base):
    __tablename__ = "demo_checkouts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[str] = mapped_column(String(20))
    billing_cycle: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="LKR")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    request_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_demo_checkout_request"),)


class ExpenseShare(Base):
    __tablename__ = "household_expense_shares"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    __table_args__ = (UniqueConstraint("transaction_id", "user_id", name="uq_expense_share_user"),)


class Settlement(Base):
    __tablename__ = "household_settlements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    share_id: Mapped[int] = mapped_column(ForeignKey("household_expense_shares.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    transfer_id: Mapped[int] = mapped_column(ForeignKey("account_transfer_records.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_settlement_request"),)


class PlatformEvent(Base):
    __tablename__ = "platform_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    target: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, index=True)
