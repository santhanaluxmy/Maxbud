# MaxBud project audit

Audit date: 16 November 2026 (Asia/Colombo). Audit only: application source, configuration, migrations and financial records were not modified. The pre-existing working tree contains extensive modified/untracked implementation files; this audit evaluates that working tree, not only committed code.

## Requirements and evidence boundaries

The requested MaxBud PRD was not available in the supplied attachment or found in the repository (including searches for PRD, PDF and DOCX files). The attachment contains audit instructions, not the PRD. Therefore every PRD-match check is **BLOCKED**; no percentage of PRD completion or fully PRD-compliant module is claimed. Requirements here come from the supplied 30-module list and 15 financial rules, supplemented by README.md, MAXBUD_HANDOFF.md, DATABASE_AUDIT.md, FAMILY_MANAGEMENT.md, SUBSCRIPTION_IMPLEMENTATION.md, GROQ_AI_INTEGRATION.md, ADMIN_SECURITY.md, ADMIN_COMPLETION.md and DEPLOYMENT_GUIDE.md. Historical claims in these documents are not fresh test results. Some old handoff sections describe OpenAI or missing features now implemented with Groq; source and current execution take precedence.

Overall: **substantial implementation, PARTIAL and not release-certified**. Frontend lint/build/tests and 48 existing isolated backend cases pass. Read-only MySQL connection, application lifespan/health and schema inspection pass. The original browser suite fails on stale currency formatting; the supplemental run with two expectations adjusted in memory passes. Details are recorded in the test report. Targeted disposable-fixture probes expose financial retry and reconciliation defects. Browser smoke checks do not establish every CRUD workflow. No real payment processor, password recovery workflow, dedicated AI goal planner or predictive spending service was found.

Statuses follow the requested vocabulary: COMPLETE requires verified end-to-end behavior in the stated environment; PARTIAL indicates implemented but incomplete/unverified dimensions; FRONTEND ONLY/BACKEND ONLY identify implementation location; BROKEN requires execution failure; MISSING means no implementation found; BLOCKED means an unavailable verification dependency; NOT TESTED means found but not executed. No whole module receives COMPLETE in this audit.

## Project structure and technology

- `frontend/`: React 19 JSX, React Router 7, Vite 8, CSS, Tailwind Vite plugin, Lucide, Recharts and optional Google OAuth. `src/main.jsx` mounts StrictMode, BrowserRouter and optional GoogleOAuthProvider; `src/App.jsx` defines public/protected/admin routes. `src_backup_overview_20261106_141456/` is an inactive backup, excluded by lint; it is not a second production application.
- `frontend/src/api/`: authenticated JSON API client, auth facade and legacy-named finance facade (actually auth helpers). `src/services/authApi.js` owns browser session persistence. State is component-local React hooks; no external store is used. Layout/navigation, common modal/loading/empty cards, onboarding and dashboard feature pages reuse the existing visual identity.
- `backend/app/`: FastAPI app with lifespan DB probe, CORS and per-worker request limiter; SQLAlchemy 2 synchronous MySQL/PyMySQL sessions; Pydantic 2 input schemas; JWT HS256 and Argon2 password hashing. Routers delegate substantial account, goal, household, subscription, cash-flow and Groq work to services. Money uses Decimal/Numeric in financial server logic; float is used for percentages and frontend display/charts.
- `backend/migrations/`: Alembic files against an existing schema, not a full clean-install baseline. Two independent roots/heads exist: `20261104_accounts` and `20261115_beta` (the `maxbud_features` branch). Never infer that applying both is safe. No migration was applied in this audit.
- `backend/tests/`, `frontend/tests/`: isolated API contracts, finance/household/admin tests, Node auth/advisor tests, optional browser and live-provider scripts. The race harness and opt-in MySQL write tests were not run against genuine data.
- Root documents contain architecture/deployment history. No container/CI deployment automation was found in the inspected project files. Existing deployment guide supplies operator steps; actual public deployment remains NOT TESTED.

Installed Python dependencies pass `pip check`; existing Node dependencies were reused without installation. Build used `/tmp/maxbud-audit-build` to preserve the existing distribution. Configuration inspection returned only booleans: development environment, rate limiting enabled, demo disabled, optional Google/Groq configuration present, MySQL TLS CA absent. Presence of credentials/models is not proof the external integration works. No secrets are included here.

## Module and integration assessment

See MAXBUD_FEATURE_CHECKLIST.md for all 30 modules and important subfeatures. Landing/auth/onboarding/dashboard/accounts/transactions/transfers/budgets/goals/reminders/reports/AI/household/subscription/admin/notifications/settings have both source and API integrations. Five onboarding steps persist server-side, account balances derive from the ledger, transfers have paired entries, and personal versus explicit household scope is enforced in key queries. Reports are delivered by `GET /dashboard?...&include_cash_flow=true`, not a missing standalone `/reports` API. Shared finance uses `/family/*` alongside legacy family membership routes. Admin authenticates through the existing login with backend role checks; a separate admin password system is not required by available specifications.

Missing/limited behavior: forgotten-password recovery and delivery; dedicated goal planning/prediction APIs; real payment gateway/webhooks (demo subscriptions are explicitly supported); amortizing loan principal/interest schedules (generic loan reminders exist); outbound email/SMS notifications; merchant-rule management UI/API (automatic learning/application exists); automated clean-install and production deployment verification. These are distinctions, not invented PRD obligations.

## Prioritized findings

| ID | Priority | Finding and evidence | Consequence / next action |
|---|---|---|---|
| FIN-01 | P0 | `/goals/{id}/contribute` personal branch ignores accepted `request_id`; identical LKR 10 request twice returned 10 then 20 saved. Dashboard contribution form sends no request key. | Retry inflates allocation. Persist personal contribution idempotency, fingerprint payload, enforce uniqueness and reuse stable client keys. |
| FIN-02 | P0 | `/transactions/{id}` permits soft-deleting a reminder payment. Probe: pay 10, delete expense, retry payment => `already_paid=true`, balance restored to 100. `editable()` only protects transfer-linked entries. Receipt-linked expenses use the same generic mutation path (source risk, not separately executed). | Payment state and ledger diverge. Define protected linked-entry edits/deletes or explicit atomic reversal. Preserve payment/receipt audit history. |
| FIN-03 | P0 | Create income 100, spend 80, delete income => HTTP 200 and account balance -80. Update only validates a requested expense; deleting income/moving it or lowering opening balances lacks resulting-balance policy enforcement. | Negative balance can bypass the insufficient-funds rule enforced on new expenses/transfers. Define permitted correction behavior and apply consistently under account locks; arithmetic itself correctly reflects deletion. |
| DB-01 | P0 | Live `users.full_name` is VARCHAR(100), ORM/register/profile accept 150; `income_sources.name` is VARCHAR(100), ORM/onboarding accept 120. | Validated inputs can exceed real columns. Align contracts conservatively or approve additive widening migration; reproduce on disposable MySQL, never genuine records. |
| AUTH-01 | P0 | Old bearer JWT still accesses `/auth/me` after password update (200). No session version/revocation field checked by `current_user`. | A stolen token remains usable through its expiry after a password change. Add a revocation/version policy and tests; no exploit against another user was attempted. |
| DB-02 | P1 | Live users.email VARCHAR(254) versus ORM 255; income amount DECIMAL(14,2) versus ORM Numeric(12,2); transactions category/description nullable in DB versus non-null ORM; generated budgets.family_scope reported nullable. | Review backward compatibility. Nullable old transaction rows may fail output validation; no private rows were read to assert occurrence. Generated COALESCE scope stays non-null by expression. Numeric/DECIMAL and Boolean/TINYINT aliases are not failures. |
| CON-01 | P0 verification gate | SQLite suite cannot verify InnoDB locks/deadlocks. User-row, account-row, reminder/family-row lock sequences differ; AI holds user locks during a provider call up to 45s. | Test concurrent financial writes on a separately provisioned disposable MySQL DB. Deadlock/race risk is source-based, not a demonstrated production race. |
| AUTH-02 | P1 | Forgotten-password form/API/token storage/delivery absent; change-password is implemented. | Users cannot recover a forgotten password. Implement only after approving recovery/delivery requirements. |
| AI-01 | P2 | Real Groq and Google OAuth not called in this run; mocked contracts pass. AI configuration present but availability/quality/cost/privacy approval not verified. | Run consented external integration cases using synthetic data and bounded spending. No external API credits were intentionally consumed by this audit. |
| UI-01 | P3 | Common Modal has dialog semantics but no focus trap, initial focus, Escape handler or focus return. | Keyboard accessibility gap, source verified; validate interactively before changing styling. |
| UI-02 | P3 | Dashboard.jsx contains old unreachable/redundant placeholder panels claiming reminders absent/personal-only family; current routes use dedicated implementations. Landing marketing references planned prediction/goal planning. Vescura declared but no supplied font asset/@font-face found. | Consolidate reachable text and label planned features accurately; preserve branding. Do not report unreachable placeholder text as a tested broken route. |
| PERF-01 | P3 | Production JS bundle 828.75 kB (240.39 kB gzip), major images ~625 kB–1.07 MB. | Consider route splitting and image optimization after correctness work; no network performance score claimed. |

## Database: source, migration and live table distinction

Fresh read-only inspection found **36 real tables**, including **all 26 ORM-mapped tables with no missing mapped columns**. `alembic_version` contains `20261115_beta`. SQLAlchemy inspector retrieved foreign keys, indexes and unique constraints; ORM unique-constraint comparison is recorded in the test report. This verifies structural presence only, not correctness of genuine financial rows. No user records, passwords, financial values, or provider keys were dumped. Connection failed with sandbox MySQL 2003 initially and succeeded in an approved read-only retry.

The remaining ten live tables are legacy/history concepts plus Alembic state: account_legacy_map, account_transfers, authentication_identities, financial_accounts, monthly_budgets, onboarding_profiles, savings_goals, transaction_audit_logs, user_profiles, alembic_version. Their existence does not mean the active code uses them. Keep legacy foreign keys/history until a separate reconciliation plan is approved. Core finance uses accounts, transactions, budgets, goals and account_transfer_records. Current shared contributions use goal_contributions.current_goal_id while legacy goal_id continues to represent savings_goals.

SQLite `create_all()` generates current metadata without live length differences and with different locking/constraint behavior; passing SQLite tests therefore cannot resolve DB-01 or CON-01. Fresh-schema bootstrap is not established by migrations that expect pre-existing users/accounts/categories. MySQL DDL is a separately reviewed deployment action.

## Financial rules: validation matrix

| Requested rule | Evidence / remaining check |
|---|---|
| Income credits correct account | Account balance computes opening + income/transfer-in − expense/transfer-out; isolated contracts and targeted probe confirm. Test account moves and cross-user IDs exhaustively. |
| Expense debits correct account | Existing tests check account balances/insufficient funds and isolation. Account lock plus current-entry reads used. |
| Transfers are paired and excluded from income/expense | Header + two entries commit together; distinct accounts, currencies, balance and replay validation present; existing tests pass. Concurrent duplicate requests not tested on MySQL. |
| Edit recalculates correctly | Derived balances avoid cached double updates; source risk: income edits/account moves lack final-balance guard. Add move/edit differential tests. |
| Delete/reverse consistency | Soft deletion affects sums; FIN-02 and FIN-03 reproduced. Formal reversal workflows missing. |
| Duplicate updates | Transactions support optional Idempotency-Key; transfers optional client_request_id; household keys mandatory; personal goal retry broken. Different/missing keys still represent distinct writes. |
| Monthly budget eligible spending | Date-bounded expense/non-deleted/non-transfer/personal-scope queries; shared report scopes expenses separately; existing tests pass. Add deleted/edited category/month boundaries. |
| Savings not deducted twice | Contributions are allocations, not account debits/expenses; cash-flow test confirms no money movement. Safe-to-spend subtracts allocations; duplicate personal allocations remain a bug. |
| Reminder pay at most once | Unique occurrence + locks and replay tests pass for normal payment; deleting linked expense breaks consistency. Month-end recurrence tested. |
| Dashboard/report matching totals | Existing cash-flow test deliberately expects dashboard personal expenses 50 and account report expenses 170 when 120 was paid personally for household. Bases differ intentionally; require clear labels/reconciliation, not forced equal totals across scopes. |
| Family no double count | Explicit family_id, paired transfers and settlement logic avoid income/expense duplication; SQLite cases pass. Concurrent and full real MySQL E2E NOT TESTED. |
| Shared goal attribution | GoalContribution records user and request; details include active/former members and history. Isolation/removal/replay cases pass. |
| Receipt confirms once | Row lock and transaction_id replay plus mocked tests pass; deleting linked transaction/review replay payload remains a follow-up. |
| Decimal money | Decimal input/Numeric persistence and exact split rounding. Frontend Number used for charts/display; test high-value form calculations. Float percentages are not ledger mutation. |
| Atomic multi-record writes | Transfer, receipt/payment, splits and settlement stage records before commit. Exceptions close/rollback sessions; concurrency/crash injection still needed. |

## Authentication, authorization and privacy

Argon2 hashing and optional legacy bcrypt verification are present. JWT has fixed HS256 verification and required subject/expiry; database current-user active check and admin-role dependencies protect operations. Password/confirmation/email rules are server enforced; public role input cannot create admins. User-scoped queries and household view/add permissions have passing isolated denial tests. Backend plan checks protect writable financial actions and AI usage, with expired read-only history/export retained. Demo activation is gated server-side and rejected in production; simulated revenue is labeled.

Receipt processing caps uploads at 5 MB, validates JPEG/PNG decoding, rejects decompression bombs, strips metadata by re-encoding, uses generated private filenames/permissions, and requires user confirmation. Keys stay server-side. Receipt retention/cleanup/backup recovery and third-party financial-data consent remain deployment/privacy review items. No unrelated financial data appears in admin endpoint projections; metadata/counts are exposed, not transaction contents.

CORS uses configured origins and bearer authorization; rate limits are per process/IP, not distributed, so reverse proxy and multi-worker enforcement need deployment verification. Browser bearer storage is JavaScript-readable (sessionStorage or optional localStorage); prevent XSS and review session design. JWT logout is local only and password change does not revoke existing tokens. Development configuration is not a production deployment: production validation demands HTTPS origin, MySQL CA, rate limiting and demo off. No credential rotation was performed or assumed needed.

## UI/UX review

Aqua #B1E5E6, cream #EEEAD7 and pink #F7ADAD are defined centrally. Existing glass cards, sidebar/mobile drawer, auth layouts, responsive media queries, reduced-motion rules, loading/error/empty components and advisor text rendering are present. Forms usually use labels/native constraints plus backend validation. Preserve these designs. Browser observations and precise completed viewport checks are in MAXBUD_TEST_REPORT.md; do not extrapolate them to all interactions or accessibility compliance. Visual-only findings (font availability, bundle/image weight, modal keyboard polish) are distinct from ledger/API defects.

## Next checkpoint

Use MAXBUD_COMPLETION_ROADMAP.md for dependency-ordered small phases and the exact first task. Implementation is **not authorized yet**. Wait for the explicit instruction `START IMPLEMENTATION`.

## Inspected source inventory

Active frontend source (backup excluded):

- `frontend/src/App.css`
- `frontend/src/App.jsx`
- `frontend/src/api/auth.js`
- `frontend/src/api/client.js`
- `frontend/src/api/finance.js`
- `frontend/src/components/AuthLayout.jsx`
- `frontend/src/components/Navbar.jsx`
- `frontend/src/components/auth/GoogleAuthButton.jsx`
- `frontend/src/components/common/EmptyState.jsx`
- `frontend/src/components/common/GlassCard.jsx`
- `frontend/src/components/common/Loading.jsx`
- `frontend/src/components/common/Modal.jsx`
- `frontend/src/config/subscription.js`
- `frontend/src/index.css`
- `frontend/src/main.jsx`
- `frontend/src/pages/landingpage/LandingPage.css`
- `frontend/src/pages/landingpage/LandingPage.jsx`
- `frontend/src/pages/login/LoginPage.css`
- `frontend/src/pages/login/LoginPage.jsx`
- `frontend/src/pages/onboarding/Onboarding.css`
- `frontend/src/pages/onboarding/Onboarding.jsx`
- `frontend/src/pages/register/RegisterPage.css`
- `frontend/src/pages/register/RegisterPage.jsx`
- `frontend/src/pages/userdashboard/dashboard/AI.jsx`
- `frontend/src/pages/userdashboard/dashboard/Admin.jsx`
- `frontend/src/pages/userdashboard/dashboard/AdvisorMessage.jsx`
- `frontend/src/pages/userdashboard/dashboard/CashFlow.jsx`
- `frontend/src/pages/userdashboard/dashboard/Dashboard.css`
- `frontend/src/pages/userdashboard/dashboard/Dashboard.jsx`
- `frontend/src/pages/userdashboard/dashboard/DashboardOverview.css`
- `frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx`
- `frontend/src/pages/userdashboard/dashboard/Notifications.jsx`
- `frontend/src/pages/userdashboard/dashboard/Reminders.jsx`
- `frontend/src/pages/userdashboard/dashboard/Settings.jsx`
- `frontend/src/pages/userdashboard/dashboard/Upgrade.jsx`
- `frontend/src/pages/userdashboard/dashboard/advisorText.js`
- `frontend/src/pages/userdashboard/family/FamilyPage.css`
- `frontend/src/pages/userdashboard/family/FamilyPage.jsx`
- `frontend/src/pages/userdashboard/family/HouseholdFinance.jsx`
- `frontend/src/pages/userdashboard/layout/DashboardLayout.css`
- `frontend/src/pages/userdashboard/layout/DashboardLayout.jsx`
- `frontend/src/pages/userdashboard/layout/DashboardPremium.css`
- `frontend/src/pages/userdashboard/layout/navigation.js`
- `frontend/src/pages/userdashboard/transaction/Transaction.css`
- `frontend/src/pages/userdashboard/transaction/Transaction.jsx`
- `frontend/src/services/authApi.js`
- `frontend/src/styles/animations.css`
- `frontend/src/styles/auth.css`
- `frontend/src/styles/controls.css`
- `frontend/src/styles/variables.css`

Backend application source:

- `backend/app/core/config.py`
- `backend/app/core/deps.py`
- `backend/app/core/plans.py`
- `backend/app/core/rate_limit.py`
- `backend/app/core/security.py`
- `backend/app/database.py`
- `backend/app/main.py`
- `backend/app/models/ai.py`
- `backend/app/models/family.py`
- `backend/app/models/finance.py`
- `backend/app/models/notification.py`
- `backend/app/models/platform.py`
- `backend/app/models/reminder.py`
- `backend/app/models/request.py`
- `backend/app/models/user.py`
- `backend/app/routers/account.py`
- `backend/app/routers/admin.py`
- `backend/app/routers/ai.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/budgets.py`
- `backend/app/routers/dashboard.py`
- `backend/app/routers/family.py`
- `backend/app/routers/goals.py`
- `backend/app/routers/household.py`
- `backend/app/routers/notifications.py`
- `backend/app/routers/onboarding.py`
- `backend/app/routers/reminders.py`
- `backend/app/routers/settings.py`
- `backend/app/routers/subscriptions.py`
- `backend/app/routers/transaction.py`
- `backend/app/schemas/account.py`
- `backend/app/schemas/auth.py`
- `backend/app/schemas/budget.py`
- `backend/app/schemas/family.py`
- `backend/app/schemas/onboarding.py`
- `backend/app/schemas/transaction.py`
- `backend/app/services/account.py`
- `backend/app/services/ai.py`
- `backend/app/services/cash_flow.py`
- `backend/app/services/family.py`
- `backend/app/services/goals.py`
- `backend/app/services/household.py`
- `backend/app/services/subscriptions.py`

Migration definitions:

- `backend/migrations/versions/20261104_accounts.py`
- `backend/migrations/versions/20261113_ai.py`
- `backend/migrations/versions/20261113_notifications.py`
- `backend/migrations/versions/20261113_reminders.py`
- `backend/migrations/versions/20261113_requests.py`
- `backend/migrations/versions/20261113_shared_goals.py`
- `backend/migrations/versions/20261115_beta.py`
