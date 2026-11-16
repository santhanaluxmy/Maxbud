"""Extend existing AI scans and add advisor history and merchant rules.

Additive only; does not backfill or update existing rows.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261113_ai"
down_revision = "20261113_reminders"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ai_scans", sa.Column("details", sa.JSON(), nullable=True))
    op.add_column("ai_scans", sa.Column("image_path", sa.String(255), nullable=True))
    op.add_column("ai_scans", sa.Column("image_hash", sa.String(64), nullable=True))
    op.add_column("ai_scans", sa.Column("transaction_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_ai_scan_transaction", "ai_scans", "transactions", ["transaction_id"], ["id"])
    op.create_table("advisor_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.UniqueConstraint("user_id", "request_id", name="uq_advisor_request"))
    op.create_index("ix_advisor_messages_user_id", "advisor_messages", ["user_id"])
    op.create_table("merchant_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("merchant", sa.String(150), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.UniqueConstraint("user_id", "merchant", name="uq_merchant_user"))


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; preserve AI history")
