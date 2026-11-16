"""Persist notification read state without changing financial data."""
from alembic import op
import sqlalchemy as sa
revision = "20261113_notifications"
down_revision = "20261113_ai"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notification_reads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_key", sa.String(150), nullable=False),
        sa.UniqueConstraint("user_id", "event_key", name="uq_notification_read"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; preserve notification state")
