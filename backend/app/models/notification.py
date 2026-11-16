from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class NotificationRead(Base):
    __tablename__ = "notification_reads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    event_key: Mapped[str] = mapped_column(String(150))
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_notification_read"),)
