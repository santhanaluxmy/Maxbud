"""Add reminder occurrences without modifying existing tables or records.

Review this migration against the target schema before applying. No backfill.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261113_reminders"
down_revision = None
branch_labels = ("maxbud_features",)
depends_on = None


def upgrade():
    op.create_table("payment_reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("recurrence", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_index("ix_payment_reminders_user_id", "payment_reminders", ["user_id"])
    op.create_table("reminder_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("payment_reminders.id"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), sa.ForeignKey("transactions.id"), nullable=False),
        sa.UniqueConstraint("reminder_id", "due_date", name="uq_reminder_payment_occurrence"))


def downgrade():
    raise RuntimeError("Reminder payment history must be preserved; destructive downgrade is disabled")
