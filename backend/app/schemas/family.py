from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
from app.schemas.auth import RegisterIn


class MemberCreate(RegisterIn):
    # Match the inspected legacy MySQL users columns, while reusing password rules.
    full_name: str = Field(min_length=2, max_length=100)
    confirm_password: str = Field(min_length=8, max_length=128)


class MemberOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: Literal["owner", "member"]
    is_active: bool
    joined_at: datetime | None = None
    can_view_shared: bool = False
    can_add_shared: bool = False


class FamilyOut(BaseModel):
    can_view_shared: bool = False
    can_add_shared: bool = False
    can_edit_shared: bool = False
    legacy_member_creation: bool = False
    id: int
    name: str
    plan: Literal["free", "premium", "family_pack", "read_only"]
    currency: str
    owner_name: str
    owner_id: int
    role: Literal["owner", "member"]
    total_active_members: int
    max_members: int
    available_slots: int
    reserved_slots: int = 0
