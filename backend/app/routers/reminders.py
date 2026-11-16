import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.deps import current_user, writable_user
from app.core.plans import PLAN_LIMITS
from app.database import get_db
from app.models.reminder import Reminder, ReminderPayment
from app.models.finance import Transaction
from app.models.user import User
from app.services.account import account_balance, owned_account, usable_account
from app.services.family import family_plan, get_family

router = APIRouter(prefix="/reminders", tags=["Reminders"])


class ReminderIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    account_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    due_date: date
    recurrence: Literal["none", "weekly", "monthly", "yearly"] = "none"


class PayIn(BaseModel):
    due_date: date


def owned(db, user, key):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    row = db.scalar(select(Reminder).where(Reminder.id == key, Reminder.user_id == user.id, Reminder.family_id.is_(None)).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "Reminder not found")
    return row


def next_due(day, recurrence, anchor_day=None):
    if recurrence == "weekly":
        return day + timedelta(days=7)
    year, month = day.year, day.month
    if recurrence == "monthly":
        year, index = divmod(year * 12 + month, 12)
        month = index + 1
    else:
        year += 1
    return date(year, month, min(anchor_day or day.day, calendar.monthrange(year, month)[1]))


@router.get("")
def listing(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.family_id.is_(None), Reminder.is_active.is_(True)).order_by(Reminder.due_date)).all()


@router.post("", status_code=201)
def create(data: ReminderIn, user: User = Depends(writable_user), db: Session = Depends(get_db)):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    try:
        from app.services.subscriptions import entitlement
        plan = entitlement(db, user)["plan"]
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        plan = "free"
    limit = PLAN_LIMITS[plan]["active_reminders"]
    count = len(db.scalars(select(Reminder.id).where(Reminder.user_id == user.id, Reminder.family_id.is_(None), Reminder.is_active.is_(True)).with_for_update()).all())
    if limit is not None and count >= limit:
        raise HTTPException(403, "Active reminder limit reached")
    usable_account(owned_account(db, user, data.account_id), user)
    row = Reminder(user_id=user.id, recurrence_day=data.due_date.day, **data.model_dump())
    db.add(row)
    db.commit()
    return row


@router.put("/{key}")
def update(key: int, data: ReminderIn, user: User = Depends(writable_user), db: Session = Depends(get_db)):
    row = owned(db, user, key)
    if not row.is_active:
        raise HTTPException(409, "Reminder is inactive")
    usable_account(owned_account(db, user, data.account_id), user)
    row.recurrence_day = data.due_date.day
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.commit()
    return row


@router.delete("/{key}")
def delete(key: int, user: User = Depends(writable_user), db: Session = Depends(get_db)):
    row = owned(db, user, key)
    row.is_active = False
    db.commit()
    return {"message": "Reminder archived"}


@router.post("/{key}/pay")
def pay(key: int, data: PayIn, user: User = Depends(writable_user), db: Session = Depends(get_db)):
    row = owned(db, user, key)
    previous = db.scalar(select(ReminderPayment).where(ReminderPayment.reminder_id == key, ReminderPayment.due_date == data.due_date).with_for_update())
    if previous:
        return {"transaction_id": previous.transaction_id, "already_paid": True}
    if not row.is_active or row.due_date != data.due_date:
        raise HTTPException(409, "Reminder changed; refresh before paying")
    account = owned_account(db, user, row.account_id, lock=True)
    usable_account(account, user)
    if account_balance(db, account, lock_entries=True) < row.amount:
        raise HTTPException(422, "Insufficient tracked account balance")
    txn = Transaction(user_id=user.id, account_id=account.id, kind="expense", category=row.category,
                      amount=row.amount, description=row.name, txn_date=date.today())
    db.add(txn)
    db.flush()
    db.add(ReminderPayment(reminder_id=key, due_date=data.due_date, transaction_id=txn.id))
    if row.recurrence == "none":
        row.is_active = False
    else:
        row.due_date = next_due(row.due_date, row.recurrence, row.recurrence_day)
    db.commit()
    return {"transaction_id": txn.id, "already_paid": False, "next_due_date": row.due_date if row.is_active else None}
