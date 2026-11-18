"""Additive recovery/session and sandbox billing state; no financial tables."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.user import now_utc


class SessionVersion(Base):
    __tablename__ = 'auth_session_versions'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class PasswordRecovery(Base):
    __tablename__ = 'password_recoveries'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    proof_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StripeAccount(Base):
    __tablename__ = 'stripe_test_accounts'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(100), unique=True)
    subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    checkout_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checkout_selection: Mapped[str | None] = mapped_column(String(60), nullable=True)


class StripeEvent(Base):
    __tablename__ = 'stripe_test_events'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    kind: Mapped[str] = mapped_column(String(100))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
