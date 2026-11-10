from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.database import get_db
from app.models.finance import (
    Account,
    Budget,
    Goal,
    IncomeSource,
    Transaction,
)
from app.models.user import User

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

ZERO = Decimal("0")


def money(value) -> str:
    return str(
        Decimal(value or 0).quantize(
            Decimal("0.01")
        )
    )


def month_start(
    year: int,
    month: int,
    offset: int = 0,
) -> date:
    year, index = divmod(
        year * 12 + (month - 1) + offset,
        12,
    )

    return date(year, index + 1, 1)


@router.get("")
def get_dashboard(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    first = today.replace(day=1)

    next_first = month_start(
        today.year,
        today.month,
        1,
    )

    accounts = db.scalars(
        select(Account).where(
            Account.user_id == user.id
        )
    ).all()

    income_sources = db.scalars(
        select(IncomeSource).where(
            IncomeSource.user_id == user.id
        )
    ).all()

    budgets = db.scalars(
        select(Budget).where(
            Budget.user_id == user.id
        )
    ).all()

    goals = db.scalars(
        select(Goal)
        .where(
            Goal.user_id == user.id,
            Goal.status == "active",
        )
        .order_by(Goal.id.desc())
        .limit(10)
    ).all()

    all_time = db.execute(
        select(
            Transaction.kind,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
        )
        .group_by(Transaction.kind)
    ).all()

    all_totals = {
        kind: Decimal(amount)
        for kind, amount in all_time
    }

    this_month = db.execute(
        select(
            Transaction.kind,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.txn_date >= first,
            Transaction.txn_date < next_first,
        )
        .group_by(Transaction.kind)
    ).all()

    month_totals = {
        kind: Decimal(amount)
        for kind, amount in this_month
    }

    monthly_income = month_totals.get(
        "income",
        ZERO,
    )

    monthly_expenses = month_totals.get(
        "expense",
        ZERO,
    )

    category_rows = db.execute(
        select(
            func.lower(Transaction.category),
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.kind == "expense",
            Transaction.txn_date >= first,
            Transaction.txn_date < next_first,
        )
        .group_by(
            func.lower(Transaction.category)
        )
        .order_by(
            func.sum(Transaction.amount).desc()
        )
    ).all()

    by_category = {
        str(category): Decimal(amount)
        for category, amount in category_rows
    }

    planned_income = ZERO

    for source in income_sources:
        if source.frequency == "weekly":
            planned_income += (
                Decimal(source.amount) * 52 / 12
            )
        elif source.frequency == "yearly":
            planned_income += (
                Decimal(source.amount) / 12
            )
        else:
            planned_income += Decimal(
                source.amount
            )

    opening_balance = sum(
        (
            Decimal(account.opening_balance)
            for account in accounts
        ),
        ZERO,
    )

    total_balance = (
        opening_balance
        + all_totals.get("income", ZERO)
        - all_totals.get("expense", ZERO)
    )

    budget_items = []
    total_budget = ZERO
    budgeted_spending = ZERO
    remaining_reserve = ZERO

    for budget in budgets:
        budget_limit = Decimal(
            budget.monthly_limit
        )

        spent = by_category.get(
            budget.category.strip().lower(),
            ZERO,
        )

        remaining = budget_limit - spent

        total_budget += budget_limit
        budgeted_spending += spent

        remaining_reserve += max(
            ZERO,
            remaining,
        )

        if budget_limit > 0:
            percent = float(
                (
                    spent / budget_limit * 100
                ).quantize(Decimal("0.1"))
            )
        else:
            percent = (
                100.0 if spent > 0 else 0.0
            )

        if spent > budget_limit:
            status = "over_limit"
        elif percent >= 80:
            status = "warning"
        else:
            status = "on_track"

        budget_items.append(
            {
                "category": budget.category,
                "limit": money(budget_limit),
                "spent": money(spent),
                "remaining": money(remaining),
                "used_percent": percent,
                "status": status,
            }
        )

    savings_total = db.scalar(
        select(
            func.coalesce(
                func.sum(Goal.saved_amount),
                0,
            )
        ).where(
            Goal.user_id == user.id
        )
    )

    recent = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.kind.in_(
                ["income", "expense"]
            ),
        )
        .order_by(
            Transaction.txn_date.desc(),
            Transaction.id.desc(),
        )
        .limit(5)
    ).all()

    first_chart_month = month_start(
        today.year,
        today.month,
        -5,
    )

    trends = db.execute(
        select(
            func.extract(
                "year",
                Transaction.txn_date,
            ),
            func.extract(
                "month",
                Transaction.txn_date,
            ),
            Transaction.kind,
            func.sum(Transaction.amount),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.deleted_at.is_(None),
            Transaction.txn_date >= first_chart_month,
            Transaction.txn_date < next_first,
        )
        .group_by(
            func.extract(
                "year",
                Transaction.txn_date,
            ),
            func.extract(
                "month",
                Transaction.txn_date,
            ),
            Transaction.kind,
        )
    ).all()

    trend_lookup = {
        (
            int(year),
            int(month),
            kind,
        ): Decimal(amount)
        for year, month, kind, amount in trends
    }

    six_month_trend = []

    for offset in range(-5, 1):
        start = month_start(
            today.year,
            today.month,
            offset,
        )

        six_month_trend.append(
            {
                "month": start.strftime("%Y-%m"),
                "income": money(
                    trend_lookup.get(
                        (
                            start.year,
                            start.month,
                            "income",
                        ),
                        ZERO,
                    )
                ),
                "expenses": money(
                    trend_lookup.get(
                        (
                            start.year,
                            start.month,
                            "expense",
                        ),
                        ZERO,
                    )
                ),
            }
        )

    return {
        "currency": user.currency,
        "onboarding_completed": user.onboarding_completed,
        "total_balance": money(total_balance),
        "monthly_income": money(monthly_income),
        "monthly_expenses": money(monthly_expenses),
        "total_savings_allocated": money(savings_total),
        "remaining_budget": money(
            total_budget - budgeted_spending
        ),
        "planned_monthly_income": money(
            planned_income
        ),
        "safe_to_spend_estimate": money(
            max(
                ZERO,
                total_balance - remaining_reserve,
            )
        ),
        "safe_to_spend_note": (
            "Estimate excludes upcoming bills and loans; "
            "not a guaranteed amount."
        ),
        "spending_by_category": [
            {
                "category": name,
                "amount": money(amount),
            }
            for name, amount in category_rows
        ],
        "budgets": budget_items,
        "goals": [
            {
                "id": goal.id,
                "name": goal.name,
                "target": money(goal.target_amount),
                "saved": money(goal.saved_amount),
                "status": goal.status,
            }
            for goal in goals
        ],
        "recent_transactions": [
            {
                "id": transaction.id,
                "account_id": transaction.account_id,
                "kind": transaction.kind,
                "category": transaction.category,
                "amount": money(transaction.amount),
                "description": transaction.description,
                "date": transaction.txn_date.isoformat(),
            }
            for transaction in recent
        ],
        "six_month_trend": six_month_trend,
    }