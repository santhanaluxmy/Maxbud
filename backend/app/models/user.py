from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    onboarding_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="LKR", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc, nullable=False)
    identities: Mapped[list["AuthIdentity"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class AuthIdentity(Base):
    __tablename__ = "auth_identities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user: Mapped[User] = relationship(back_populates="identities")
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
        UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),
    )
