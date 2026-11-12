# Family Management

Implemented using the existing `families`, `family_memberships`, `subscriptions`,
`users`, and `auth_identities` tables. No schema migration is required or was run.
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
Accounts repair migration for this feature. The existing Alembic version table is empty.

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

## Actual validation results

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

## Remaining validation limits

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
