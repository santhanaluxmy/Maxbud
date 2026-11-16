"""Add shared current goals to the existing goal/contribution tables.

No row is updated, relinked or backfilled. The legacy goal_id foreign key to
savings_goals is preserved. Widening its nullability lets new rows reference the
current goals table through a separate nullable FK. Review locking/DDL on the
intended MySQL deployment before running; downgrade deliberately disabled.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261113_shared_goals"
down_revision = "20261113_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("goals", sa.Column("family_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_goal_family", "goals", "families", ["family_id"], ["id"])
    op.create_index("ix_goals_family_id", "goals", ["family_id"])
    op.alter_column("goal_contributions", "goal_id", existing_type=sa.Integer(), existing_nullable=False, nullable=True)
    op.add_column("goal_contributions", sa.Column("current_goal_id", sa.Integer(), nullable=True))
    op.add_column("goal_contributions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("goal_contributions", sa.Column("request_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_contribution_current_goal", "goal_contributions", "goals", ["current_goal_id"], ["id"])
    op.create_foreign_key("fk_contribution_user", "goal_contributions", "users", ["user_id"], ["id"])
    op.create_index("ix_goal_contributions_current_goal_id", "goal_contributions", ["current_goal_id"])
    op.create_index("ix_goal_contributions_user_id", "goal_contributions", ["user_id"])
    op.create_unique_constraint("uq_goal_contribution_request", "goal_contributions", ["user_id", "request_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; preserve both legacy and current goal history")
