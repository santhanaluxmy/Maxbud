import re
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("full_name")
    @classmethod
    def name_ok(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Name is too short")
        return v

    @field_validator("password")
    @classmethod
    def password_ok(cls, v):
        if not (re.search(r"[A-Z]", v) and re.search(r"[a-z]", v) and re.search(r"\d", v) and re.search(r"[^A-Za-z0-9]", v)):
            raise ValueError("Password needs uppercase, lowercase, number and symbol")
        return v

    @model_validator(mode="after")
    def match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class GoogleIn(BaseModel):
    credential: str = Field(min_length=20)

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    role: str
    currency: str
    onboarding_completed: bool

class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    onboarding_completed: bool
