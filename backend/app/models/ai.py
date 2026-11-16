from datetime import date, datetime
from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.user import now_utc


class AIScan(Base):
    __tablename__ = "ai_scans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(25))
    merchant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    occurred_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)


class AIUsage(Base):
    __tablename__ = "ai_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    scan_id: Mapped[int] = mapped_column(ForeignKey("ai_scans.id"))
    charged_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class AdvisorMessage(Base):
    __tablename__ = "advisor_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    request_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (UniqueConstraint("user_id", "request_id", name="uq_advisor_request"),)


class MerchantRule(Base):
    __tablename__ = "merchant_rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    merchant: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("user_id", "merchant", name="uq_merchant_user"),)
