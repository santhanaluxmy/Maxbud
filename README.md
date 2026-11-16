# MaxBud

Existing React/Vite + FastAPI + MySQL personal and household budget application. The November 15 beta implementation preserves the existing design, accounts and financial history. It adds explicit household ledgers, persisted trials, demo subscriptions, Groq receipt review/advisor, and platform administration.

## Run locally

Backend: `cd backend`, activate `.venv`, install `requirements.txt`, then `uvicorn app.main:app --reload`. Frontend: `cd frontend`, `npm ci`, `npm run dev`. Configure the existing private environment files; never commit credentials. Run migrations only after reviewing [DATABASE_AUDIT.md](DATABASE_AUDIT.md). This repository contains two Alembic branches: use `alembic upgrade maxbud_features@head`, never `upgrade heads` against this existing database.

New users receive three calendar months of personal trial access, without an automatic household. Expired access retains history and JSON export. Legacy Free/Premium personal entitlements are retained. Shared household editing requires an active Family Pack for every account, including legacy households. Family Pack supports one owner and up to five invited people (six total users). Membership never grants access to private salaries or accounts.

## Connected local workflow

Start FastAPI from `backend` with `.venv/bin/python -m uvicorn app.main:app --reload` and Vite from `frontend` with `npm run dev`. Keep database credentials and the JWT secret in the existing private `backend/.env`. No database password or AI key belongs in a frontend variable.

All frontend clients share one API URL. Without an override, `/api` goes through Vite to `http://127.0.0.1:8000`; `API_PROXY_TARGET` changes that local target. An existing `VITE_API_URL` (or legacy `VITE_BACKEND_URL`) overrides the proxy for a separately hosted API. Restart Vite after environment changes. Production hosting needs either the public `VITE_API_URL` or a reverse proxy forwarding `/api` to FastAPI. The Vite proxy is only a development/preview service.

Register, complete the five onboarding steps, and use Accounts, Transactions, Budgets, Savings Goals, Reminders and Reports. Accounts now includes **Transfer money** between two active accounts. Transactions and transfers update tracked balances; goal contributions reserve savings without moving account money; marking a reminder paid creates its expense. Reports read the persisted ledger.

The new core-flow verification and remaining limitations are documented in [docs/MAXBUD_CORE_FLOW_IMPLEMENTATION.md](docs/MAXBUD_CORE_FLOW_IMPLEMENTATION.md). From `backend`, run `FAMILY_TEST_MYSQL=0 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` for disposable SQLite regressions, and `.venv/bin/python tests/core_flow_browser.py` for the browser → proxy → API → temporary database journey (requires existing Playwright and Chrome). The browser test restarts its own API to verify persistence; it never seeds genuine MySQL data.

Demo checkout is disabled by default. An operator can supply `DEMO_PAYMENTS_ENABLED=true` for local/controlled-beta simulation. No money is charged; no real payment integration exists. Production rejects unrestricted demo activation. Prices come from `PLAN_PRICES_JSON`, not invented defaults.

Groq requires `GROQ_API_KEY`, `GROQ_VISION_MODEL`, `GROQ_CHAT_MODEL`. Upload receipts through the existing scanner, review extracted fields, choose an existing category and account, then confirm. Missing printed totals remain null; calculated item subtotals are separately labelled. AI never directly executes financial writes.

## Verification and handoff

See [TEST_REPORT.md](TEST_REPORT.md) for actual results, [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for the 10-person beta checklist, and [MAXBUD_HANDOFF.md](MAXBUD_HANDOFF.md) for status and remaining gates. Module details: [FAMILY_MANAGEMENT.md](FAMILY_MANAGEMENT.md), [SUBSCRIPTION_IMPLEMENTATION.md](SUBSCRIPTION_IMPLEMENTATION.md), [GROQ_AI_INTEGRATION.md](GROQ_AI_INTEGRATION.md), [ADMIN_SECURITY.md](ADMIN_SECURITY.md).

No production deployment or real-user beta participation is claimed.

Family Pack sharing, common income/expenses, private ledgers and current verification: [docs/MAXBUD_FAMILY_PACK_FLOW.md](docs/MAXBUD_FAMILY_PACK_FLOW.md).
