# Database audit — November 15, 2026

Target inspected: local `maxbud_db`, revision initially `20261113_shared_goals`, 31 existing tables. Backups verified available and protected by SHA256 comparison: `~/Documents/MaxBud_backups/maxbud_before_final.sql` and `maxbud_source_backup.tar.gz`. Neither was overwritten. Private `.env` files are also hash-protected and unchanged.

## Active/legacy concepts

Active application finance writes use `accounts`, `transactions`, `budgets`, `goals`, `account_transfer_records`; authentication uses `auth_identities` with existing compatibility mappings. `financial_accounts`, `account_legacy_map`, `account_transfers`, `monthly_budgets`, `savings_goals`, `authentication_identities` remain preserved for existing compatibility/history. Existing `goal_contributions.goal_id` retains its legacy savings_goals relationship; current shared ledger uses `current_goal_id` and contributor/request fields from the earlier migration. No legacy table was dropped or merged.

## Applied beta migration

`backend/migrations/versions/20261115_beta.py`, parent `20261113_shared_goals`, is now the `maxbud_features` head. Applied to local MySQL after reviewed operations and an explicit escalation request. It adds family activation/sponsor, granular membership permissions, nullable trial/billing fields, and nullable family scope on existing accounts/transactions/budgets/reminders. Existing rows stay private (`family_id=NULL`); legacy subscription source stays NULL. No UPDATE backfill, user reset or financial-record deletion occurs.

New tables represent distinct missing concepts only: `family_invitations`, `demo_checkouts`, `household_expense_shares`, `household_settlements`, `platform_events`. Total tables: **36**. No duplicate accounts/goals/subscriptions/receipt tables were created.

Budget uniqueness is widened from user/category to user/generated `family_scope=COALESCE(family_id,0)`/category. The replacement unique constraint is created before removing the original index. This preserves personal-category uniqueness while permitting a separate shared Food budget. MySQL applied the generated column/index successfully. Downgrade is intentionally blocked to avoid deleting beta histories; restore/recovery needs operator planning, not an automatic destructive rollback.

Before/after hashes over original columns verified **all 116 existing rows in 30 data tables unchanged**. The only excluded table is `alembic_version`, whose revision intentionally changes. MySQL DDL is not transactional; any interrupted future migration must be inspected before rerunning. Never execute `upgrade heads`: a separate unrelated legacy-accounts branch remains present and must not be applied blindly.

## Accounting and transaction safety

Income/expenses remain signed ledger effects on actual accounts. Shared-wallet funding and reimbursements create paired transfers, not income/expenses. Shared personal-paid expense is recorded once with explicit family scope; balance queries still debit the payer's account. Splits use Decimal cent allocation, with equal/custom/percentage checks. Partial settlement reduces debt and transfers actual funds to the original payer; it does not reinsert the expense. Goal allocations do not move funds and remain separate from expenses. Shared reports never pool private salaries/accounts/bills.

Family/account/user locks and unique request constraints serialize relevant writes; financial payload fingerprints reject conflicting replays. Membership is rechecked after family locking. MySQL integration tests use outer transactions/savepoints and always roll back, never drop/reset application tables. Multi-connection race verification remains blocked by the existing account's error 1044 permission to create an isolated test database. Do not change grants or run the earlier destructive race harness against this database. No production concurrency claim is made.
