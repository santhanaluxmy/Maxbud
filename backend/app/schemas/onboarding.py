from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator

Money = Decimal
class AboutYouIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    currency: str = Field(default="LKR", pattern=r"^[A-Z]{3}$")

class IncomeItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    amount: Money = Field(gt=0, max_digits=12, decimal_places=2)
    frequency: Literal["weekly", "monthly", "yearly"] = "monthly"

class IncomeIn(BaseModel):
    sources: list[IncomeItem] = Field(min_length=1, max_length=20)

class AccountItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: Literal["cash", "bank", "wallet", "other"]
    opening_balance: Money = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)

class AccountsIn(BaseModel):
    accounts: list[AccountItem] = Field(min_length=1, max_length=20)

class BudgetItem(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    monthly_limit: Money = Field(ge=0, max_digits=12, decimal_places=2)

class BudgetsIn(BaseModel):
    budgets: list[BudgetItem] = Field(min_length=1, max_length=30)

    @field_validator("budgets")
    @classmethod
    def unique_categories(cls, items):
        names = [x.category.strip().casefold() for x in items]
        if len(names) != len(set(names)):
            raise ValueError("Budget categories must be unique")
        return items

class GoalItem(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: Money = Field(gt=0, max_digits=12, decimal_places=2)
    saved_amount: Money = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    target_date: date | None = None

class GoalsIn(BaseModel):
    goals: list[GoalItem] = Field(default_factory=list, max_length=20)

    @field_validator("goals")
    @classmethod
    def amounts_ok(cls, items):
        if any(x.saved_amount > x.target_amount for x in items):
            raise ValueError("Saved amount cannot exceed target")
        return items
