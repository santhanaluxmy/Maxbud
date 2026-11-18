"""Add only recovery, session version and Stripe sandbox mapping/event tables.

Does not modify/backfill users, subscriptions or financial records.
Apply explicitly after reviewing the target database and normal backups.
"""
from alembic import op
from app.models.access import SessionVersion, PasswordRecovery, StripeAccount, StripeEvent

revision = '20261117_access'
down_revision = '20261115_beta'
branch_labels = None
depends_on = None


def upgrade():
    for model in [SessionVersion, PasswordRecovery, StripeAccount, StripeEvent]:
        model.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Recovery/billing audit records are retained. Destructive downgrade is intentionally unavailable.')
