# MaxBud

Existing React/Vite + FastAPI + MySQL personal and household budget application. The November 15 beta implementation preserves the existing design, accounts and financial history. It adds explicit household ledgers, persisted trials, demo subscriptions, Groq receipt review/advisor, and platform administration.

## Run locally

Backend: `cd backend`, activate `.venv`, install `requirements.txt`, then `uvicorn app.main:app --reload`. Frontend: `cd frontend`, `npm ci`, `npm run dev`. Configure the existing private environment files; never commit credentials. Run migrations only after reviewing [DATABASE_AUDIT.md](DATABASE_AUDIT.md). This repository contains two Alembic branches: use `alembic upgrade maxbud_features@head`, never `upgrade heads` against this existing database.

New users receive three calendar months of personal trial access, without an automatic household. Expired access retains history and JSON export. Legacy Free/Premium subscriptions are grandfathered. Family Pack sponsors one household with six total users by default. Membership never grants access to private salaries or accounts.

Demo checkout is disabled by default. An operator can supply `DEMO_PAYMENTS_ENABLED=true` for local/controlled-beta simulation. No money is charged; no real payment integration exists. Production rejects unrestricted demo activation. Prices come from `PLAN_PRICES_JSON`, not invented defaults.

Groq requires `GROQ_API_KEY`, `GROQ_VISION_MODEL`, `GROQ_CHAT_MODEL`. Upload receipts through the existing scanner, review extracted fields, choose an existing category and account, then confirm. Missing printed totals remain null; calculated item subtotals are separately labelled. AI never directly executes financial writes.

## Verification and handoff

See [TEST_REPORT.md](TEST_REPORT.md) for actual results, [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for the 10-person beta checklist, and [MAXBUD_HANDOFF.md](MAXBUD_HANDOFF.md) for status and remaining gates. Module details: [FAMILY_MANAGEMENT.md](FAMILY_MANAGEMENT.md), [SUBSCRIPTION_IMPLEMENTATION.md](SUBSCRIPTION_IMPLEMENTATION.md), [GROQ_AI_INTEGRATION.md](GROQ_AI_INTEGRATION.md), [ADMIN_SECURITY.md](ADMIN_SECURITY.md).

No production deployment or real-user beta participation is claimed.
