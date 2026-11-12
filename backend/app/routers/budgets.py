
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.database import get_db
from app.models.finance import Budget, Transaction
from app.models.user import User
from app.schemas.budget import (
    BudgetAlert,
    BudgetCreate,
    BudgetOut,
    BudgetUpdate,
)


router = APIRouter(
    prefix="/budgets",
    tags=["Budgets"],
)

ZERO = Decimal("0.00")


# ---------------------------------------
# Monthly date range
# ---------------------------------------

def month_bounds(
    month: str | None,
) -> tuple[date, date, str]:

    if month:
        try:
            first = date.fromisoformat(
                month + "-01"
            )
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="Invalid month; use YYYY-MM",
            ) from None
    else:
        first = date.today().replace(day=1)

    if first.month == 12:
        next_first = date(
            first.year + 1,
            1,
            1,
        )
    else:
        next_first = date(
            first.year,
            first.month + 1,
            1,
        )

    return (
        first,
        next_first,
        first.strftime("%Y-%m"),
    )


# ---------------------------------------
# Security: user's own budget only
# ---------------------------------------

def get_owned_budget(
    db: Session,
    user_id: int,
    budget_id: int,
) -> Budget:

    budget = db.scalar(
        select(Budget).where(
            Budget.id == budget_id,
            Budget.user_id == user_id,
        )
    )

    if budget is None:
        raise HTTPException(
            status_code=404,
            detail="Budget not found",
        )

    return budget


# ---------------------------------------
# Prevent duplicate category budgets
# ---------------------------------------

def require_unique_category(
    db: Session,
    user_id: int,
    category: str,
    exclude_id: int | None = None,
) -> None:

    statement = select(Budget.id).where(
        Budget.user_id == user_id,
        func.lower(
            func.trim(Budget.category)
        ) == category.casefold(),
    )

    if exclude_id is not None:
        statement = statement.where(
            Budget.id != exclude_id
        )

    if db.scalar(statement) is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "A budget already exists "
                "for this category"
            ),
        )


# ---------------------------------------
# Calculate expense totals per category
# ---------------------------------------

def spent_lookup(
    db: Session,
    user_id: int,
    first: date,
    next_first: date,
) -> dict[str, Decimal]:

    normalized_category = func.lower(
        func.trim(Transaction.category)
    )

    rows = db.execute(
        select(
            normalized_category,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
            Transaction.kind == "expense",
            Transaction.txn_date >= first,
            Transaction.txn_date < next_first,
        )
        .group_by(normalized_category)
    ).all()

    return {
        str(category): Decimal(amount)
        for category, amount in rows
    }


# ---------------------------------------
# Build budget response with status
# ---------------------------------------

def as_output(
    budget: Budget,
    amounts: dict[str, Decimal],
    currency: str,
    month: str,
) -> BudgetOut:

    limit = Decimal(budget.monthly_limit)

    spent = amounts.get(
        budget.category.strip().casefold(),
        ZERO,
    )

    remaining = limit - spent

    if limit > ZERO:

        percent = float(
            (
                spent * Decimal(100) / limit
            ).quantize(
                Decimal("0.1"),
                rounding=ROUND_HALF_UP,
            )
        )

        if spent > limit:
            state = "over_limit"

        elif spent == limit:
            state = "limit_reached"

        elif percent >= 80:
            state = "warning"

        else:
            state = "on_track"

    else:
        percent = (
            100.0 if spent > ZERO else 0.0
        )

        state = (
            "over_limit"
            if spent > ZERO
            else "not_set"
        )

    return BudgetOut(
        id=budget.id,
        category=budget.category,
        monthly_limit=limit,
        limit=limit,
        spent=spent,
        remaining=remaining,
        used_percent=percent,
        status=state,
        currency=currency,
        month=month,
    )


# ---------------------------------------
# Get all user budgets with calculations
# ---------------------------------------

def user_budget_views(
    db: Session,
    user: User,
    month: str | None,
) -> list[BudgetOut]:

    first, next_first, month_label = (
        month_bounds(month)
    )

    amounts = spent_lookup(
        db,
        user.id,
        first,
        next_first,
    )

    budgets = db.scalars(
        select(Budget)
        .where(Budget.user_id == user.id)
        .order_by(Budget.category)
    ).all()

    return [
        as_output(
            item,
            amounts,
            user.currency,
            month_label,
        )
        for item in budgets
    ]


# ---------------------------------------
# READ: All monthly budgets
# ---------------------------------------

@router.get(
    "",
    response_model=list[BudgetOut],
)
def list_budgets(
    month: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return user_budget_views(
        db,
        user,
        month,
    )


# ---------------------------------------
# READ: Budget warnings and alerts
# ---------------------------------------

@router.get(
    "/alerts",
    response_model=list[BudgetAlert],
)
def budget_alerts(
    month: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):

    result = []

    for item in user_budget_views(
        db,
        user,
        month,
    ):

        if item.status not in (
            "warning",
            "limit_reached",
            "over_limit",
        ):
            continue

        if item.status == "warning":
            message = (
                f"You have used "
                f"{item.used_percent:g}% "
                f"of your {item.category} budget."
            )

        elif item.status == "limit_reached":
            message = (
                f"You have reached your "
                f"{item.category} budget limit."
            )

        else:
            message = (
                f"You are over your "
                f"{item.category} budget limit."
            )

        result.append(
            BudgetAlert(
                budget_id=item.id,
                category=item.category,
                level=item.status,
                message=message,
                used_percent=item.used_percent,
                spent=item.spent,
                monthly_limit=item.monthly_limit,
                month=item.month,
            )
        )

    return result


# ---------------------------------------
# READ: Specific budget
# ---------------------------------------

@router.get(
    "/{budget_id}",
    response_model=BudgetOut,
)
def get_budget(
    budget_id: int = Path(gt=0),
    month: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):

    budget = get_owned_budget(
        db,
        user.id,
        budget_id,
    )

    first, next_first, label = (
        month_bounds(month)
    )

    amounts = spent_lookup(
        db,
        user.id,
        first,
        next_first,
    )

    return as_output(
        budget,
        amounts,
        user.currency,
        label,
    )


# ---------------------------------------
# CREATE: New monthly budget
# ---------------------------------------

@router.post(
    "",
    response_model=BudgetOut,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    data: BudgetCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):

    require_unique_category(
        db,
        user.id,
        data.category,
    )

    budget = Budget(
        user_id=user.id,
        category=data.category,
        monthly_limit=data.monthly_limit,
    )

    try:
        db.add(budget)
        db.commit()
        db.refresh(budget)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "A budget already exists "
                "for this category"
            ),
        ) from None

    first, next_first, label = (
        month_bounds(None)
    )

    amounts = spent_lookup(
        db,
        user.id,
        first,
        next_first,
    )

    return as_output(
        budget,
        amounts,
        user.currency,
        label,
    )


# ---------------------------------------
# UPDATE: Existing monthly budget
# ---------------------------------------

@router.put(
    "/{budget_id}",
    response_model=BudgetOut,
)
def update_budget(
    data: BudgetUpdate,
    budget_id: int = Path(gt=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):

    budget = get_owned_budget(
        db,
        user.id,
        budget_id,
    )

    require_unique_category(
        db,
        user.id,
        data.category,
        exclude_id=budget.id,
    )

    budget.category = data.category
    budget.monthly_limit = data.monthly_limit

    try:
        db.commit()
        db.refresh(budget)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=(
                "A budget already exists "
                "for this category"
            ),
        ) from None

    first, next_first, label = (
        month_bounds(None)
    )

    amounts = spent_lookup(
        db,
        user.id,
        first,
        next_first,
    )

    return as_output(
        budget,
        amounts,
        user.currency,
        label,
    )


# ---------------------------------------
# DELETE: Remove a budget
# Transactions remain unchanged
# ---------------------------------------

@router.delete("/{budget_id}")
def delete_budget(
    budget_id: int = Path(gt=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):

    budget = get_owned_budget(
        db,
        user.id,
        budget_id,
    )

    db.delete(budget)
    db.commit()

    return {
        "message": "Budget deleted",
        "id": budget_id,
    }
