"""Transaction submission idempotency; no existing financial data is changed."""
from alembic import op
import sqlalchemy as sa
revision = "20261113_requests"
down_revision = "20261113_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_reminders", sa.Column("recurrence_day", sa.Integer(), nullable=True))
    op.create_table("transaction_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.UniqueConstraint("user_id", "request_key", name="uq_transaction_user_request"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; preserve request history")
