# Latest handoff — November 15, 2026

The current implementation follows the final beta request. Historical November13 notes below are preserved, but pooled-private-family reporting, automatic household creation for new users, old two-plan marketing and the previous unavailable OpenAI provider assumptions are superseded.

New code uses persisted three-calendar-month trials, configurable demo-only Individual/Family plans, explicit private/shared ledgers, secure invitations and actual Groq. The existing layout/branding and finance/goal/reminder flows remain.

Local MySQL is at `20261115_beta`, 36 tables. Before/after migration checks verified all116 pre-existing rows across30 data tables unchanged. Both supplied backups and backend/frontend environment files were preserved. Never use `upgrade heads`; target `maxbud_features@head` only. No commit, push, production deployment, real charge or actual admin elevation was performed.

Final checks:81 SQLite pytest cases,41 distinct MySQL integration cases, targeted final scanner regressions on both engines, production build/lint/frontend tests and all three browser harnesses passed. Real Groq API/MySQL and frontend upload/advisor flows passed. Read [TEST_REPORT.md](TEST_REPORT.md) for final evidence and per-module classifications. The suite distinguishes mocked provider tests, real Groq calls, temporary browser fixtures and rolled-back MySQL integration. Automated synthetic accounts are not ten real beta participants.

Operator gates: configure optional demo prices/flag, HTTPS origin/API, verified MySQL TLS, durable private receipt storage, monitoring/backup restore, real Google OAuth origin checks if used, and recruit ten consenting testers using [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md). Isolated multi-connection MySQL concurrency verification remains blocked by error1044 permissions; no grant change or database-drop test was run.

Important source groups: backend `services/{subscriptions,household,goals,ai}.py`, `routers/{subscriptions,household,ai,admin}.py`, compatible scope filters in finance/auth/onboarding/settings, models/platform and beta migration; frontend existing Subscription/Family/AI/Admin/Overview/Settings pages and landing pricing integration. Existing untracked source/test assets are intentionally retained.

Viva decisions: distinguish billing owner/membership/effective entitlement; explicit family scope prevents salary pooling; transfers and reimbursements are not income/expenses; Decimal splits preserve cents; idempotency protects financial replays; nullable OCR totals require reviewed confirmation; no AI write tools; admin observes platform metadata without unrestricted private finance access. See the linked implementation documents for endpoints and details.

Recommended commit after reviewing all existing changes: `feat: complete MaxBud beta household finance, demo subscriptions and Groq AI`.

---

# MaxBud implementation and deployment handoff

Date: 13 November 2026 (Asia/Colombo).

This report records the original core integration. Later UI and family work is documented in [UI_PHASE1.md](UI_PHASE1.md) and the Phase 2 section of [FAMILY_MANAGEMENT.md](FAMILY_MANAGEMENT.md); those sections supersede earlier counts and family-goal limitations.

## Completed implementation

- Existing password authentication, Remember Me, JWT verification, account status checks and family authorization preserved. Google button now uses the same `VITE_API_URL` as password login; legacy `VITE_BACKEND_URL` remains a fallback. Expired browser sessions are cleared and API 401 responses return to login.
- Existing five-step onboarding retained, with locked step transitions, plan limits for initial goals and automatic completion for fully funded goals.
- Existing account, transaction and budget APIs retained. Account edit/archive/restore controls connected, transaction search added, and transaction creation supports persistent `Idempotency-Key` headers. The UI keeps a submission key across retries. Archive preserves all ledger history.
- Goals now support creation, editing, contribution, automatic completion, archive/restore and backend plan limits. These are allocations, not account transfers.
- Reminders support rent/utilities/loans/subscriptions/custom categories, edit/archive, overdue/upcoming states, one-time and weekly/monthly/yearly recurrence. Mark Paid creates an expense exactly once per due date. Recurring month-end dates retain their original day. A new bill's due date is part of the payment request, preventing a retry from accidentally paying the next occurrence. There is no pre-existing loan-principal model; amortization and loan remaining-principal tracking are not implemented.
- Safe-to-spend uses recorded balance less goal allocations and remaining commitments. Bills reserve only the amount beyond their category's remaining budget, avoiding double-counting. Expected income is displayed separately and is not spendable before recording. Unrecorded obligations cannot be included. Reports now accept a selected year/month; balances remain current tracked balances.
- In-app upcoming/overdue bill, budget warning/overspending and goal-completion alerts, with user-isolated persistent read state and a notification bell destination.
- OpenAI receipt adapter: authenticated JPG/PNG uploads up to 5 MB, decoded-image validation, pixel-bomb checks, EXIF removal, resize, private UUID filenames, structured output validation, editable review, currency/account checks, duplicate confirmation protection and per-user merchant-category memory. Extraction never creates a transaction before confirmation. Successful extractions consume one scan, even if the user subsequently declines to confirm. Duplicate normalized images reuse their extraction.
- Advisor adapter: personal aggregate summary only, bounded question/response sizes, saved history, request idempotency, timeouts and successful-message usage accounting. Transaction descriptions, names, account IDs, credentials and tokens are not sent as financial context. User questions and receipt images themselves may contain personal data; the UI explains their transmission. Provider storage is disabled in the request.
- Central Free/Premium limits match the request. AI usage meters, upgrade information and effective subscription checks are present. Live checkout is disabled; no paid subscription is activated by the UI.
- Platform-admin APIs require `role == 'admin'`, separately from family membership/ownership. Overview, bounded user/subscription lists, AI counts and enable/disable APIs are present. Administrator accounts cannot disable themselves or other admins through this endpoint. No real account was granted admin or changed for testing.
- Profile and password-edit forms connected. Password changes require the existing password. There was no supported password-reset service to complete.
- Production mode enforces an HTTPS frontend origin, verified MySQL TLS and rate limiting. Production CORS omits localhost; SQL parameters are hidden in errors. Password hashing and JWT checks are retained. Per-process request limits and security headers were added.

## Schema and data safety

The existing database's `alembic_version` table was empty. The older accounts migration performs legacy data mapping, so it was deliberately **not run or stamped**.

The additive feature migrations form the independent `maxbud_features` branch:

1. `20261113_reminders`: reminder/payment tables.
2. `20261113_ai`: nullable fields on existing `ai_scans`, advisor history and merchant rules; existing `ai_usage` reused.
3. `20261113_notifications`: notification read-state table.
4. `20261113_requests`: transaction submission keys and nullable recurrence anchor day.

Reviewed and applied locally with:

```bash
cd backend
.venv/bin/alembic upgrade maxbud_features@head
```

Do not use an unqualified `alembic upgrade heads`: it also selects the unrelated legacy accounts branch. Review the target schema and take a verified backup before any legacy migration/backfill. New schema migrations do not delete, reset or backfill data; destructive downgrades are disabled. MySQL tests use new accounts under outer transactions and roll back test financial records. Receipt files used by automated API tests are in temporary directories.

## External services requiring action

### Google sign-in

The configured frontend/backend Google client IDs are present and match. This does not establish that Google has authorized the frontend origin. No Google Console access was available to inspect or alter the OAuth client.

In **Google Cloud Console → Google Auth Platform → Clients**, select the matching **Web application** OAuth client. Under **Authorized JavaScript origins**, add each frontend origin you actually use:

- `http://localhost`
- `http://localhost:5173`
- `http://127.0.0.1:5173` if opening the frontend by that address
- The final HTTPS frontend origin after deployment (no path).

If Vite uses another port, add that exact origin too. Confirm `VITE_GOOGLE_CLIENT_ID` and backend `GOOGLE_CLIENT_ID` identify this same Web client, then restart Vite/rebuild. Review consent-screen audience/test users and publishing status for the intended Google accounts. This application uses a JavaScript credential callback, so `/auth/google` is a token-verification API, not a Google redirect URI.

A live Google sign-in must still be verified in your browser after the Console change. Google documents the required origin configuration at https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid.

### AI provider

No backend OpenAI API key or model is configured. Set backend-only `OPENAI_API_KEY` and `OPENAI_MODEL` to an authorized API project key and an available model supporting images and structured outputs. Enable billing/spending controls in that provider account only with your approval. Restart FastAPI. Then test a real receipt and a real advisor question. Do not put the API key in any `VITE_*` variable.

The implementation follows the official Responses API contract: https://developers.openai.com/api/reference/resources/responses/methods/create. Tests replace provider responses and failures; they do not establish live provider availability or extraction accuracy.

### Email and SMS

No SMTP/Twilio/SMS/mail provider settings were found; delivery is not implemented or claimed. Current alerts are in-app. A future SMTP adapter requires `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS`, a verified sender/domain and authorized sending. An SMS adapter requires provider selection, approved sender, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` (if using Twilio), verified destinations as required, and user consent. Supplying variables alone will not enable delivery; an adapter and delivery/error tests are still required.

### Live payments

No approved payment-gateway integration exists. The upgrade page explicitly has no live checkout. Before live subscriptions: approve a gateway supporting the intended LKR recurring-payment model; obtain merchant/KYC approval, settlement account and live recurring-payment permission; implement backend checkout, signed webhook verification, idempotent event handling, renewal/cancellation/expiration and reconciliation; supply its live merchant credentials and webhook secret only on the backend. No payment success or revenue has been simulated. LKR 990/month is displayed as the requested assumption.

### Admin access

Select and explicitly authorize the real platform-admin account before provisioning it. This changes an existing user's platform role and was not performed. API tests grant admin only to temporary test accounts. Family owners do not automatically receive this permission.

## Production deployment status

**Not deployed or production-certified.** Local production build passes; current local runtime is development mode and its MySQL connection has no configured TLS CA. No cloud services were purchased or activated.

Provision hosting and a reachable managed MySQL instance, authorize account access, migrate existing data using a verified backup/restore procedure, and configure:

- Backend: `ENVIRONMENT=production`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL_CA`, a random `JWT_SECRET` (at least 32 characters), `JWT_MINUTES`, `FRONTEND_ORIGIN=https://<frontend>`, `GOOGLE_CLIENT_ID`, `RATE_LIMIT_ENABLED=true`, optional authorized AI settings above, and `RECEIPT_STORAGE_DIR` pointing to a private persistent writable volume outside the web root.
- Frontend build: `VITE_API_URL=https://<api>` and `VITE_GOOGLE_CLIENT_ID`. Rebuild with `npm ci && npm run build`; use SPA fallback to `index.html`. The local build still inherits local API settings; set production values before building deployment assets.
- Backend install/run: `pip install -r requirements.txt`, apply only reviewed migrations, then `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` behind a trusted HTTPS reverse proxy. Configure trusted proxy forwarding explicitly. Do not expose MySQL publicly; use network allowlisting/private networking and separate restricted runtime/migration database roles.
- Rate limits are in-memory per worker and keyed to the direct client address. Configure shared/edge limits before scaling horizontally and forward trusted client addresses correctly. They are not a distributed abuse-prevention system.
- Use managed daily encrypted snapshots plus point-in-time recovery if available; establish retention and test restoration into a separate database before relying on backups. Back up private receipt storage with the database and define retention/deletion policy. Never store receipts under frontend public assets.
- Verify HTTPS, CORS, OAuth, API health, secrets injection, persistent uploads, logs, provider spending caps, restore capability and the full user journey on the actual public deployment.

## Verification results

See the final verification section below for the latest recorded commands/results. Earlier tests intentionally used SQLite or transactional MySQL; no live provider/payment delivery was claimed. A Vite warning remains for the large existing main bundle; it does not fail the build.

## Final verification

| Check | Actual result |
|---|---|
| Backend SQLite API suite | 22 passed (`.venv/bin/python -m unittest discover -s tests -v`) |
| MySQL API/integration suite | 22 passed (`FAMILY_TEST_MYSQL=1 .venv/bin/python -m unittest discover -s tests -v`), outer transactions rolled back |
| Frontend authentication tests | 5 passed (`npm test`, outside the sandbox; the sandbox reports only the file wrapper) |
| Python compile/import checks | Passed (`python -m compileall -q backend/app backend/migrations backend/tests`) |
| Frontend production build | Passed (`npm run build` in `frontend`); main-bundle size warning remains |
| Git whitespace checks | Passed (`git diff --check`) |
| Desktop/mobile browser flow | Passed (`.venv/bin/python tests/family_browser.py`), isolated SQLite API and local Vite server |
| Google OAuth | Verifier/verified-email tests passed with a mocked Google verifier; real browser OAuth blocked by Console setup |
| Receipt extraction | Upload validation, review, confirmation and usage tests passed with mocked AI output; live extraction blocked by missing provider configuration |
| Advisor | History, isolation, successful usage, failure accounting and quotas passed with mocked AI output; live response blocked by missing provider configuration |
| Payment delivery | Not tested or claimed; no payment gateway implemented/activated |
| Email/SMS | Not tested or claimed; in-app notifications only |
| Public cloud/HTTPS/MySQL TLS | Not deployed or verified |

The browser run initially timed out on a member save with the default five-second assertion wait; it passed with the longer wait. The expanded browser run then exposed an ambiguous reminder account-select label; an explicit accessible label fixed it and the full run passed. Initial local test invocations from the repository root failed on module/package paths; corrected commands were run in their project directories. Pytest is not installed; the backend suite uses unittest directly. The Starlette TestClient emits an httpx deprecation warning, but tests pass. No failed live provider, payment or cloud test has been relabeled as passing.

### Requested user flows

| Flow | Verified coverage and limitation |
|---|---|
| A: new user | Registration/login, required onboarding sequence, saved income/accounts/budgets/goals, completed status and login persistence verified through APIs; account persistence and finance forms also verified in browser. Full landing-to-logout click sequence has not been automated. |
| B: family | Owner/member login, limits, add/remove, aggregation, cross-family isolation and privacy verified in APIs/MySQL and desktop/mobile browser. |
| C: reminders | Create/edit/archive APIs, upcoming/overdue listing, payment-to-transaction and balance update, recurrence and duplicate payment protections implemented; payment, next due date, account balance and read-state checks pass in API tests, creation/payment/navigation pass in browser. Not every edit/delete UI button has a separate browser assertion. |
| D: receipts | Validated upload → mocked extraction → editable data → confirmation → one transaction → usage verified by API tests. Live provider response and full receipt-review browser submission remain unverified. |
| E: advisor | Mocked response, saved personal history, isolation, failure accounting and quotas verified by APIs; chat page renders in browser. Live provider response remains unverified. |
| F: premium | Free AI limit, authorized temporary Premium subscription permissions, family limits and expiration verified by API tests. Upgrade page is informative; no live checkout. |
| G: admin | Temporary admin access, owner denial, user listing/statistics and normal-user denial verified in APIs. Password-change and enable/disable behavior verified in SQLite tests. No real admin was provisioned; the full admin browser flow is not automated. |

### Remaining limitations and blockers

- Google Console origin/client consent configuration and a real sign-in are required.
- An approved AI project/key/model is required, followed by live receipt/advisor validation. No live AI request was made.
- Approved merchant/gateway choice, recurring-payment authorization and a signed-webhook billing implementation are required for live payments. The current upgrade page cannot charge or activate a plan.
- A specifically authorized real platform administrator must be provisioned before using the admin UI with real data.
- Public hosting, production URLs/TLS, secure managed MySQL connectivity, persistent private receipt storage and backup/restore validation remain deployment work.
- Email/SMS adapters and delivery validation are absent; alerts are in-app. Loan principal/amortization tracking is absent because it was not supported by the existing schema.
- Browser tests cover important integrated paths, not every possible button, validation state or device. Do not treat the result as exhaustive production certification.
- Local `.env` files were neither edited nor exposed. No legacy family backfill, destructive database operation, service purchase, commit or push was performed.
- The legacy `/transactions` URL now redirects to the authenticated dashboard transaction page, removing the separate unprotected route entry while preserving the component source.

## Changed files

- `backend/.gitignore`
- `backend/app/core/config.py`
- `backend/app/core/plans.py`
- `backend/app/database.py`
- `backend/app/main.py`
- `backend/app/routers/dashboard.py`
- `backend/app/routers/onboarding.py`
- `backend/app/routers/transaction.py`
- `backend/app/schemas/auth.py`
- `backend/migrations/env.py`
- `backend/requirements.txt`
- `backend/tests/family_browser.py`
- `backend/tests/test_family.py`
- `frontend/src/App.jsx`
- `frontend/src/api/auth.js`
- `frontend/src/api/client.js`
- `frontend/src/components/auth/GoogleAuthButton.jsx`
- `frontend/src/pages/userdashboard/dashboard/Dashboard.jsx`
- `frontend/src/pages/userdashboard/layout/DashboardLayout.css`
- `frontend/src/pages/userdashboard/layout/DashboardLayout.jsx`
- `frontend/src/pages/userdashboard/layout/navigation.js`
- `frontend/src/services/authApi.js`
- `frontend/tests/auth.test.mjs`
- `MAXBUD_HANDOFF.md`
- `backend/app/core/rate_limit.py`
- `backend/app/models/ai.py`
- `backend/app/models/notification.py`
- `backend/app/models/reminder.py`
- `backend/app/models/request.py`
- `backend/app/routers/admin.py`
- `backend/app/routers/ai.py`
- `backend/app/routers/goals.py`
- `backend/app/routers/notifications.py`
- `backend/app/routers/reminders.py`
- `backend/app/routers/settings.py`
- `backend/app/services/ai.py`
- `backend/migrations/versions/20261113_ai.py`
- `backend/migrations/versions/20261113_notifications.py`
- `backend/migrations/versions/20261113_reminders.py`
- `backend/migrations/versions/20261113_requests.py`
- `backend/tests/test_features.py`
- `frontend/src/pages/userdashboard/dashboard/AI.jsx`
- `frontend/src/pages/userdashboard/dashboard/Admin.jsx`
- `frontend/src/pages/userdashboard/dashboard/Notifications.jsx`
- `frontend/src/pages/userdashboard/dashboard/Reminders.jsx`
- `frontend/src/pages/userdashboard/dashboard/Settings.jsx`
- `frontend/src/pages/userdashboard/dashboard/Upgrade.jsx`

## UI polish handoff — 16 November 2026

Targeted visual and read-only cash-flow/advisor improvements are preserved; see [UI_POLISH.md](UI_POLISH.md). Backend93 SQLite pytest cases,3 frontend test files (including React advisor output), targeted lint and build pass. No migration or live MySQL data write; `.env` and supplied backups unchanged. Hero untouched. The latest responsive browser runs did not complete (startup timeout / interrupted reruns), so new visual changes are not browser-verified. Existing business modules passed automated regressions; fresh live Groq/demo browser checks remain incomplete. Zero active real platform admins were found by read-only count; developer must explicitly bootstrap an existing operator account as documented. No credentials were created/reset, no commit/push/deployment performed.

## Card contrast and admin handoff — 16 November 2026

Cards3/6 use #F6E7B5 with continuous backgrounds; surrounding cream and hero preserved. Existing admin modules now include request-specific loading/error/empty states, filtering/pagination, monthly/yearly billing metadata/statistics and proper admin login redirection/session handling. Secure CLI can create a new admin with hidden password confirmation or verify the current password before promoting an existing active account; it never resets hashes or exposes public signup. See [ADMIN_COMPLETION.md](ADMIN_COMPLETION.md) / [ADMIN_SECURITY.md](ADMIN_SECURITY.md) for exact commands.

Evidence:108 backend pytest cases,5 targeted admin scenarios,3 frontend test files, lint/build and Chrome at360/768/1024/1440 passed. Browser includes all7 modules, user/subscription actions, settings retry, session expiry, suspended admin, logout and forged-role denial. MySQL metadata queries were read-only and passed. Real active admin count remains0; developer must choose the real credentials and run the explicit bootstrap. No real MySQL account or financial write, migration, secret/backup change, commit or deployment was performed.
