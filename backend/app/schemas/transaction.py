from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionIn(BaseModel):
    account_id: int = Field(gt=0)
    kind: Literal["income", "expense"]
    category: str = Field(min_length=1, max_length=60)
    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    description: str = Field(default="", max_length=255)
    txn_date: date = Field(default_factory=date.today)

    @field_validator("category")
    @classmethod
    def clean_category(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Category cannot be empty")

        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()


class TransactionOut(TransactionIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: Literal["income", "expense", "transfer_in", "transfer_out"]
    category: str = Field(min_length=1, max_length=100)
    transfer_id: int | None = None
    created_at: datetime