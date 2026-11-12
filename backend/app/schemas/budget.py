
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BudgetCreate(BaseModel):
    category: str = Field(min_length=1, max_length=60)
    monthly_limit: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
    )

    @field_validator("category")
    @classmethod
    def clean_category(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category cannot be empty")
        return value


class BudgetUpdate(BudgetCreate):
    """PUT replaces the category and monthly limit."""


class BudgetOut(BaseModel):
    id: int
    category: str
    monthly_limit: Decimal
    limit: Decimal
    spent: Decimal
    remaining: Decimal
    used_percent: float
    status: Literal[
        "not_set",
        "on_track",
        "warning",
        "limit_reached",
        "over_limit",
    ]
    currency: str
    month: str


class BudgetAlert(BaseModel):
    budget_id: int
    category: str
    level: Literal[
        "warning",
        "limit_reached",
        "over_limit",
    ]
    message: str
    used_percent: float
    spent: Decimal
    monthly_limit: Decimal
    month: str
