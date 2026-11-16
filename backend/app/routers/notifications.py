from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import current_user
from app.database import get_db
from app.models.notification import NotificationRead
from app.models.reminder import Reminder
from app.models.finance import Goal
from app.models.user import User
from app.routers.dashboard import get_dashboard

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def events(db, user):
    today = date.today()
    rows = []
    for bill in db.scalars(select(Reminder).where(Reminder.user_id == user.id, Reminder.family_id.is_(None), Reminder.is_active.is_(True), Reminder.due_date <= today + timedelta(days=7))):
        state = "overdue" if bill.due_date < today else "upcoming"
        rows.append({"key": f"bill:{bill.id}:{bill.due_date}:{state}", "message": f"{bill.name} is {state}: {bill.amount} due {bill.due_date}", "path": "/dashboard/reminders"})
    for budget in get_dashboard("me", user, db)["budgets"]:
        if budget["used_percent"] >= 80:
            state = "overspent" if budget["used_percent"] >= 100 else "warning"
            rows.append({"key": f"budget:{today:%Y-%m}:{budget['category']}:{state}", "message": f"{budget['category']} budget: {budget['used_percent']}% used", "path": "/dashboard/budgets"})
    for goal in db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.status == "completed")):
        rows.append({"key": f"goal:{goal.id}:completed", "message": f"Goal completed: {goal.name}", "path": "/dashboard/goals"})
    return rows


@router.get("")
def listing(user: User = Depends(current_user), db: Session = Depends(get_db)):
    read = set(db.scalars(select(NotificationRead.event_key).where(NotificationRead.user_id == user.id)))
    return [{**row, "read": row["key"] in read} for row in events(db, user)]


class ReadIn(BaseModel):
    key: str = Field(min_length=1, max_length=150)


@router.post("/read")
def mark_read(data: ReadIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if data.key not in {row["key"] for row in events(db, user)}:
        raise HTTPException(404, "Notification not found")
    db.add(NotificationRead(user_id=user.id, event_key=data.key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"read": True}
