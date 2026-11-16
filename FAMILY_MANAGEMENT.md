# Current beta contract — November 15, 2026

This section supersedes earlier pooled-family report and new-user auto-family policies below. Earlier implementation notes are retained as history.

## Current behavior

Personal accounts, salaries, expenses, budgets, bills, reports and goals stay private. Shared records carry explicit `family_id`; membership alone never exposes private finance. Owners and members with `can_view_shared` can see shared reports; `can_add_shared` permits expenses, wallet/goal contributions, bill payment and settlement. Owner-only controls manage invitations, membership grants/removals, name, wallets, shared budgets and shared-goal definitions. Platform admin is a separate role.

New registrations start a personal trial without a household. An active own Family Pack creates one household; its owner sponsors up to five invited members by default. Existing legacy households/subscriptions remain grandfathered. Legacy password-created members remain supported for compatibility only; new Family Pack uses secure invitation acceptance with each member's independent login. Joining never cancels the member's own paid subscription.

Invitations use random high-entropy tokens, stored as hashes, invited-email matching, seven-day expiry, pending-seat reservation, revoke/reject and one-time acceptance. A removed member cannot replay an old accepted token to rejoin. Owner provides a secure link manually; no automatic email is claimed. A member may leave; an owner cannot leave or transfer ownership. Only an empty household without shared goals/wallets/transactions can close. Existing financial histories are never deleted by membership changes.

## Financial examples verified in integration tests

- Shared goal: owner300 + member200 =500, with dated contributor ledger, remaining amount/progress and duplicate request protection. Removing a member preserves contributions. Goal contributions are allocations; no account transfer/expense is fabricated.
- Wallet: personal20000 + personal30000 = shared50000 through paired transfers. Groceries8000 leaves42000. Funding is not income; expenses are recorded once. Private endpoints cannot open shared wallets by guessing IDs.
- Personal-paid electricity12000 with equal owner/member split creates one6000 debt to the payer. Partial reimbursement2000 transfers money and leaves4000 outstanding. Original expense remains one12000 expense. Equal/custom/percentage splits use Decimal, validate participants/totals and allocate cent remainders deterministically.
- Authorized report contains shared spending/categories, wallet funding and balances, member contributions, shared goals, unpaid bills and reimbursement balances. Private salaries/accounts/budget/bill details stay absent. Historical year/month selection filters shared spending. Current balance is live, as in the personal report.

Shared safe-to-spend uses shared wallet funds less the larger of category budget remainder/unpaid matching commitments to avoid duplicate reserves. If manual goal allocations exist outside the wallet, safe-to-spend is unavailable rather than presented as certain. Personal-paid shared expenses are disclosed in household activity and affect the payer's balance; personal monthly category reports intentionally show personal-scope expenses only.

## API map

- `GET/POST/PATCH /family`: overview/create/rename.
- `GET /family/members`, `DELETE /family/members/{id}`, `PATCH /family/members/{id}/permissions`.
- `POST /family/leave`, `POST /family/close` (empty only).
- `GET/POST /family/invitations`, `DELETE /family/invitations/{id}`, `POST /family/invitations/respond`.
- `GET/POST /family/wallets`, `PATCH /family/wallets/{id}`, `POST /family/wallets/{id}/archive`, `POST /family/wallets/{id}/contribute`.
- `POST/PUT/DELETE /family/budgets[/{id}]`; list/report via `GET /dashboard?scope=family`.
- `GET/POST /family/expenses`; shared expense history is append-only in this beta.
- `GET /family/participants`, `GET /family/reimbursements`, `POST /family/reimbursements/{share_id}/settle`.
- `POST /family/bills`, `POST /family/bills/{id}/pay`: creates/remembers occurrences, no duplicate payment.
- `GET/POST /goals?scope=family`, `PUT/PATCH /goals/{id}`, `POST /goals/{id}/contribute`.

All finance writes require current entitlement and permission; membership revocations/removals are checked against the database despite old JWTs. After Family Pack expiry/downgrade, authorized shared history remains readable while shared editing stops. No ownership transfer, email-delivery service, wallet withdrawal or shared-expense reversal UI is claimed. Settlement credits the original personal payer account; archived original accounts must be restored before repayment. Historic debts remain visible after membership removal; settlement currently requires active membership.

See [TEST_REPORT.md](TEST_REPORT.md) for SQLite/MySQL/browser evidence and [DATABASE_AUDIT.md](DATABASE_AUDIT.md) for preserved legacy tables and concurrency limitations.

---

# Family Management

Implemented using the existing `families`, `family_memberships`, `subscriptions`,
`users`, and `auth_identities` tables. The initial membership implementation required no migration. The Phase 2 schema extension and its approval/results are documented below.
Existing sidebar, layout, login UI, and financial CRUD pages are preserved.

## Behavior

- Password and Google registration create one owner family and active Free
  subscription in the same transaction as the user. Login never creates families.
- Family currency defaults to LKR. Existing personal currencies are preserved;
  family aggregation rejects non-LKR accounts rather than adding incompatible currencies.
- Roles in family API responses derive from the existing owner relationship.
  Membership is checked against the database on every request.
- Owners see the overview and active member list; members see basic family
  information and only their own membership.
- `POST /family/members` reuses registration password validation, Argon2, and
  the existing identity model. Name/email limits match the inspected MySQL columns.
- Free allows 3 active users including the owner; Premium allows 7. Premium
  requires an active, unexpired subscription on the owner. No payment/upgrade API
  was added because none exists in the current application.
- Member creation locks the family row and uses locking current reads for the
  capacity check, serializing additions under MySQL InnoDB. Duplicate email races
  also hit the existing database unique constraint.
- `DELETE /family/members/{user_id}` changes membership status to `removed`.
  It never deletes/deactivates the user or financial records. Existing JWTs lose
  family access on subsequent requests; personal access remains available.
- `/dashboard?scope=me` preserves the personal response. `scope=family` is owner-only,
  aggregates active household users, excludes transfers/deleted transactions,
  combines budget categories once, and omits individual transactions/goals.
- The existing dashboard charts and cards provide both scopes. The family scope
  displays combined budgets instead of individual transaction and goal details.
- The membership table has no join timestamp; the UI reports “Not recorded”.
- New members complete the existing onboarding flow before using the dashboard.

## Legacy accounts: review before applying

The dry run found 11 eligible existing users (IDs 1–11), all without families.
No existing users were changed. The optional data-only backfill creates one Free
family, owner membership, and subscription per eligible user and changes their
role from `user` to `owner`. It preserves all financial records and currencies.
It skips anyone with family ownership, any membership history, or a subscription.
The whole backfill uses one transaction. It never runs during login or startup.

From the repository root, review:

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/backfill_families.py
```

Only after reviewing the dry run and approving that data change, apply explicitly:

```bash
PYTHONPATH=. .venv/bin/python scripts/backfill_families.py --apply
```

This is a data backfill, not an Alembic schema change. Do not run the unrelated
Accounts repair migration for this feature. The Alembic version table was empty during the initial implementation; the independent feature branch now records later migrations.

## Run

Backend, using the existing environment configuration:

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend in a separate terminal:

```bash
cd frontend
npm run dev
```

Open `/dashboard/family` after login/onboarding. Existing accounts need the reviewed
backfill first; new registrations are provisioned automatically.

## Test

Install test dependencies if missing:

```bash
cd backend
.venv/bin/python -m pip install -r requirements-test.txt
```

API suite with an isolated in-memory SQLite database:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Actual configured MySQL schema, with unique test emails, savepoints and an outer
transaction that is always rolled back. This needs normal DML permissions, and
consumes auto-increment sequence values even though all inserted rows roll back:

```bash
FAMILY_TEST_MYSQL=1 .venv/bin/python -m unittest discover -s tests -v
```

Desktop/mobile Chrome checks use an isolated temporary SQLite file and test-only
API/Vite servers on ports 8765 and 5174. They do not change MySQL or `.env`.
Requires `/usr/bin/google-chrome` and both test ports to be available:

```bash
.venv/bin/python tests/family_browser.py
```

Frontend build and lint, from the repository root:

```bash
cd frontend
npm run build
./node_modules/.bin/eslint src/pages/userdashboard/family/FamilyPage.jsx src/pages/userdashboard/dashboard/DashboardOverview.jsx src/App.jsx
npm test
```

## Initial validation results (historical)

- API suite: 10/10 passed on SQLite and 10/10 passed against live MySQL.
  Covers owner provisioning, login, password safety, family/member visibility,
  Free/Premium capacity and expiration, duplicate/invalid inputs, cross-family
  and member authorization, owner self-removal denial, safe removal with existing
  JWTs, personal account/budget access, financial totals/budgets/trends/transfer
  exclusion, expired JWTs, inactive accounts, and unchanged legacy login behavior.
- Chrome: passed owner add/limit/remove/confirmation, refresh persistence, dashboard
  scope switching, member privacy, actual member onboarding, desktop/mobile layout,
  no mobile viewport overflow, and no owner-page JavaScript errors.
- Production build: passed; Vite reports its existing large-bundle advisory.
- Targeted frontend lint and Python compilation: passed.
- Legacy backfill: dry run passed; 11 eligible users; NOT applied.
- Existing `npm test`: failed before executing auth assertions because its Node
  import cannot resolve `src/services/authApi`. The tests also describe an older
  `/api/auth`/OAuth form contract. Authentication was not rewritten to satisfy them.

## Initial validation limits (see Phase 2 results below)

A real multi-connection MySQL creation race has not been exercised. The savepoint
suite checks capacity serially and cannot prove concurrent scheduling. Row locking
is implemented, but this race still needs an isolated, shared MySQL test database.
An attempt to create temporary test tables was denied by the configured DB account;
the passing MySQL suite instead uses rollback-only transactions. Browser refresh
persistence was tested on isolated SQLite; MySQL commit/reconnect persistence and
browser flows against production data were deliberately not exercised.
Google provider exchange was not exercised against a real Google account.

## Files changed for this task

Existing files modified (unrelated pre-existing edits were preserved):

- `backend/app/main.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/dashboard.py`
- `frontend/src/App.jsx`
- `frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx`

New files:

- `backend/app/core/plans.py`
- `backend/app/models/family.py`
- `backend/app/routers/family.py`
- `backend/app/schemas/family.py`
- `backend/app/services/family.py`
- `backend/requirements-test.txt`
- `backend/scripts/backfill_families.py`
- `backend/tests/test_family.py`
- `backend/tests/family_browser.py`
- `frontend/src/pages/userdashboard/family/FamilyPage.jsx`
- `frontend/src/pages/userdashboard/family/FamilyPage.css`
- `FAMILY_MANAGEMENT.md`

## Phase 2: shared goals and household reporting (13 November 2026)

The original membership architecture and owner-only aggregate permission remain.
Members can participate in explicitly shared family goals; they do not gain access
to `/dashboard?scope=family`, other personal goals, transactions or account details.
No trial is activated and the billing backend is unchanged.

### Compatible schema extension

Read-only inspection confirmed that `goal_contributions.goal_id` references the
legacy `savings_goals` table, not the current `goals` table. Do not relink these
historical IDs or infer a contributor for old rows.

Review [the migration](backend/migrations/versions/20261113_shared_goals.py):

- Add nullable `goals.family_id` with its family FK and index.
- Widen legacy `goal_contributions.goal_id` to allow NULL, retaining its existing
  `savings_goals` FK and every existing value.
- Add nullable `current_goal_id`, `user_id`, and `request_id`, indexes, FKs and a
  unique `(user_id, request_id)` constraint for new ledger entries.
- No existing row is updated, moved, linked to a different goal, or backfilled.
- No table/column is dropped; automatic destructive downgrade is disabled.

The migration intentionally changes the nullability of an existing ledger column.
It needs explicit review/approval before execution on the configured database;
MySQL ALTER operations may hold metadata locks. The legacy backfill and legacy
Accounts repair are not part of this migration. Apply only the feature branch,
after approval and an appropriate backup/maintenance review:

```bash
cd backend
.venv/bin/alembic upgrade maxbud_features@head
```

Do not start the updated application against an unmigrated database: the current
Goal mapping now includes the new column. SQLite tests create an isolated current
schema; they do not migrate the configured MySQL database.

### APIs and ledger policy

Existing routes are extended, rather than duplicated:

- `GET /goals?scope=me` remains personal only, including for an owner.
- `GET /goals?scope=family` returns the current family's shared goals and ledger
  to active participants. Every request rechecks current membership in MySQL.
- `POST /goals?scope=family` is owner-only. A shared goal starts at zero; initial
  savings must be recorded as authenticated contributions. Owner-created shared
  goals count toward the existing owner's active-goal plan limit.
- Existing `PUT /goals/{id}` and `PATCH /goals/{id}` manage shared metadata and
  archive/restore only for the owner. Ledger balances cannot be edited directly,
  and a target cannot be reduced below the recorded total.
- `POST /goals/{id}/contribute` accepts an amount and a required `request_id` for
  shared goals. The author comes only from the authenticated user. Extra identity
  fields are rejected. Replays return the same ledger state; reusing a key with
  different details returns 409. No API edits another member's ledger entry.
- Contribution records are append-only. A removed member's history is retained
  and labeled former/inactive in the shared view. The removed member retains
  personal records but cannot read or contribute to family goals, even using an
  existing JWT. Contribution reversals/withdrawals are not implemented.
- Contributions are manual savings allocations, not verified bank deposits,
  transactions, account transfers or income. They do not change account balances.
- Shared goals use LKR only. Mismatched active household user/account currencies
  block new contributions rather than applying an invented conversion rate.
- Family locks, current locking membership reads and a unique ledger key protect
  capacity and contributions. Inactive accounts continue occupying membership
  seats until removed, avoiding an over-capacity household on reactivation.

### Family financial policy and UI

The existing DashboardOverview gains owner-only member income/expense/net cash
flow summaries, shared allocations, shared-goal totals, and upcoming payment
aggregates. Family Management provides shared goal creation, edit, contribution,
archive/restore and contribution history in the existing glass-card layout.
The owner has links to the existing family report and Subscription page.

Current family finances continue to aggregate **active memberships with active
accounts**, preserving the established removal policy. Removed users' financial
history is not included in current household totals or exposed through private
transaction details. Historical shared contributions remain visible in the shared
ledger. Individual member summaries contain totals, not private transactions.
Upcoming household bills are grouped by category/due date; private bill names,
account identifiers and per-member bill details are omitted.

Cash balance and monthly net cash flow are distinct. The existing Safe to Spend
method reserves personal savings plus each active user's recorded shared savings
allocations, remaining budgets and unpaid commitments. Shared goal totals are not
counted as income or subtracted twice from the owner's personal balance. Historical
allocations by removed members are not assumed available in active household cash.

### Additional verification commands

```bash
cd backend
.venv/bin/python -m unittest discover -s tests -v
FAMILY_TEST_MYSQL=1 .venv/bin/python -m unittest discover -s tests -v
# Requires permission to create/drop an isolated UUID-named test database.
# Clones DDL only; no customer records are copied or changed.
PYTHONPATH=. .venv/bin/python tests/family_mysql_races.py
.venv/bin/python tests/family_browser.py
```

The concurrency script tests the exact migration against the cloned legacy schema,
asserts the legacy contribution and FK are unchanged, then sends eight simultaneous
member additions and concurrent duplicate owner/member contributions. It removes
only its newly created `maxbud_family_test_*` database in cleanup. It never runs a
migration on the configured customer database.


### Phase 2 actual verification results

- The reviewed feature migration was approved and applied to the configured local
  MySQL database. Its recorded revision is `20261113_shared_goals`. Read-only
  inspection confirmed `goal_contributions.goal_id` still references
  `savings_goals`, and is now nullable. No legacy backfill or row relinking ran.
- Backend suite: **27 passed on SQLite** and **27 passed against MySQL**. MySQL
  fixture records were held under outer transactions and rolled back. Tests consume
  auto-increment values; they do not reset them or retain customer-like test rows.
- Tests verify the full owner/member onboarding and income/expense journey,
  separate personal/family totals, actual member net cash flow, 300 + 200 = 500,
  authenticated contribution authorship, duplicate/conflicting requests, owner-only
  goal changes, archive/restore/completion, family isolation, removed/inactive member
  access, historical contribution retention, private bill omission, currency
  mismatch and Premium expiry. Existing Free/Premium/member/auth/finance tests pass.
- Family Chrome flow: **passed** owner add/limit/remove/refresh, member onboarding,
  personal/family scope, membership privacy, owner and member shared contributions,
  refreshed total 500 and two ledger entries, existing accounts/goals/reminders/
  reports/settings/AI pages, desktop/mobile, and no page errors. An earlier run
  timed out on Add Member; the subsequent diagnostic run and full flow passed.
- Phase 1 responsive Chrome sweep: **passed** all 12 dashboard pages at 360, 768,
  1280 and 1600px, landing feature grids/FAQ, sidebar collapse/mobile navigation,
  overview hierarchy, real subscription plan/usage, and advisor suggestion/error
  behavior. No viewport overflow or page errors were detected. The final sweep
  also verifies that resizing an open mobile drawer to desktop releases scroll locking.
- Frontend authentication tests: **5 passed**. Targeted ESLint, production build,
  Python compilation and `git diff --check`: **passed**. The existing Vite
  main-bundle size warning and Starlette httpx deprecation warning remain.
- Auth router, Login, Register and Onboarding source hashes match the pre-UI-phase
  snapshot. The approved hero CSS block is byte-for-byte unchanged. No `.env`
  file was edited or exposed. Phase 1 UI work is preserved.

### Remaining verification limits / required external action

The true multi-connection MySQL race/migration-clone script **did not run its
assertions**: MySQL denied `CREATE DATABASE` (error 1044) for the configured
restricted account. No disposable database was created. Locking and unique-key
protections are implemented and serial duplicate/capacity tests pass, but this is
not proof of concurrent scheduling. To run that script, a DBA must authorize a
separate test account with schema-read access to the source and create/alter/drop
permissions limited to the disposable `maxbud_family_test_*` namespace, or provide
an isolated test server containing a schema-only copy. Do not broaden the runtime
account's production permissions merely to run tests. Supply approved test
credentials through the test process environment; do not publish secrets.

The exact migration was applied locally, but its clone-and-legacy-row preservation
assertion was blocked along with the race test. The migration code contains no row
updates and the legacy FK was inspected afterward. Take a verified backup and
review MySQL metadata-lock effects before applying it on another deployment.

MySQL tests establish transactional persistence and refresh behavior with rollback;
independent-connection durable commit/reconnect testing on an isolated MySQL database
remains part of the blocked test. Browser refresh/re-login persistence uses isolated
SQLite. No real customer records were changed for these tests.

Member access to household aggregates remains deliberately unavailable. There is
no new owner-sharing permission toggle. Shared-goal access is restricted to active
family membership and does not grant aggregate reporting permissions. Contributions
are allocations, not bank-verified deposits; reversals/withdrawals remain absent.
Premium trial activation and payment processing remain outside this phase.

### Phase 2 modified/new files

- `backend/app/models/finance.py`
- `backend/app/routers/family.py`
- `backend/app/routers/goals.py`
- `backend/app/routers/dashboard.py`
- `backend/app/services/family.py`
- `backend/app/services/goals.py` (new)
- `backend/migrations/versions/20261113_shared_goals.py` (new)
- `backend/tests/test_shared_family.py` (new)
- `backend/tests/family_mysql_races.py` (new, blocked by DB privileges)
- `backend/tests/family_browser.py`
- `frontend/src/pages/userdashboard/family/FamilyPage.jsx`
- `frontend/src/pages/userdashboard/family/FamilyPage.css`
- `frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx`
- `FAMILY_MANAGEMENT.md`

No commit or push was made.
