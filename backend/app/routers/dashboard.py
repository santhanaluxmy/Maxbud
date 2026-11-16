from datetime import date
from decimal import Decimal
from typing import Literal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
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
from app.models.reminder import Reminder
from app.models.family import Family, FamilyMembership
from app.models.user import User
from app.services.family import active_users, get_family
from app.services.goals import allocated_shared, shared_details

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
    scope: Literal["me", "family"] = "me",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    year: int | None = None,
    month: int | None = None,
    include_cash_flow: bool = False,
):
    if (year is None) != (month is None) or (year is not None and not (1900 <= year <= 9998 and 1 <= month <= 12)):
        raise HTTPException(422, "Provide a valid year and month together")
    if scope == "family":
        from app.services.household import household_report
        return household_report(db, user, year=year, month=month)
    family = None
    user_ids = [user.id]
    if scope == "family":
        family = get_family(db, user, owner_only=True)
        user_ids = [member.id for member in active_users(db, family)]
    today = date.today()
    if (year is None) != (month is None) or (year is not None and not (1900 <= year <= 9998 and 1 <= month <= 12)):
        raise HTTPException(422, "Provide a valid year and month together")
    if year is not None:
        today = date(year, month, 1)
    first = today.replace(day=1)

    next_first = month_start(
        today.year,
        today.month,
        1,
    )

    accounts = db.scalars(
        select(Account).where(
            Account.user_id.in_(user_ids), Account.family_id.is_(None)
        )
    ).all()

    if family and db.scalar(select(User.id).where(User.id.in_(user_ids), User.currency != "LKR").limit(1)) is not None:
        raise HTTPException(409, "Family totals require LKR household currencies; currency conversion is not supported")
    if family and any(account.currency != "LKR" for account in accounts):
        raise HTTPException(409, "Family totals require LKR accounts; currency conversion is not supported")

    if not family and any(account.currency != user.currency for account in accounts):
        raise HTTPException(409, "Totals require accounts in your selected currency; conversion is unavailable")

    income_sources = db.scalars(
        select(IncomeSource).where(
            IncomeSource.user_id.in_(user_ids)
        )
    ).all()

    budgets = db.scalars(
        select(Budget).where(
            Budget.user_id.in_(user_ids), Budget.family_id.is_(None)
        )
    ).all()

    if family:
        # Combine limits once per normalized category to avoid counting spending
        # repeatedly when different members budget for the same category.
        grouped = {}
        for budget in budgets:
            key = budget.category.strip().lower()
            grouped[key] = grouped.get(key, ZERO) + Decimal(budget.monthly_limit)
        budgets = [SimpleNamespace(category=key, monthly_limit=limit) for key, limit in grouped.items()]

    goals = db.scalars(
        select(Goal)
        .where(
            Goal.user_id.in_(user_ids),
            Goal.status == "active",
            Goal.family_id.is_(None),
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
            Transaction.user_id.in_(user_ids), Transaction.family_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.transfer_id.is_(None),
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
            Transaction.user_id.in_(user_ids), Transaction.family_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.transfer_id.is_(None),
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
            Transaction.user_id.in_(user_ids), Transaction.family_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.transfer_id.is_(None),
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

    from app.services.account import account_balance
    total_balance = sum((account_balance(db, account) for account in accounts), ZERO)
    active_tracked_balance = sum((account_balance(db, account) for account in accounts if not account.is_archived), ZERO)
    cash_flow = None
    if include_cash_flow:
        from app.services.cash_flow import monthly_cash_flow
        cash_flow = monthly_cash_flow(db, user, accounts, first, next_first)

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

        if spent >= budget_limit and spent > 0:
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

    # An unpaid bill reserves money only beyond the remaining budget for its
    # category, so the same planned expense is never reserved twice.
    unpaid_by_category = {}
    for bill in db.scalars(select(Reminder).where(Reminder.user_id.in_(user_ids), Reminder.family_id.is_(None), Reminder.is_active.is_(True), Reminder.due_date < next_first)):
        category = bill.category.strip().lower()
        unpaid_by_category[category] = unpaid_by_category.get(category, ZERO) + Decimal(bill.amount)
    budget_reserves = {item["category"].strip().lower(): max(ZERO, Decimal(item["remaining"])) for item in budget_items}
    unpaid_extra = sum((max(ZERO, amount - budget_reserves.get(category, ZERO)) for category, amount in unpaid_by_category.items()), ZERO)
    remaining_reserve += unpaid_extra

    savings_total = db.scalar(
        select(
            func.coalesce(
                func.sum(Goal.saved_amount),
                0,
            )
        ).where(
            Goal.user_id.in_(user_ids),
            Goal.family_id.is_(None),
        )
    )

    shared_allocation = allocated_shared(db, user_ids)
    if not family and shared_allocation and user.currency != "LKR":
        raise HTTPException(409, "Shared savings allocations are in LKR; currency conversion is unavailable")
    savings_total = Decimal(savings_total or 0) + shared_allocation

    member_summaries = []
    shared_goals = []
    upcoming_bills = []
    if family:
        amounts = db.execute(select(Transaction.user_id, Transaction.kind, func.sum(Transaction.amount)).where(
            Transaction.user_id.in_(user_ids), Transaction.family_id.is_(None), Transaction.deleted_at.is_(None), Transaction.transfer_id.is_(None),
            Transaction.kind.in_(["income", "expense"]), Transaction.txn_date >= first, Transaction.txn_date < next_first,
        ).group_by(Transaction.user_id, Transaction.kind)).all()
        totals = {(uid, kind): Decimal(amount) for uid, kind, amount in amounts}
        for member in active_users(db, family):
            income = totals.get((member.id, "income"), ZERO)
            expense = totals.get((member.id, "expense"), ZERO)
            member_summaries.append({"user_id": member.id, "full_name": member.full_name,
                "income": money(income), "expenses": money(expense), "net_cash_flow": money(income - expense),
                "shared_goal_contributions": money(allocated_shared(db, [member.id], family.id))})
        shared_goals = [shared_details(db, goal) for goal in db.scalars(select(Goal).where(Goal.family_id == family.id).order_by(Goal.id))]
        # Household payment aggregates omit personal bill names and account IDs.
        bill_rows = db.execute(select(func.lower(Reminder.category), Reminder.due_date, func.sum(Reminder.amount), func.count(Reminder.id)).where(
            Reminder.user_id.in_(user_ids), Reminder.family_id.is_(None), Reminder.is_active.is_(True)
        ).group_by(func.lower(Reminder.category), Reminder.due_date).order_by(Reminder.due_date).limit(10)).all()
        upcoming_bills = [{"category": category, "name": f"{category} payments", "amount": money(amount), "due_date": due, "bill_count": count}
                         for category, due, amount, count in bill_rows]

    recent = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id.in_(user_ids), Transaction.family_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.transfer_id.is_(None),
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
            Transaction.user_id.in_(user_ids), Transaction.family_id.is_(None),
            Transaction.deleted_at.is_(None),
            Transaction.transfer_id.is_(None),
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
        "currency": "LKR" if family else user.currency,
        "scope": scope,
        "can_view_family": db.scalar(select(FamilyMembership.id).join(Family,Family.id==FamilyMembership.family_id).where(FamilyMembership.user_id==user.id,FamilyMembership.status=="active",Family.is_active.is_(True),(Family.owner_user_id==user.id)|(FamilyMembership.can_view_shared.is_(True)))) is not None,
        "onboarding_completed": user.onboarding_completed,
        "total_balance": money(total_balance),
        "active_tracked_balance": money(active_tracked_balance),
        **({"cash_flow": cash_flow} if include_cash_flow else {}),
        "monthly_income": money(monthly_income),
        "monthly_expenses": money(monthly_expenses),
        "monthly_net_cash_flow": money(monthly_income - monthly_expenses),
        "member_summaries": member_summaries,
        "shared_goals": shared_goals,
        "upcoming_bills": upcoming_bills,
        "family_population": "Active memberships with active user accounts; removed members are excluded from current financial totals. Shared goal history is retained." if family else None,
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
                total_balance - remaining_reserve - Decimal(savings_total or 0),
            )
        ),
        "shared_savings_allocated": money(shared_allocation),
        "unpaid_bill_reserve": money(unpaid_extra),
        "safe_to_spend_note": (
            "Tracked balance less savings allocations, remaining budgets and unpaid bills through month end. Expected income is not available until recorded. Unrecorded obligations are excluded."
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
            for goal in (goals if not family else [])
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
            for transaction in (recent if not family else [])
        ],
        "six_month_trend": six_month_trend,
    }
