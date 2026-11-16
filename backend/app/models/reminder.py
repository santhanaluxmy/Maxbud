from datetime import date
from decimal import Decimal
from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Reminder(Base):
    __tablename__ = "payment_reminders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    family_id: Mapped[int | None] = mapped_column(ForeignKey("families.id"), nullable=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    due_date: Mapped[date] = mapped_column(Date)
    recurrence_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recurrence: Mapped[str] = mapped_column(String(20), default="none")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReminderPayment(Base):
    __tablename__ = "reminder_payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reminder_id: Mapped[int] = mapped_column(ForeignKey("payment_reminders.id"))
    due_date: Mapped[date] = mapped_column(Date)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    __table_args__ = (UniqueConstraint("reminder_id", "due_date", name="uq_reminder_payment_occurrence"),)
