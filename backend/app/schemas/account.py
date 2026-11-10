from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


AccountKind = Literal[
    "cash",
    "bank",
    "wallet",
    "other",
]


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=120,
    )

    kind: AccountKind

    opening_balance: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class AccountPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )

    kind: AccountKind | None = None

    opening_balance: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def valid_changes(self):
        changes = self.model_dump(exclude_unset=True)

        if not changes or any(
            value is None
            for value in changes.values()
        ):
            raise ValueError(
                "Provide at least one non-null account field"
            )

        return self


class AccountArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    archived: bool = True


class AccountOut(BaseModel):
    id: int
    name: str
    kind: str
    opening_balance: Decimal
    current_balance: Decimal
    currency: str
    is_archived: bool
    status: Literal["active", "archived"]


class AccountListOut(BaseModel):
    items: list[AccountOut]
    total_balance: Decimal
    currency: str


class TransferCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_account_id: int = Field(gt=0)
    to_account_id: int = Field(gt=0)

    amount: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )

    txn_date: date = Field(
        default_factory=date.today,
    )

    description: str = Field(
        default="",
        max_length=255,
    )

    client_request_id: UUID | None = None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value):
        return value.strip()

    @model_validator(mode="after")
    def different_accounts(self):
        if self.from_account_id == self.to_account_id:
            raise ValueError(
                "Choose two different accounts"
            )

        return self


class TransferOut(BaseModel):
    id: int
    from_account_id: int
    to_account_id: int
    amount: Decimal
    currency: str
    txn_date: date
    description: str
    client_request_id: str | None
    created_at: datetime
    entry_ids: list[int]