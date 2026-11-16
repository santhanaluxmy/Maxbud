# MaxBud core flow implementation

16 November 2026. Implements the user-authorized core-feature and frontend/backend/database connection work following the audit. The original audit reports remain a historical snapshot; this document records subsequent changes and fresh results. The actual PRD is still unavailable, so this is not a claim that all PRD requirements are complete.

## Connected flow

```text
React pages
  -> shared API URL (/api by default)
  -> Vite development/preview proxy (or configured public API URL)
  -> existing FastAPI authentication and financial endpoints
  -> SQLAlchemy sessions
  -> configured MySQL database
```

All API callers now share `frontend/src/api/base.js`: public catalog, registration/login/profile, Google authentication, financial requests, receipt uploads and advisor requests. No caller separately invents a hard-coded browser backend address. Existing `VITE_API_URL` and legacy `VITE_BACKEND_URL` overrides are retained. URL whitespace/trailing slashes are normalized. Default local routing is `/api`; `API_PROXY_TARGET` sets Vite's server-side target, defaulting to port 8000. The production host must provide an `/api` reverse proxy or a public backend URL.

The active Accounts page now exposes a transfer form using the existing `/transfers` API, same-currency active accounts, Decimal-compatible amount strings, and a stable submission UUID. The button waits for two active accounts to load. The source and destination balances refresh after success; transfers remain excluded from income/expense totals. The form reuses existing modal, card/button styles and API error handling. Selects have explicit accessible labels.

## Financial behavior fixed

- **Personal savings retries:** new personal contributions write to the existing `goal_contributions` ledger and respect an optional `request_id`. Repeating the same key/goal/amount returns the goal without another increment; conflicting key reuse returns 409. The frontend generates the key when opening the contribution form and retains it while retrying. Existing keyless callers remain supported; their separate submissions remain separate contributions and cannot be deduplicated automatically.
- **Historic savings preserved:** existing `saved_amount` remains the baseline. No historic backfill or rewrite runs. Only future contributions produce ledger rows. Personal ledger rows are excluded from `allocated_shared()` to prevent counting the same allocation twice in safe-to-spend.
- **Payment consistency:** generic transaction editing/deletion rejects reminder-linked or confirmed-receipt-linked payments with 409. Transfer-linked entries remain protected. This phase prevents inconsistent direct mutation; it does not implement a separate audited refund/reversal workflow.
- **Balance corrections:** transaction edits/account moves/deletions and account opening-balance edits check resulting balances under the account locks. Corrections cannot create a deficit or worsen an existing one. Genuine historical negative balances are not rewritten; changes that leave them unchanged or improve them are supported. Failing changes roll back the entire mutation, including both accounts on a move.
- **Database-compatible form limits:** registration/profile/onboarding full names and onboarding income names are capped at the verified live capacity of 100. Google names are truncated consistently. ORM user name/email and income name/precision now reflect the inspected existing schema. This adjusts source contracts to the existing schema; no table alteration occurs.

## Files changed and purpose

| Files | Purpose |
|---|---|
| `frontend/src/api/base.js` (new) | Shared normalized API URL and URL builder. |
| `frontend/src/api/client.js`, `api/auth.js`, `api/finance.js`, `services/authApi.js` | Route authenticated, financial and authentication calls consistently. |
| `frontend/src/components/auth/GoogleAuthButton.jsx`, `pages/landingpage/LandingPage.jsx`, `pages/userdashboard/dashboard/AI.jsx` | Use the same base for Google login, public plans and multipart receipt uploads. |
| `frontend/vite.config.js`, `frontend/.env.example` | Configurable same-origin proxy for dev/preview; document public versus server-side settings. |
| `frontend/src/pages/userdashboard/dashboard/AccountTransfer.jsx` (new), `Dashboard.jsx` | Wire active transfer form, stable contribution retry IDs, account loading guard and explicit select labels. |
| `backend/app/routers/goals.py`, `services/goals.py` | Personal contribution replay, persisted ledger and rollback; exclude personal rows from shared allocation totals. |
| `backend/app/routers/account.py`, `routers/transaction.py`, `services/account.py` | Validate post-correction balances, atomic rollback and protect linked payments. |
| `backend/app/models/user.py`, `models/finance.py`, `schemas/auth.py`, `schemas/onboarding.py`, `routers/auth.py`, `routers/settings.py` | Align source/input field sizes with the already inspected MySQL schema. |
| `frontend/src/pages/register/RegisterPage.jsx`, `pages/onboarding/Onboarding.jsx`, `pages/userdashboard/dashboard/Settings.jsx` | Match UI input limits to backend/database contracts. |
| `backend/tests/test_core_finance_flow.py` (new) | 17 core-flow regressions and acceptance cases. |
| `backend/tests/core_flow_browser.py` (new) | Browser → proxy → API → temporary SQL database journey, retry fault injection and restart persistence. |
| `frontend/tests/api-client.test.mjs` (new), `tests/auth.test.mjs` | API URL normalization, auth headers, retry keys, exact amount strings and validation/error contracts. |
| `README.md`, this document | Start/test instructions, behavior and remaining limits. |

Private environment files are unchanged. No migration was added/applied, dependency installed, genuine financial row modified, admin provisioned, payment activated, commit made or deployment performed.

## Run locally

Use the existing private backend environment configuration. In separate terminals:

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

Open the Vite URL shown in the terminal. With no public API override, the browser calls `/api` and Vite forwards to FastAPI on port 8000. If FastAPI uses another local port, set `API_PROXY_TARGET` for Vite. For separately hosted frontend/backend services, set `VITE_API_URL` to the public API and configure the allowed frontend origin on FastAPI. Restart Vite after changing its environment. Keep database credentials, signing secrets and provider keys exclusively on the backend.

Expected flow: register → five onboarding steps → dashboard → create/adjust accounts → income/expense transactions → transfer between accounts → review budgets → contribute to goals → create/pay a reminder → view reports. Reloads and future sign-ins read persisted records. Goal contributions reserve savings without moving tracked account balances; paying a reminder creates an expense; transfers move money without adding income/expense.

## Run tests

From `backend`:

```bash
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/core_flow_browser.py
```

The browser runner requires the already installed Playwright and `/usr/bin/google-chrome`. It starts FastAPI on 8768 and Vite on 5178, sets a server-side proxy target, disables external providers and uses its own temporary SQLite file. All services stop afterward, including on failure. Its restart check reopens the same temporary file. Do not set MySQL write-test mode against genuine data.

From `frontend`:

```bash
npm run lint
npm test
npm run build
```

## Actual verification

- Baseline regression run before fixes: 15 test methods executed; 13 methods failed (15 assertion failures including subtests), exposing the intended financial gaps. Two existing valid-edit/delete scenarios passed.
- First implementation run: **63 backend tests passed**, including the 15 new methods, in 72.061s.
- After database input-limit coverage: **65 backend tests passed**, including 17 new methods, in 74.049s. The complete scenario checks onboarding, income1000, expense40, transfer100, contribution25 retried, bill50 paid twice safely, balances910/100, expenses90, savings25, safe-to-spend925 and report closing1010.
- Frontend lint and Node tests passed after API URL integration; Node runner reports **four passing test files**. Production build passed. Final post-transfer checks are recorded below.
- Read-only **real MySQL connection through the frontend proxy passed**: a temporary Vite server forwarded `/api/health` to the actual FastAPI app, whose lifespan/health executed configured MySQL `SELECT 1`; result200/database connected. Proxied accounts rejected an unauthenticated request; the public plan catalog returned LKR data. Those temporary servers were stopped. No private records were queried or changed by this smoke check.

Final results:

- **Browser core-flow suite passed (exit 0):** real browser registration, five-step onboarding, second account creation, income/expense entry, paired transfer, a simulated lost contribution response followed by a retry with the same key, one saved allocation, bill payment, budget/report reconciliation, API restart against the same temporary database, reload, sign-out/sign-in and no browser JavaScript errors. Every browser API call went through `/api`; no direct backend-origin requests were observed.
- **Final frontend checks passed:** `npm run lint`; `npm test` (four passing files, zero failures); `npm run build -- --outDir /tmp/maxbud-connected-build` (2354 modules, 3.09s). JavaScript bundle is 831.86kB /241.12kB gzip; the existing large-chunk warning remains.
- `git diff --check` passed. Backend coverage remained **65 passing cases**; no backend source changed after that successful run.
- During browser-test development, the initial attempt stopped at an account-select label and the second at an overly strict transaction-cell selector (the cell also includes “Money in”). Select accessibility labels and the test selector were corrected before the final passing run. Those failed development runs are not claimed as passes.

## Remaining limits

- Browser mutation and restart acceptance uses SQLite. Real MySQL connectivity was verified read-only; full MySQL mutation/concurrency proof still requires a separately provisioned disposable test database. No multi-connection race claim is made.
- Keyless contribution requests retain backwards-compatible behavior and are not retry-safe; the updated UI always supplies a stable key.
- Generic linked-payment mutation is intentionally blocked. A dedicated audited reversal/refund flow is future work.
- Password-change JWT revocation, forgotten-password recovery, dedicated AI planner/predictions, real payment gateway, external AI/OAuth acceptance, production deployment/restore and comprehensive accessibility remain separate roadmap tasks.
- Existing production bundle-size/image warnings remain. No redesign or dependency upgrade was introduced.
