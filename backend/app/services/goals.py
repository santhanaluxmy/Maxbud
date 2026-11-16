"""Shared goal access and append-only contribution reporting."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func, select
from app.models.family import Family
from app.models.finance import Account, Goal, GoalContribution
from app.models.user import User
from app.services.family import active_users, get_family


def shared_family(db, user, owner_only=False):
    family = get_family(db, user, owner_only=owner_only, lock=True)
    # Recheck membership with a current read AFTER the family row lock, so a
    # removed member's existing JWT cannot use a stale InnoDB snapshot.
    if user.id not in {member.id for member in active_users(db, family, lock=True)}:
        raise HTTPException(403, "Active family membership required")
    # Keep legacy explicitly shared goal access; new households use the owner's
    # granular permission grants for all shared records, including goals.
    from app.models.family import Subscription
    subscription = db.scalar(select(Subscription).where(Subscription.user_id == family.owner_user_id))
    if subscription is not None and subscription.source is not None:
        from app.services.household import access
        access(db, user, owner=owner_only)
    return family


def shared_goal(db, user, goal_id, owner_only=False):
    family = shared_family(db, user, owner_only)
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.family_id == family.id).with_for_update().execution_options(populate_existing=True))
    if goal is None:
        raise HTTPException(404, "Shared goal not found")
    return family, goal


def shared_balance(db, goal):
    # Locking reads avoid stale repeatable-read snapshots during contribution.
    amounts = db.scalars(select(GoalContribution.amount).where(GoalContribution.current_goal_id == goal.id, GoalContribution.reversed_at.is_(None)).with_for_update()).all()
    return sum((Decimal(amount) for amount in amounts), Decimal(0))


def shared_details(db, goal, lock=False):
    statement = select(GoalContribution, User.full_name).join(User, User.id == GoalContribution.user_id).where(GoalContribution.current_goal_id == goal.id).order_by(GoalContribution.id)
    if lock:
        statement = statement.with_for_update()
    rows = db.execute(statement).all()
    active_ids = {member.id for member in active_users(db, db.get(Family, goal.family_id))}
    total = sum((Decimal(row.amount) for row, _ in rows if row.reversed_at is None), Decimal(0))
    members = {}
    for row, name in rows:
        if row.reversed_at is None:
            entry = members.setdefault(row.user_id, {"user_id": row.user_id, "full_name": name, "is_active_member": row.user_id in active_ids, "amount": Decimal(0)})
            entry["amount"] += row.amount
    return {"id": goal.id, "name": goal.name, "family_id": goal.family_id,
            "target_amount": str(goal.target_amount), "saved_amount": str(total),
            "remaining_amount": str(max(Decimal(0), goal.target_amount - total)),
            "target_date": goal.target_date, "status": goal.status,
            "progress": float(min(Decimal(100), total / goal.target_amount * 100)),
            "contributions": [{**entry, "amount": str(entry["amount"])} for entry in members.values()],
            "history": [{"id": row.id, "user_id": row.user_id, "full_name": name, "is_active_member": row.user_id in active_ids, "amount": str(row.amount), "recorded_on": row.recorded_on, "reversed": row.reversed_at is not None} for row, name in rows]}


def allocated_shared(db, user_ids, family_id=None):
    statement = select(func.coalesce(func.sum(GoalContribution.amount), 0)).join(Goal, Goal.id == GoalContribution.current_goal_id).where(GoalContribution.user_id.in_(user_ids), GoalContribution.reversed_at.is_(None), Goal.family_id.is_not(None))
    if family_id is not None:
        statement = statement.where(Goal.family_id == family_id)
    return Decimal(db.scalar(statement) or 0)


def require_shared_currency(db, family, user=None):
    if user is not None and user.currency != "LKR":
        raise HTTPException(409, "Shared goal allocations require your personal currency to be LKR; conversion is unavailable")
