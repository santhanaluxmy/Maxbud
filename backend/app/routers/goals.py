"""Personal allocations and shared goals; neither creates income or transfers."""
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.deps import current_user, writable_user
from app.core.plans import PLAN_LIMITS
from app.database import get_db
from app.models.finance import Goal, GoalContribution
from app.models.user import User
from app.schemas.onboarding import GoalItem
from app.services.family import family_plan, get_family
from app.services.goals import shared_family, shared_goal, shared_details, shared_balance, require_shared_currency

router = APIRouter(prefix="/goals", tags=["Goals"])


def owned(db, user, goal_id):
    initial = db.get(Goal, goal_id)
    if initial is not None and initial.family_id is not None:
        family, goal = shared_goal(db, user, goal_id, owner_only=True)
        from app.services.subscriptions import family_access
        family_access(db, family, write=True)
        return goal
    from app.services.subscriptions import require_edit
    require_edit(db, user)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user.id, Goal.family_id.is_(None)).with_for_update().execution_options(populate_existing=True))
    if goal is None:
        raise HTTPException(404, "Goal not found")
    return goal


def check_limit(db, user, additional=1):
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    try:
        from app.services.subscriptions import entitlement
        plan = entitlement(db, user)["plan"]
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        plan = "free"
    count = len(db.scalars(select(Goal.id).where(Goal.user_id == user.id, Goal.status == "active").with_for_update()).all())
    if count + additional > PLAN_LIMITS[plan]["active_goals"]:
        raise HTTPException(403, "Active goal limit reached. Archive a goal or upgrade your plan.")


def serialize(goal, db=None):
    if goal.family_id is not None:
        return shared_details(db, goal, lock=True)
    return {"id": goal.id, "name": goal.name, "target_amount": str(goal.target_amount),
            "saved_amount": str(goal.saved_amount), "target_date": goal.target_date,
            "status": goal.status, "progress": float(min(Decimal(100), goal.saved_amount / goal.target_amount * 100))}


@router.get("")
def listing(scope: Literal["me", "family"] = "me", user: User = Depends(current_user), db: Session = Depends(get_db)):
    if scope == "family":
        family = shared_family(db, user)
        goals = db.scalars(select(Goal).where(Goal.family_id == family.id).order_by(Goal.id.desc()).with_for_update()).all()
    else:
        goals = db.scalars(select(Goal).where(Goal.user_id == user.id, Goal.family_id.is_(None)).order_by(Goal.id.desc())).all()
    return [serialize(goal, db) for goal in goals]


@router.post("", status_code=201)
def create(data: GoalItem, scope: Literal["me", "family"] = "me", user: User = Depends(current_user), db: Session = Depends(get_db)):
    family = None
    if scope == "family":
        family = shared_family(db, user, owner_only=True)
        from app.services.subscriptions import family_access
        family_access(db, family, write=True)
        require_shared_currency(db, family)
        if data.saved_amount != 0:
            raise HTTPException(422, "Shared goals start at zero; record each member's contribution in the ledger")
        if not data.name.strip():
            raise HTTPException(422, "Goal name is required")
    if family is None:
        from app.services.subscriptions import require_edit
        require_edit(db, user)
    if data.saved_amount > data.target_amount:
        raise HTTPException(422, "Saved amount cannot exceed target")
    complete = data.saved_amount == data.target_amount
    if not complete:
        check_limit(db, user)
    goal = Goal(user_id=user.id, family_id=family.id if family else None, **data.model_dump(), status="completed" if complete else "active")
    db.add(goal)
    db.flush()
    result = serialize(goal, db)
    db.commit()
    return result


@router.put("/{goal_id}")
def update(goal_id: int, data: GoalItem, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = owned(db, user, goal_id)
    if goal.family_id is not None:
        data.name = data.name.strip()
        if not data.name:
            raise HTTPException(422, "Goal name is required")
        balance = shared_balance(db, goal)
        if data.saved_amount != balance:
            raise HTTPException(422, "Shared saved amounts are controlled by the contribution ledger")
        if data.target_amount < balance:
            raise HTTPException(422, "Target cannot be below recorded contributions")
    if data.saved_amount > data.target_amount:
        raise HTTPException(422, "Saved amount cannot exceed target")
    status = "completed" if data.saved_amount == data.target_amount else "active"
    if status == "active" and goal.status != "active":
        check_limit(db, user)
    for key, value in data.model_dump().items():
        setattr(goal, key, value)
    goal.status = "archived" if goal.status == "archived" else status
    result = serialize(goal, db)
    db.commit()
    return result


class Contribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    request_id: str | None = Field(default=None, min_length=1, max_length=36)


@router.post("/{goal_id}/contribute")
def contribute(goal_id: int, data: Contribution, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return record_contribution(db, user, goal_id, data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Contribution conflicts with an existing submission; refresh and retry") from None
    except Exception:
        db.rollback()
        raise


def record_contribution(db, user, goal_id, data):
    initial = db.get(Goal, goal_id)
    if initial is not None and initial.family_id is not None:
        family, goal = shared_goal(db, user, goal_id)
        from app.services.subscriptions import family_access
        family_access(db, family, write=True)
        require_shared_currency(db, family, user)
        from app.services.household import access
        access(db, user, write=True)
        if not data.request_id:
            raise HTTPException(422, "A submission request_id is required for shared contributions")
        previous = db.scalar(select(GoalContribution).where(GoalContribution.user_id == user.id, GoalContribution.request_id == data.request_id).with_for_update())
        if previous:
            if previous.current_goal_id != goal.id or previous.amount != data.amount:
                raise HTTPException(409, "Contribution request_id was already used with different details")
            return serialize(goal, db)
        balance = shared_balance(db, goal)
        if goal.status != "active":
            raise HTTPException(409, "Only active goals accept contributions")
        if balance + data.amount > goal.target_amount:
            raise HTTPException(422, "Contribution exceeds the remaining goal amount")
        db.add(GoalContribution(current_goal_id=goal.id, user_id=user.id, request_id=data.request_id, amount=data.amount))
        goal.saved_amount = balance + data.amount
        if goal.saved_amount == goal.target_amount:
            goal.status = "completed"
        db.flush()
    else:
        goal = owned(db, user, goal_id)
        # The user/goal locks serialize personal contributions. Keep historical
        # saved_amount as the baseline; only new contributions enter the ledger.
        if data.request_id:
            previous = db.scalar(select(GoalContribution).where(
                GoalContribution.user_id == user.id,
                GoalContribution.request_id == data.request_id,
            ).with_for_update())
            if previous:
                if previous.current_goal_id != goal.id or previous.amount != data.amount:
                    raise HTTPException(409, "Contribution request_id was already used with different details")
                return serialize(goal, db)
        if goal.status != "active":
            raise HTTPException(409, "Only active goals accept contributions")
        if goal.saved_amount + data.amount > goal.target_amount:
            raise HTTPException(422, "Contribution exceeds the remaining goal amount")
        db.add(GoalContribution(
            current_goal_id=goal.id,
            user_id=user.id,
            request_id=data.request_id,
            amount=data.amount,
        ))
        goal.saved_amount += data.amount
        if goal.saved_amount == goal.target_amount:
            goal.status = "completed"
    result = serialize(goal, db)
    db.commit()
    return result


class StatusChange(BaseModel):
    status: Literal["archived", "active"]


@router.patch("/{goal_id}")
def change_status(goal_id: int, data: StatusChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    goal = owned(db, user, goal_id)
    balance = shared_balance(db, goal) if goal.family_id is not None else goal.saved_amount
    status = "completed" if data.status == "active" and balance >= goal.target_amount else data.status
    if status == "active" and goal.status != "active":
        check_limit(db, user)
    goal.status = status
    result = serialize(goal, db)
    db.commit()
    return result
