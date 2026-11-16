"""Compatible trial/demo billing, explicit household scopes, invitation and split ledgers.

Existing rows retain their old plan/source, private family_id NULL, old identities
and financial history. No data backfill, table deletion or destructive downgrade.
The budget key is widened only after the replacement unique key exists.
"""
from alembic import op
import sqlalchemy as sa
revision='20261115_beta'
down_revision='20261113_shared_goals'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('families',sa.Column('is_active',sa.Boolean(),nullable=False,server_default='1'))
    op.add_column('families',sa.Column('sponsor_user_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_family_sponsor','families','users',['sponsor_user_id'],['id'])
    for name in ['can_view_shared','can_add_shared']:
        op.add_column('family_memberships',sa.Column(name,sa.Boolean(),nullable=False,server_default='0'))
    for name in ['trial_started_at','trial_ends_at','period_started_at']:
        op.add_column('subscriptions',sa.Column(name,sa.DateTime(),nullable=True))
    for name,size in [('billing_cycle',10),('source',20),('pending_plan',20),('pending_cycle',10)]:
        op.add_column('subscriptions',sa.Column(name,sa.String(size),nullable=True))
    op.add_column('subscriptions',sa.Column('cancel_at_period_end',sa.Boolean(),nullable=False,server_default='0'))
    for table in ['accounts','transactions','budgets','payment_reminders']:
        op.add_column(table,sa.Column('family_id',sa.Integer(),nullable=True))
        op.create_foreign_key('fk_'+table+'_family',table,'families',['family_id'],['id'])
        op.create_index('ix_'+table+'_family_id',table,['family_id'])
    op.add_column('budgets',sa.Column('family_scope',sa.Integer(),sa.Computed('COALESCE(family_id, 0)')))
    op.create_unique_constraint('uq_budget_scope_category','budgets',['user_id','family_scope','category'])
    op.drop_constraint('uq_user_budget_category','budgets',type_='unique')
    op.create_table('family_invitations',
        sa.Column('id',sa.Integer(),primary_key=True),sa.Column('family_id',sa.Integer(),sa.ForeignKey('families.id'),nullable=False),
        sa.Column('invited_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('email',sa.String(255),nullable=False),
        sa.Column('token_hash',sa.String(64),nullable=False,unique=True),sa.Column('status',sa.String(20),nullable=False),
        sa.Column('expires_at',sa.DateTime(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('can_view_shared',sa.Boolean(),nullable=False),sa.Column('can_add_shared',sa.Boolean(),nullable=False))
    op.create_index('ix_family_invitations_family_id','family_invitations',['family_id'])
    op.create_index('ix_family_invitations_email','family_invitations',['email'])
    op.create_table('demo_checkouts',sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('plan',sa.String(20),nullable=False),
        sa.Column('billing_cycle',sa.String(10),nullable=False),sa.Column('amount',sa.Numeric(14,2),nullable=True),
        sa.Column('currency',sa.String(3),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('request_id',sa.String(36),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),sa.Column('expires_at',sa.DateTime(),nullable=False),sa.Column('completed_at',sa.DateTime(),nullable=True),
        sa.UniqueConstraint('user_id','request_id',name='uq_demo_checkout_request'))
    op.create_index('ix_demo_checkouts_user_id','demo_checkouts',['user_id'])
    op.create_table('household_expense_shares',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('transaction_id',sa.Integer(),sa.ForeignKey('transactions.id'),nullable=False),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('amount',sa.Numeric(14,2),nullable=False),sa.UniqueConstraint('transaction_id','user_id',name='uq_expense_share_user'))
    op.create_index('ix_household_expense_shares_transaction_id','household_expense_shares',['transaction_id'])
    op.create_table('household_settlements',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('share_id',sa.Integer(),sa.ForeignKey('household_expense_shares.id'),nullable=False),sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('amount',sa.Numeric(14,2),nullable=False),sa.Column('transfer_id',sa.Integer(),sa.ForeignKey('account_transfer_records.id'),nullable=False),
        sa.Column('request_id',sa.String(36),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('user_id','request_id',name='uq_settlement_request'))
    op.create_index('ix_household_settlements_share_id','household_settlements',['share_id'])
    op.create_table('platform_events',sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),sa.Column('kind',sa.String(60),nullable=False),
        sa.Column('target',sa.String(80),nullable=True),sa.Column('details',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False))
    for field in ['user_id','kind','created_at']: op.create_index('ix_platform_events_'+field,'platform_events',[field])


def downgrade():
    raise RuntimeError('Destructive downgrade disabled; preserve subscription, shared and financial history')
