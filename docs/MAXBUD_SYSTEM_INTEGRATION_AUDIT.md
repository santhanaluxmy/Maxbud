# MaxBud system integration audit

Audit date: 17 November 2026, Asia/Colombo; final connectivity snapshot at 12:52. Workspace: `/home/uki-jaffna/Documents/MaxBud`. Initial Git HEAD: `29f4eea` (`family management setting version 2`). This report describes observed snapshots of a changing, uncommitted workspace.

## Scope and evidence boundaries

This is verification and reporting only. Only this report is intentionally added to the repository. Application source, environment files, migrations, dependencies and existing financial records were not edited. No migrations, database resets, grants, installs, commits, deployments or server restarts were performed. The other session continued changing authentication, billing, family management and UI files during inspection. Tests imported the source available when their processes started; this is not a frozen release certification.

MySQL inspection used the configured SQLAlchemy engine, read-only SELECT/schema metadata queries, and an explicitly read-only transaction followed by rollback. Tests used fresh in-memory SQLite or newly created temporary SQLite databases. `FAMILY_TEST_MYSQL=0` was explicit; additional targeted probes blocked MySQL connections through an engine event hook. Exercised Groq, Google verification, SMTP and Stripe test operations were mocked. No real credentials, JWTs, recovery codes, receipt contents or personal records are included.

`VERIFIED WORKING` applies only to the specific behavior exercised. SQLite results do not verify MySQL writes or InnoDB concurrency. A production build does not verify a complete authenticated browser journey.

## 1. Module matrix

| Module | Frontend | Backend | MySQL | Verification Evidence | Status |
|---|---|---|---|---|---|
| Configured database connection | N/A | Actual SQLAlchemy engine connected | `maxbud_db`; SELECT 1 succeeded | Read-only engine queries; MySQL 8.0.46 | VERIFIED WORKING |
| Schema/migrations | N/A | Existing models largely match; new access tables absent | Revision `20261115_beta`; two source heads | Inspector, Alembic metadata, FK/count checks | PARTIALLY WORKING |
| Normal API availability | API base targets 8000 | Healthy initially; transient outage; recovered | Configured engine reachable at final check | Health 200, intervening refusal/502, final direct/proxy 200 | PARTIALLY WORKING |
| Public React pages | Landing/login/register/recovery rendered | No writes submitted | N/A | Separate browser, fresh profile, writes blocked; no page exceptions | VERIFIED WORKING |
| Frontend/API integration | Vite health 200, transient 502, recovered | Reachable at final check | No authenticated write/read round trip | HTTP checks and intervening browser health failure | PARTIALLY WORKING |
| Registration/login | JSON and session tests pass | Trial/password/JWT/role tests pass in SQLite | No live account inserted or logged in | 9 auth tests; public forms rendered | CODE PRESENT, NOT END-TO-END VERIFIED |
| Onboarding | Matching steps and redirects present | Isolated persistence/order tests pass | No live writes | Feature/core-flow tests | CODE PRESENT, NOT END-TO-END VERIFIED |
| Personal finance | Routes/forms present; build/lint pass | Core tests pass; one fixture regression | Integrity checks clean; writes untested | 17 core and 12 feature tests | CODE PRESENT, NOT END-TO-END VERIFIED |
| Receipt scanner | Review/confirmation UI present | Mocked happy path passes; long-category save fails | Tables/FKs present; no dangling confirmed receipt found | Receipt regressions and independent boundary probe | PARTIALLY WORKING |
| AI advisor | Rendering/escaping tests pass | Mocked context/history/quota/error tests pass | Live provider/write untested | Feature/beta and advisor tests | CODE PRESENT, NOT END-TO-END VERIFIED |
| Family management | Shared finance/report screens present | Capacity/privacy/splitting tests pass in SQLite | No household records changed | 10 Family Pack and 5 shared-family tests plus beta | CODE PRESENT, NOT END-TO-END VERIFIED |
| Existing local Family sandbox | Port 5184 refused connection | Port 8011 refused connection | SQLite, not `maxbud_db` | HTTP checks; temporary sandbox test timeout | BLOCKED |
| Trial/demo subscriptions | Subscription UI present | Calendar/lifecycle tests pass; actual demo disabled | Fields present | Auth/beta/improvement tests; catalog | CODE PRESENT, NOT END-TO-END VERIFIED |
| Stripe sandbox | Checkout/portal wired | Implemented and under development | Mapping/event tables absent | Mocked tests pass; actual readiness incomplete | IN PROGRESS IN OTHER CODEX SESSION |
| Password recovery | Recovery page renders | Mocked flow passes; SMTP/tables missing | Recovery/session tables absent | Browser and improvement tests | IN PROGRESS IN OTHER CODEX SESSION |
| Admin | Unsigned navigation redirects | Database-backed admin role required | No genuine admin session used | 5 admin tests; initial unsigned API 401 | CODE PRESENT, NOT END-TO-END VERIFIED |

## 2. Architecture and configuration

Backend entry point: `backend/app/main.py`, exporting `app`. It registers auth, recovery, billing, onboarding, accounts/transfers, transactions, dashboard, budgets, goals, reminders, family/household, settings/export, notifications, AI, subscriptions and admin. Startup and `/health` run SELECT 1; neither establishes feature-level schema readiness.

`backend/app/database.py` creates a `mysql+pymysql` engine with pre-ping, recycling and hidden SQL parameters. `get_db()` yields/closes a request session; routes/services commit explicitly. There is no automatic successful-request commit.

Frontend entry: `frontend/src/main.jsx`; routes: `frontend/src/App.jsx`. BrowserRouter wraps React, with conditional GoogleOAuthProvider. The dashboard shares `Dashboard.jsx` across accounts, transactions, budgets, goals and reports. Other modules have dedicated pages. Client guards check stored authentication/onboarding; backend authorization independently protects data.

`frontend/src/api/base.js` uses `VITE_API_URL`, then `VITE_BACKEND_URL`, then `/api`. The inspected frontend `.env` sets **`VITE_API_URL=http://127.0.0.1:8000`**. Actual application requests therefore bypass Vite's proxy. `frontend/vite.config.js` separately rewrites `/api/*` to port 8000 by default, overridable with `API_PROXY_TARGET`. Proxy success alone does not verify the configured direct browser API path.

Actual backend settings: development; DB `127.0.0.1:3306/maxbud_db`; frontend origin `http://localhost:5173`; JWT lifetime 360 minutes; rate limiting enabled; demo payments disabled; six-person family limit. DB TLS CA is unset for loopback development. Production/beta enforce HTTPS origin, DB CA and rate limiting; production rejects demo/test billing entitlements.

Environment names inspected without exposing secret values:

- Database: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL_CA`.
- Auth/security: `JWT_SECRET`, `JWT_MINUTES`, `GOOGLE_CLIENT_ID`, `ENVIRONMENT`, `RATE_LIMIT_ENABLED`, `FRONTEND_ORIGIN`.
- AI: `GROQ_API_KEY`, `GROQ_CHAT_MODEL`, `GROQ_VISION_MODEL`, `RECEIPT_STORAGE_DIR`; older OPENAI settings remain, but the active adapter uses Groq.
- Plans: `DEMO_PAYMENTS_ENABLED`, `PLAN_PRICES_JSON`, `FAMILY_PACK_MEMBER_LIMIT`.
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SECURITY`.
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PREMIUM_MONTHLY`, `STRIPE_PRICE_PREMIUM_YEARLY`, `STRIPE_PRICE_FAMILY_MONTHLY`, `STRIPE_PRICE_FAMILY_YEARLY`, `STRIPE_PORTAL_CONFIGURATION`.
- Frontend/proxy: `VITE_API_URL`/`VITE_BACKEND_URL`, `VITE_GOOGLE_CLIENT_ID`, `API_PROXY_TARGET`.

The actual backend `.env` also contains `ACCESS_TOKEN_MINUTES`, `CORS_ORIGINS`, `STRIPE_MODE`, `STRIPE_PUBLISHABLE_KEY` and differently named `STRIPE_*_PRICE_ID` variables. These are not current Settings fields; `extra="ignore"` silently ignores them. JWT duration comes from `JWT_MINUTES`, CORS from `FRONTEND_ORIGIN`/development defaults, and the price-name mismatch blocks billing. Both `.env` files are git-ignored and absent from `git ls-files`.

Dependencies are declared in backend requirements files and frontend package/lock files. Observed installed versions: FastAPI 0.162.0, Starlette 1.10.0, SQLAlchemy 2.0.55, PyMySQL 1.2.3, Alembic 1.20.1, httpx 0.28.1, Groq 1.7.0, requests 2.34.2, pwdlib 0.3.1, PyJWT 2.15.1, Pillow 12.3.0, python-multipart 0.0.32 and Vite 8.3.5. Nothing was installed. Frontend backup source trees are outside active entry-point imports and ignored by ESLint.

## 3. Actual MySQL connection, tables and migrations

Configured-engine observations:

```text
SELECT 1 -> 1
SELECT DATABASE() -> maxbud_db
MySQL -> 8.0.46-0ubuntu0.24.04.4
Port -> 3306
alembic_version -> 20261115_beta
```

SQLAlchemy authenticated successfully. The first restricted attempt returned error 2003 with `[Errno 1] Operation not permitted`; the permitted read-only retry succeeded. That was a tool network restriction, not invalid MySQL credentials. No grants were changed.

The 36 observed tables:

```text
account_legacy_map              account_transfer_records
account_transfers               accounts
advisor_messages                ai_scans
ai_usage                        alembic_version
auth_identities                 authentication_identities
budgets                         categories
demo_checkouts                  families
family_invitations              family_memberships
financial_accounts              goal_contributions
goals                           household_expense_shares
household_settlements           income_sources
merchant_rules                  monthly_budgets
notification_reads              onboarding_profiles
payment_reminders               platform_events
reminder_payments               savings_goals
subscriptions                   transaction_audit_logs
transaction_requests            transactions
user_profiles                   users
```

Current source additionally registers `auth_session_versions`, `password_recoveries`, `stripe_test_accounts` and `stripe_test_events`; all four were absent at schema inspection. Their additive migration is `backend/migrations/versions/20261117_access.py`, descended from beta. It was not applied by this audit.

Source heads are **`20261104_accounts` and `20261117_access`**. Accounts and reminders start independent root branches. Read-only `ScriptDirectory.get_current_head()` raised:

```text
CommandError: The script directory has multiple heads (due to branching).
Please use get_heads(), or merge the branches using alembic merge.
```

Thus generic single-head resolution is ambiguous. No upgrade was executed. The applied beta revision does not establish that the independent accounts root is represented in revision history; the existing accounts schema itself was inspected successfully.

Normalized comparisons found no missing columns on existing mapped tables, no financial precision/scale mismatch, no missing declared indexes and no missing declared unique constraints. NUMERIC versus DECIMAL, TINYINT versus Boolean and reflected collations were normalized, not reported as false defects.

| Financial fields | Actual MySQL type |
|---|---|
| Account opening balances, income sources, transactions, transfer records | DECIMAL(14,2) |
| Goal contributions, reminders, demo checkout amounts, expense shares, settlements | DECIMAL(14,2) |
| Budget limits, current goal targets and saved amounts | DECIMAL(12,2) |

MySQL permits NULL for transaction category/description, while ORM/response types expect strings. Both active-NULL counts were zero. Generated `budgets.family_scope` also reflects nullable despite its non-null model annotation; its COALESCE expression is the semantic guard.

Inspected single-column FK orphan checks returned no orphan rows. Additional aggregate checks returned **zero** for private transaction/account ownership mismatches, wrong-family wallet references, shared personal payments with wrong owners, nonpositive active transactions, personal currency mismatches, transfer headers without two balanced active entries, confirmed scans missing a valid transaction, and unmapped legacy financial accounts.

Aggregate snapshot: 16 transactions, 18 current accounts, 43 budgets, 7 goals, 1 AI scan, 13 current auth identities, 2 platform events, 0 transaction audit rows. Legacy authentication identities, financial accounts, monthly budgets and savings goals were empty. Other unmapped legacy/support tables include account maps/transfers, onboarding profiles, transaction audit logs and user profiles. Their existence alone is not a confirmed failure; no deletion is recommended.

Transactions/transfers have explicit commits and rollback handling; receipt confirmation inserts and links before one commit. Request session closure rolls back uncommitted exceptions, but unexpected database exceptions generally become generic 500 responses. Database-outage UX, every failed-commit path and concurrent MySQL locking were not exercised. No live commit/retrieval round trip was attempted.

## 4. Running environments and frontend/backend connectivity

| Environment | Frontend | Backend | Database | Observation |
|---|---|---|---|---|
| Normal | `127.0.0.1:5173`, configured origin `localhost:5173` | `127.0.0.1:8000` | Configured SQLAlchemy: MySQL `maxbud_db` | Initially available; transient outage; recovered at final check |
| Existing Family sandbox | `127.0.0.1:5184` | `127.0.0.1:8011` | `backend/.local-family-test/sandbox.db`, SQLite | Both ports refused connections; neither started by this audit |
| Audit tests | Unit/render tests and separate public-page browser | In-process TestClient | Fresh SQLite memory/temporary files | Separate from both existing environments |

Initial HTTP evidence:

- Direct `/health` on 8000: 200, `{"status":"ok","database":"connected"}`.
- `/openapi.json`: 200, expected API title/routes, including recovery and Stripe.
- Unsigned `/auth/me` and `/admin/overview`: 401, `Not authenticated`.
- Frontend `/`: 200 with Vite HTML; proxied `/api/health`: 200.
- Direct and proxied `/subscriptions/plans`: 200, matching catalog.
- CORS preflight from `http://localhost:5173`: 200 with matching allow-origin. Normal API preflight from sandbox origin `http://127.0.0.1:5184`: 400/no allow-origin, consistent with distinct environments.

A later recheck returned **`[Errno 111] Connection refused`** on port 8000 and **502** from frontend `/api/health`. The separate browser's direct API health fetch failed as well. No server was stopped/restarted by this audit. The reason for the listener disappearing was not established. Association with ongoing implementation is possible, not proven. Initial success does not demonstrate continuous availability.

**Final recheck, 12:52 Asia/Colombo:** direct `/health` on 8000 and proxied `/api/health` on 5173 both returned 200 with `database: connected`. The independently queried SQLAlchemy engine again returned SELECT 1 = 1, database `maxbud_db`, revision `20261115_beta`. Ports 8011 and 5184 still refused connections. This establishes recovery of HTTP connectivity, not a completed authenticated browser/MySQL write flow.

Health does not expose runtime database identity. The separately executed configured engine positively identified `maxbud_db`; the initial live response proves only that the API's own health check connected to a database. A complete authenticated React → FastAPI → MySQL → FastAPI → React persistence chain remains **not end-to-end verified**.

No confirmed method/path mismatch was found among inspected active frontend callers and backend declarations. Auth sends JSON; finance attaches Bearer JWTs; transaction retries support `Idempotency-Key`; relevant forms preserve decimal strings. Receipt upload uses its own FormData fetch; confirmation uses the common JSON client. `/forgot-password` was added during inspection and rendered by the public-page check; an earlier missing-route observation is not retained as a current defect.

The common client clears authentication/redirects on 401, parses validation-array errors and accepts caller abort signals. Auth helpers check local JWT expiry. There is no refresh-token flow or default browser request deadline in the common client, auth helper or receipt upload. Provider timeouts are 45 seconds for Groq and 20 seconds for Stripe, which do not bound all browser requests.

## 5. Registration, login and onboarding results

Registration fields match: full name, email, password and confirmation. Isolated tests passed for normalization, duplicate rejection, server-assigned user role, Argon2 hashing, persisted three-calendar-month trial and no automatic household creation. Login preserves the trial period, supports current hashes/legacy bcrypt, rejects corrupt hashes, denies disabled users and returns current onboarding/role state. JWTs use HS256 with required subject/expiry; authorization reloads active user/session state. Missing/expired/tampered-token tests passed.

Frontend session tests passed for exactly one remembered/session storage record, error messages and expiry handling. Login/register forms rendered without browser exceptions. No genuine user's correct password was supplied or used, and no live registration was submitted. Google token verification was mocked; live Google sign-in remains unverified.

Onboarding implements ordered about-you, income, accounts, budgets and goals. Backend step/completion state persists; the frontend resumes from `/onboarding/status` and updates stored completion after the final step. Isolated tests covered ordering, replay prevention, lengths, limits, completion and a complete core-finance sequence. Income sources are forecasts, not automatically posted cash income. No live onboarding record was changed.

## 6. Personal finance and exact financial verification

Seventeen core tests passed, alongside feature/family/beta coverage. Exercised behaviors include ownership, balance calculations, income edits/moves/deletes, rejection of deleting spent income or reducing opening balances into overdraft, transaction idempotency, soft deletion, protected transfer/receipt/reminder entries, savings replay/rollback, reminders, budget/dashboard recomputation and month filtering.

Concrete passing synthetic core-flow example: initial funds 100; posted income 1000; expense 40; transfer 100 to another personal account; savings allocation 25; reminder payment 50. Account balances became **910 and 100**, monthly income **1000**, expenses **90**, allocated savings **25**, safe-to-spend estimate **925**, and cash-flow closing balance **1010**. Transfer did not add income; savings did not create an expense. These are SQLite results, not MySQL write verification.

Backend money calculations use Decimal and MySQL money fields use DECIMAL. Transfers/reimbursements use paired transfer movements, excluded from ordinary income/expense totals. Household funding is separate from shared income. Equal/custom/percentage split and partial-reimbursement tests passed; remainder cents are distributed deterministically. Savings allocations are contribution records, not account movements.

Personal cash-flow includes archived personal accounts, prior dated movements and shared expenses paid from the user's own account, while excluding household wallets. Personal dashboard spending excludes explicitly shared spending; the cash-flow `basis` explains this distinction. Account opening dates are not modeled, so historical openings use recorded opening balances as their baseline.

One existing cash-flow test failed: opening balance **0.00 instead of 1500**. An independent probe showed an uncommitted account count changing **1 → 0 across authenticated `GET /auth/me`**. The new session-version helper inspects the Engine rather than the active Session connection, interacting incorrectly with the shared single-connection SQLite fixture. This establishes a fixture/transaction-ownership regression, not lost MySQL records or proven wrong MySQL totals. The empty-month cash-flow test passed. MySQL race tests were not run because their script creates/drops a schema; the live-MySQL rollback fixture was also not selected.

## 7. Receipt scanner result

Current code caps image reads at 5 MB, accepts/decodes JPG/PNG, rejects decompression bombs, normalizes/re-encodes images and stores them under generated private filenames. Extraction validation preserves unknown totals/currency for review, restricts categories to authenticated personal expenses, deduplicates image hashes and separates successful usage from failed provider requests.

Mocked tests passed for upload → review with no transaction yet → user correction/account selection → one saved transaction, replay-safe confirmation, ownership denial, invalid upload, missing printed total and provider-failure usage handling. Confirmation creates a Transaction and links AIScan before committing. The UI checks confirmed status plus transaction ID before displaying success.

**The prior unreliable-save concern cannot be declared fully fixed.** An independent disposable SQLite reproduction found:

```text
Existing Category name length: 61
GET /ai/categories includes it: true
POST /ai/receipts/{id}/confirm:
  ValidationError in TransactionIn.category: at most 60 characters
Saved transaction count: 0
```

Category storage and ConfirmReceipt allow 100 characters, but nested TransactionIn allows 60. The handler raises an uncaught internal validation exception, not a controlled request-validation 422. The reproduced boundary is 61–100 characters; this does not imply every ordinary receipt save fails.

No live Groq receipt request was made. Real image recognition, provider/model validity, MySQL receipt save, browser refresh and resulting Transactions/dashboard/report presentation remain unverified. Zero dangling confirmed-receipt links were found in MySQL; that count cannot prove future save reliability.

## 8. AI advisor result

The Groq adapter uses bounded requests and exposes no write tools. Advisor context contains only the authenticated user's personal financial summary, goals, upcoming bills and limited own history. Tests verified context/privacy, cross-user history denial, successful history persistence/idempotency, monthly entitlement limits and failed-provider requests not consuming successful usage.

Frontend tests exercised structured JSON, Tamil text, headings/lists/currency, malformed replies and escaped HTML. No unsafe raw HTML was observed in the exercised renderer. Groq key/model fields were nonempty, but no live call validated the credentials or model availability.

## 9. Family management result

Family Pack permits six people total: owner plus five. Hashed expiring invitations enforce exact recipient email, reserved capacity and owner permissions. Invitations are manually shared links; the API explicitly says no email was sent. Tokens use URL fragments and are removed from the address bar for post-login acceptance.

Family/beta/Family Pack/shared-goal tests exercised capacity, expiry/reuse, cross-family denial, view/add revocation, personal privacy, removal, shared income/expenses, wallets/funding, budgets/goals/bills, contribution history, settlements and sponsor downgrade/expiry. Five shared-family tests passed separately. Removed members lose shared access while personal records and historical contributions remain. Membership does not upgrade personal AI limits or cancel personal subscriptions. Improvement tests verified permitted shared access despite expired personal trial.

The shared dashboard returns explicit shared monthly income/expenses, wallet funding/net movement, budgets/goals, member aggregates, debts and six-month trends. Frontend labels distinguish monthly values and all-time goal allocations. A new `/family/activity` implementation appeared during parallel work; source/build were inspected, but authenticated browser behavior and the live route were not independently verified. The UI explicitly identifies a dated household running-balance ledger as unavailable; aggregates/activity do not establish such a ledger.

No existing household/sandbox records were changed. Both sandbox ports were unavailable. The fresh file-based sandbox test attempt timed out, so grant/expiry/revoke behavior is not certified here.

## 10. Subscriptions, Stripe and recovery

The actual public catalog initially returned a three-calendar-month trial, Premium Individual **LKR 650 monthly**, Family Pack **LKR 900 monthly**, six-person capacity, **yearly prices null**, `demo_enabled=false` and `stripe_test_enabled=false`. Current catalog code fixes monthly amounts and preserves configured annual amounts. Calendar expiry, read-only history/export, demo payment success/failure/replay, cancellation/resumption, yearly periods and shared sponsorship passed isolated tests.

Stripe has implemented test-key/livemode restrictions, price/currency/amount/interval validation, customer mapping, Checkout/pending-session reuse, Portal, timestamped signature verification, durable event deduplication, current subscription re-fetch, invoice/customer/subscription association and lifecycle synchronization. Mocked tests passed for forged signatures, live-key rejection, wrong amounts, no redirect activation, pending-session reuse, retries, renewal, failure and cancellation scheduling.

Actual blockers:

1. Test-prefix secret key present, but webhook secret empty; key validity not checked with Stripe.
2. Expected price fields unset. `.env` uses `STRIPE_PREMIUM_MONTHLY_PRICE_ID`, `STRIPE_PREMIUM_YEARLY_PRICE_ID`, `STRIPE_FAMILY_MONTHLY_PRICE_ID`, `STRIPE_FAMILY_YEARLY_PRICE_ID`; code expects `STRIPE_PRICE_PREMIUM_MONTHLY`, `STRIPE_PRICE_PREMIUM_YEARLY`, `STRIPE_PRICE_FAMILY_MONTHLY`, `STRIPE_PRICE_FAMILY_YEARLY`.
3. Stripe mapping/event tables absent; yearly catalog amounts null.
4. Hosted Checkout, Portal, actual webhook delivery and MySQL activation/renewal were not exercised.
5. Admin billing currently lists demo checkouts/simulated revenue, not complete Stripe invoice/payment reconciliation.

Checkout redirects do not grant access in tested code. Current production live billing is intentionally unsupported by this test-only adapter. Stripe remains **IN PROGRESS IN OTHER CODEX SESSION**; no billing changes were made here.

Recovery has a rendered page and request/verify/reset handlers. Mocked tests passed for hashing, attempts/expiry, unknown-account responses, one-time proofs, new-password login and old-session rejection after recovery reset. Actual SMTP configuration and both recovery/session-version tables are absent. Readiness guards specify 503 for incomplete setup; no real request/email was sent. Recovery reset revocation differs from ordinary settings password changes.

## 11. Admin authorization and security

Every inspected `/admin/*` route depends on `admin()`, which reloads the authenticated user and requires role `admin`. Household owner is separate. Five isolated tests passed for bootstrap, public escalation prevention, non-admin denial, expired/tampered/disabled authentication, admin actions, privacy and simulated billing/audit counts. Live unsigned admin API initially returned 401; unsigned admin browser navigation redirected to login. Genuine admin browser/MySQL operation remains unverified.

Observed controls: Argon2/legacy bcrypt, JWT expiry/signature checks, active-user/session-version lookup, owner/member permissions, ownership/family filters, personal AI/history isolation, entitlement checks, per-worker/IP rate limits with Retry-After, bounded providers, private normalized receipt files, input schemas, server-controlled public roles, parameterized SQL and secret-free admin responses. Rate-limit and malicious-render tests passed. No cross-user/family privacy breach was reproduced.

Confirmed limitation: `PUT /settings/password` changes the hash without incrementing SessionVersion. An independent disposable probe returned **200 for the change and 200 for `/auth/me` with the old JWT afterward**. Recovery reset does increment the version. Old-password rejection during new login does not revoke existing sessions; configured JWT duration is six hours.

Architectural limits: browser tokens remain script-accessible in storage, logout only removes local credentials, no refresh-token flow exists, and per-process rate limiting needs shared/edge enforcement with multiple workers. These are not evidence of an observed data breach. The parallel security/billing work needs final review once it stabilizes.

## 12. Backend test results

The reviewed broad suite was run from `backend`:

```bash
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 timeout 180 \
  .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

It exited **124 at the time limit**. There was no complete-suite pass.

| Module | Completed passed | Completed failed | Qualification |
|---|---:|---:|---|
| `test_admin` | 5 | 0 | Completed module |
| `test_auth_flow` | 9 | 0 | Completed module |
| `test_beta` | 14 | 0 | Completed module |
| `test_cash_flow` | 1 | 1 | Failure reproduced separately |
| `test_core_finance_flow` | 17 | 0 | Completed module |
| `test_family` | 10 | 0 | Completed module |
| `test_family_pack` | 10 | 0 | Completed module |
| `test_features` | 12 | 0 | Completed module |
| Broad-run total | **78** | **1** | Local module did not complete |
| Separate `test_shared_family` | 5 | 0 | Completed |
| Separate `test_requested_improvements.ImprovementTests` | 8 | 0 | Completed; provider calls mocked |
| Separate temporary local sandbox attempt | 1 | 0 | 90-second timeout during expiry test |

Across those processes, **92 distinct methods completed successfully and 1 distinct method failed**. This is a combined count across source snapshots, not a successful 93-test suite. The local sandbox module declares nine tests; only its CLI preview/noninteractive guard completed in the separate attempt. Expiry was still in progress at timeout; the remainder was not reached. Independent probes reproduced the receipt failure, SQLite rollback and old-JWT retention.

Other attempts: the first restricted TestClient run timed out without completed tests. A diagnostic run with a traceback watchdog exited 139 after a traceback/segmentation fault; it supplied no reliable final suite result and is not evidence of a production crash. Starlette emitted an httpx TestClient deprecation warning. No dependency change was made.

Audit-owned temporary evidence: `/tmp/maxbud-system-audit-regression.log`, `/tmp/maxbud-system-audit-cashflow.log`, `/tmp/maxbud-system-audit-probes.log`, `/tmp/maxbud-system-audit-shared-stripe.log`, `/tmp/maxbud-system-audit-remaining.log`, `/tmp/maxbud-system-audit-browser.log`. Decisive results are transcribed here; temporary files are not permanent report dependencies.

## 13. Frontend tests, build and browser results

| Check | Result |
|---|---|
| `npm test` | Exit 0; runner reported 4 test files passed, 0 failed |
| `./node_modules/.bin/eslint src vite.config.js` | Initial and final checks exit 0, no findings |
| Production build to `/tmp/maxbud-system-audit-build` | Exit 0; 2356 modules; large-chunk warning |
| Build after new recovery/UI files, to `/tmp/maxbud-system-audit-build-final` | Build succeeded; main JS 850.97 kB / gzip 245.47 kB; warning retained |
| Public browser smoke | Landing/login/register/recovery rendered, unsigned admin redirected, no recorded page exceptions |
| Browser direct API health | Failed during later outage |
| Final direct API/proxy health, 12:52 | Both returned 200; database engine also connected |

Build arguments were `--configLoader runner --emptyOutDir false`, with output outside the served build. Tests cover API-base normalization, exact amount/header propagation, auth validation/errors/storage/expiry and advisor parsing/escaping. The separate headless browser used a new profile, blocked external services/write methods, and never attached to the other browser session. Initial network-idle attempts timed out; the recorded DOM-ready public-page check completed. No authenticated data-entry browser flow was submitted.

## 14. Confirmed P0/P1/P2 issues

### P0-01 — Receipt confirmation fails for an accepted category

- **Expected:** A selectable existing receipt category saves with otherwise valid data, or produces a controlled validation response.
- **Actual/evidence:** A 61-character category is returned by `/ai/categories`, but confirmation raises uncaught TransactionIn ValidationError and saves zero transactions. Ordinary mocked receipt tests pass; this is the 61–100 character boundary.
- **Files:** `backend/app/models/finance.py` (Category), `backend/app/routers/ai.py:230` and `:255`, `backend/app/schemas/transaction.py:11`, `frontend/src/pages/userdashboard/dashboard/AI.jsx`.
- **API:** `GET /ai/categories`, `POST /ai/receipts/{key}/confirm`.
- **Minimal recommended fix:** Align category/receipt/transaction limits with existing VARCHAR(100) storage; validate nested conversion before the save path. Add a boundary regression verifying one saved transaction and safe replay. Do not silently truncate categories.

### P0-02 — Transient normal API outage, recovered at final check

- **Expected:** Normal backend serves requests while frontend is available.
- **Actual/evidence:** Initial health/catalog 200; later port 8000 refused connections, proxy health returned 502, and browser API fetch failed. At 12:52 direct/proxied health recovered to 200. Cause was not established; no database failure is inferred. This is an observed transient availability incident, not a current permanent outage.
- **Diagnostic files:** `backend/app/main.py` (lifespan/health), `frontend/vite.config.js` (upstream), `frontend/src/api/base.js` (configured origin). No source file is established as the cause.
- **API:** `/health`, frontend `/api/health`; other normal flows depend on the same listener.
- **Minimal recommended fix:** The implementation session should inspect process/reloader/startup logs to explain the interruption and verify stability after development settles. HTTP recovery is confirmed; authenticated browser verification remains pending. This audit did not restart services or change credentials.

### P1-01 — Stripe is not environment/schema-ready

- **Expected:** Monthly/yearly sandbox checkout and verified webhook state persist through MySQL.
- **Actual/evidence:** Webhook secret missing, price variable names ignored, mapping/event tables absent, yearly amounts null, public Stripe availability false. Mocked behavior passes; hosted flow unverified.
- **Files:** `backend/.env` (names only), `backend/app/core/config.py`, `backend/app/services/stripe_test.py:16` and `:42`, `backend/app/services/subscriptions.py:104`, `backend/app/routers/billing.py:20`, `backend/migrations/versions/20261117_access.py`, `frontend/src/pages/userdashboard/dashboard/Upgrade.jsx`.
- **API:** `/subscriptions/plans`, `/billing/stripe/checkout`, `/portal`, `/webhook`.
- **Minimal recommended fix:** Let the other session finish; reconcile names/aliases, test prices/signing secret/yearly amounts and reviewed migration readiness. Then verify hosted checkout, signed delivery/retries, plan changes, renewal/cancel and MySQL entitlements in an authorized isolated environment. A key alone is insufficient.

### P1-02 — Actual password recovery setup is incomplete

- **Expected:** Delivered code can be verified and redeemed once.
- **Actual/evidence:** UI/mock tests work; SMTP and recovery/session tables are absent. Code explicitly guards incomplete setup with 503; no email was attempted.
- **Files:** `backend/app/routers/recovery.py`, `backend/app/services/recovery.py`, `backend/app/models/access.py`, access migration, `frontend/src/pages/login/PasswordRecovery.jsx`.
- **API:** `/auth/recovery/request`, `/verify`, `/reset`.
- **Minimal recommended fix:** Complete the parallel work, configure secure SMTP and reviewed additive schema, then verify actual delivery/reset using an isolated account.

### P1-03 — Session-schema inspection discards SQLite fixture setup

- **Expected:** Authenticated reads preserve unrelated test-session setup.
- **Actual/evidence:** Uncommitted account count 1 → 0 after `/auth/me`; cash-flow expected opening 1500 became 0.00. Engine inspection borrows/closes the shared in-memory SQLite connection. MySQL data loss was not observed.
- **Files:** `backend/app/core/security.py:9`, `backend/tests/test_family.py:24`, `backend/tests/test_cash_flow.py:9`. Similar Engine readiness inspection exists in recovery/billing.
- **API:** All authenticated paths use the helper; reproduced via `/auth/me` and cash-flow dashboard.
- **Minimal recommended fix:** Inspect the active Session connection or cache readiness per correct engine, preserving transaction ownership; commit deliberately completed fixture setup before requests. Re-run the failed regression without weakening calculation assertions.

### P1-04 — Password change retains existing JWTs

- **Expected:** Password change supports revoking existing sessions, consistently with recovery reset.
- **Actual/evidence:** Password update 200 followed by old-JWT `/auth/me` 200. Configured lifetime is 360 minutes; old-password login rejection is separate.
- **Files:** `backend/app/routers/settings.py:33`, `backend/app/core/security.py:9`, `backend/app/core/deps.py`; recovery router provides the version-increment pattern.
- **API:** `PUT /settings/password`, `GET /auth/me`.
- **Minimal recommended fix:** Persist a session-version increment atomically with the password change, with reviewed schema present; require re-login or intentionally issue a replacement session. Test old-token rejection.

### P1-05 — Multiple independent migration heads

- **Expected:** Explicit, reproducible existing-schema migration path.
- **Actual/evidence:** Heads `20261104_accounts` and `20261117_access`; single-head resolution raises CommandError; DB revision beta only.
- **Files:** `backend/migrations/versions/20261104_accounts.py`, `20261113_reminders.py`, `20261117_access.py`, `backend/migrations/env.py` and deployment guidance.
- **API:** N/A; deployment/schema readiness affects modules.
- **Minimal recommended fix:** Review branch history and document a safe explicit target or reviewed merge revision. Do not rewrite applied history or run an unreviewed generic upgrade against existing financial records.

### P1-06 — Local sandbox test verification timed out

- **Expected:** Temporary sandbox grant/expiry/revoke tests complete with assertions/teardown.
- **Actual/evidence:** Broad run exited 124 at 180 seconds before completing local tests; separate attempt exited 124 at 90 seconds during expiry. One local CLI test passed. Root cause is unknown.
- **Files:** `backend/tests/test_local_family_access.py:182`, `backend/scripts/local_family_test.py`.
- **API:** Journey invokes auth/family/invitations/wallets/income; exact stalled call was not isolated.
- **Minimal recommended fix:** Add per-step/teardown diagnostics in fresh temporary fixtures and inspect thread/connection waits. Do not infer the separately confirmed in-memory rollback is the cause; do not touch the existing sandbox/MySQL to diagnose it.

### P2-01 — No default browser API timeout

- **Expected:** Stalled requests end with a useful retry state.
- **Actual/evidence:** Source fetch calls have no default deadline; caller cancellation is not an automatic timeout.
- **Files:** `frontend/src/api/client.js:5`, `frontend/src/services/authApi.js`, `frontend/src/pages/userdashboard/dashboard/AI.jsx`.
- **API:** Auth, finance and AI requests.
- **Minimal recommended fix:** Bounded caller-overridable deadlines with consistent timeout errors, caller cancellation and retained idempotency keys.

### P2-02 — Large frontend bundle

- **Expected:** Major dashboard/chart/admin features load in bounded chunks.
- **Actual/evidence:** Final main JS 850.97 kB, gzip 245.47 kB; Vite warns above 500 kB. Build succeeds.
- **Files:** `frontend/src/App.jsx`, dashboard/chart imports, `frontend/vite.config.js`.
- **API/route:** Initial application and dashboard/admin load.
- **Minimal recommended fix:** Measure and lazily split routes/heavy charts; do not merely raise the warning threshold.

### P2-03 — Exact-budget-limit status differs

- **Expected:** Consistent status at exactly 100 percent.
- **Actual/evidence:** Dashboard labels spent >= limit `over_limit`; budgets distinguishes equality as `limit_reached`. Source-confirmed label inconsistency, not wrong arithmetic.
- **Files:** `backend/app/routers/dashboard.py:274`, `backend/app/routers/budgets.py` (`as_output`).
- **API:** `/dashboard`, `/budgets`, `/budgets/alerts`.
- **Minimal recommended fix:** Share threshold/status logic; verify equality and excess boundaries.

### P2-04 — Transaction column nullability exceeds the response contract

- **Expected:** Stored category/description satisfy non-null response types.
- **Actual/evidence:** MySQL permits NULL; ORM/response types do not. Current active-NULL counts are zero, so no present serialization failure was established.
- **Files:** `backend/app/models/finance.py`, `backend/app/schemas/transaction.py`, accounts migration.
- **API:** Transaction read endpoints and consumers.
- **Minimal recommended fix:** Review legacy compatibility and reconcile schema/contract through normal reviewed migration work. No audit-time backfill/alter is warranted.

## 15. Exact next steps

1. Preserve the confirmed HTTP recovery and inspect the transient interruption in the implementation session. Repeat the configured direct-browser health check and verify stability, keeping the Family sandbox separate.
2. Fix the reproduced receipt boundary and SQLite session-inspection regression; verify exact amounts, one persisted transaction, safe replay and restored cash-flow regression.
3. Complete parallel Stripe/recovery configuration and migration targeting, including price-name reconciliation, webhook/SMTP readiness and all four access tables. This report is not migration authorization.
4. Establish and test consistent password-change session revocation.
5. Diagnose temporary sandbox timeouts; run the complete backend suite once source stabilizes. Preserve failed/timed-out results until superseded by actual evidence.
6. Use a separately authorized isolated MySQL test database for register/login/onboarding, receipt/transaction/transfer persistence, concurrent family/financial operations, expiry and webhook entitlements. Do not enable the live-DB rollback fixture against existing financial records as a substitute.
7. Run authenticated browser journeys only with isolated users/data: refresh persistence, receipt → Transactions → budgets/dashboard/reports, family privacy/removal, admin denial and timeout/provider failures.
8. Verify hosted Stripe sandbox Checkout/Portal, signed delivery/retries, plan changes, renewal/failure/cancel and persisted MySQL state. Production live billing is outside the current adapter's scope.
9. Reduce bundle size and align budget status, schema contracts and client deadlines; repeat build/lint after parallel changes settle.

The confirmed configured-MySQL connection and isolated test passes establish useful evidence. They do not certify complete MySQL user flows, live AI reliability, hosted payment readiness or continuous API availability.
