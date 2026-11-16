"""Mappings for the existing MySQL family and subscription tables."""
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Family(Base):
    __tablename__ = "families"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sponsor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class FamilyMembership(Base):
    __tablename__ = "family_memberships"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("families.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    can_view_shared: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    can_add_shared: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    plan: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    billing_cycle: Mapped[str | None] = mapped_column(String(10), nullable=True)
    source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    pending_plan: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pending_cycle: Mapped[str | None] = mapped_column(String(10), nullable=True)
