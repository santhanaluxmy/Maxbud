from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class TransactionRequest(Base):
    __tablename__ = "transaction_requests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_key: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    __table_args__ = (UniqueConstraint("user_id", "request_key", name="uq_transaction_user_request"),)
