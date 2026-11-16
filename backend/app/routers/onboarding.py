
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.deps import current_user, writable_user
from app.database import get_db
from app.models.user import User
from app.models.finance import IncomeSource, Account, Budget, Goal
from app.schemas.onboarding import (
    AboutYouIn,
    IncomeIn,
    AccountsIn,
    BudgetsIn,
    GoalsIn,
)


router = APIRouter(
    prefix="/onboarding",
    tags=["Onboarding"],
)


def require_step(user: User, number: int, db: Session):
    db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if user.onboarding_completed:
        raise HTTPException(
            status_code=409,
            detail="Onboarding already completed",
        )

    if user.onboarding_step != number:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Complete onboarding step "
                f"{user.onboarding_step} first"
            ),
        )


@router.get("/status")
def status(
    user: User = Depends(current_user),
):
    return {
        "current_step": user.onboarding_step,
        "onboarding_completed": user.onboarding_completed,
        "total_steps": 5,
    }


@router.post("/about-you")
def about_you(
    data: AboutYouIn,
    user: User = Depends(writable_user),
    db: Session = Depends(get_db),
):
    require_step(user, 1, db)

    user.full_name = data.full_name.strip()
    user.currency = data.currency
    user.onboarding_step = 2

    db.commit()

    return {
        "message": "About You saved",
        "current_step": 2,
    }


@router.post("/income")
def income(
    data: IncomeIn,
    user: User = Depends(writable_user),
    db: Session = Depends(get_db),
):
    require_step(user, 2, db)

    for item in data.sources:
        db.add(
            IncomeSource(
                user_id=user.id,
                **item.model_dump(),
            )
        )

    user.onboarding_step = 3
    db.commit()

    return {
        "message": "Income saved",
        "current_step": 3,
    }


@router.post("/accounts")
def accounts(
    data: AccountsIn,
    user: User = Depends(writable_user),
    db: Session = Depends(get_db),
):
    require_step(user, 3, db)

    for item in data.accounts:
        db.add(
            Account(
                user_id=user.id,
                currency=user.currency,
                **item.model_dump(),
            )
        )

    user.onboarding_step = 4
    db.commit()

    return {
        "message": "Accounts saved",
        "current_step": 4,
    }


@router.post("/budgets")
def budgets(
    data: BudgetsIn,
    user: User = Depends(writable_user),
    db: Session = Depends(get_db),
):
    require_step(user, 4, db)

    for item in data.budgets:
        db.add(
            Budget(
                user_id=user.id,
                **item.model_dump(),
            )
        )

    user.onboarding_step = 5
    db.commit()

    return {
        "message": "Budgets saved",
        "current_step": 5,
    }


@router.post("/goals")
def goals(
    data: GoalsIn,
    user: User = Depends(writable_user),
    db: Session = Depends(get_db),
):
    require_step(user, 5, db)

    from app.routers.goals import check_limit
    active_count = sum(item.saved_amount < item.target_amount for item in data.goals)
    check_limit(db, user, active_count)

    for item in data.goals:
        db.add(
            Goal(
                user_id=user.id,
                **item.model_dump(),
                status="completed" if item.saved_amount == item.target_amount else "active",
            )
        )

    user.onboarding_completed = True
    db.commit()

    return {
        "message": "Onboarding completed",
        "current_step": 5,
        "onboarding_completed": True,
    }
