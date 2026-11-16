# Controlled beta deployment guide — November 15, 2026

The code is prepared for controlled beta validation. No public deployment or ten real participants is claimed. Local checks do not prove external HTTPS, restore procedures, deliverability, capacity or multi-device behavior.

## Configuration

Backend private environment names:

- `ENVIRONMENT`: development/test/beta/production. Public controlled demo uses beta, not production with a bypass.
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`; `DB_SSL_CA` for verified MySQL TLS in beta/production. Use a least-privilege runtime account and separate migration operator.
- `JWT_SECRET`: random >=32 characters; `JWT_MINUTES`; keep out of source/logs.
- `FRONTEND_ORIGIN`: exact HTTPS frontend origin for beta/production; no wildcard CORS.
- `GROQ_API_KEY`, `GROQ_VISION_MODEL`, `GROQ_CHAT_MODEL`: server only. Verify live model availability and provider budget/rate limits.
- `DEMO_PAYMENTS_ENABLED`: false by default; explicit true only for controlled demo/local testing. Production rejects true. No real payment credentials are needed.
- `PLAN_PRICES_JSON`: operator-configured optional demo prices; no final prices are assumed.
- `FAMILY_PACK_MEMBER_LIMIT`: total users including owner; default6.
- `RECEIPT_STORAGE_DIR`: private durable directory outside webroot with restricted permissions and backup/access policy.
- `RATE_LIMIT_ENABLED=true` for exposed environments. Current limiter is in-process; start with one worker or add a shared limiter before multiple workers.
- `GOOGLE_CLIENT_ID`: optional, configure matching authorized frontend origins in Google console. Live OAuth redirect validation remains an operator check.

Frontend: `VITE_API_URL` points to HTTPS API; optional `VITE_GOOGLE_CLIENT_ID` must match backend. No Groq, DB or JWT signing secrets in frontend variables. Existing `.env` files were preserved; supply deployment values through the hosting secret manager. Never copy their real values into an example file.

## Release steps

1. Review the diff and updated docs. Confirm backup availability and rehearse restore on an isolated database. Preserve the existing supplied backup archives unchanged; create separately named future backups.
2. Stage a copy of the existing schema, verify current revision and apply only `alembic upgrade maxbud_features@head`. Current local feature head is `20261115_beta`; never blindly apply the separate legacy accounts head.
3. Install locked frontend dependencies with `npm ci`, backend requirements in a virtual environment, build with `npm run build`. Configure persistent private receipt storage and sufficient free space.
4. Serve the built frontend and FastAPI behind HTTPS/reverse proxy with request-body limits/timeouts matching <=5MB uploads and <=45s AI calls. Trust forwarded headers only from the proxy. Bind MySQL privately and verify certificate hostname/CA. Test CORS from the actual origin.
5. Keep one API worker initially for the current rate limiter. Configure process restarts, health probes, sanitized error logs and alerts for AI failures/disk/database issues. Set proxy upload size and stop verbose request/body logging.
6. Bootstrap an existing operator account only with explicit `bootstrap_admin.py --email ... --apply`; do not expose public admin signup. Test regular-user denial and suspended-user denial.
7. Run local/API/browser checks below, then test real phones/laptops across networks on staging. Receipt and advisor requests transmit selected data to Groq; explain this before recruiting users.
8. Review provider spend, data retention, backup frequency and restoration ownership. Do not claim production readiness until external checks and isolated MySQL race tests pass. No real payment gateway is part of this release.

## Ten-user checklist (not yet executed by real users)

Recruit five new Free Trial users and five explicitly demo-paid/sponsored users: two Family Pack owners, two invited members and one Premium Individual. Use consenting participants and their own test data; do not create fake public activity. Record participant consent, device/browser, date, result and issue reference without passwords or raw receipts.

| Participants | Required checks |
| --- | --- |
| Trial users 1–5 | Landing → register → login → full onboarding → account → income/expense → transfer → budget → personal goal → month report; refresh/re-login persistence |
| Trial users 1–5 | Real receipt upload/review/correct/confirm once; cropped missing-total receipt; English/Tamil/Tanglish advisor; per-user credit changes; failure retry without successful charge |
| Demo users 6–10 | Monthly/yearly catalog, failed then successful checkout, clear no-money disclosure, trusted expiry, cancellation, renewal, scheduled change; reload confirms persisted state |
| Owners 6 and 8 | Create separate households; invite email match/expiry/reject/revoke; seat limits; grants/revocations; cross-family isolation; owner-only controls |
| Members 7 and 9 | Accept secure link, sponsored access, retain private salary/accounts; leave/rejoin with new invitation; existing paid plan remains intact |
| Each household | Owner300 + member200 shared goal=500; wallet20000+30000=50000 → groceries8000=42000; both authorized shared reports |
| Each household | Personal-paid bill12000 equal split → owed6000 → partial2000 → remaining4000; no duplicate expense; custom/percentage rounding; household bill pay replay |
| All 10 | Mobile navigation/forms/modals, meaningful error/loading/empty states, forbidden admin access, JSON export and privacy |
| Operator | Admin search/suspend/reactivate/subscriptions, AI failure/usage counts, labelled demo reports, no private receipt or transaction exposure; backup/restore and health checks |

Trial/period expiry can be exercised on isolated staging fixtures; never rewrite real participants' dates in production. Track real participation separately from automated synthetic fixtures. Ownership transfer is intentionally unsupported; an owner cannot abandon a household with history.

## Safe test commands

From backend: `.venv/bin/python -m pytest tests -q`; `FAMILY_TEST_MYSQL=1 .venv/bin/python -m unittest discover -s tests -v` uses inspected outer rollbacks. Live tests consume Groq requests: `FAMILY_TEST_MYSQL=1 PYTHONPATH=.:tests .venv/bin/python tests/live_groq.py`; `.venv/bin/python tests/beta_browser.py`. Preserved family browser: `.venv/bin/python tests/family_browser.py`. From frontend: `npm test`, `npm run build`, targeted eslint, `../backend/.venv/bin/python tests/ui_browser.py`.

Do not run `family_mysql_races.py` under the current database restrictions: its historical isolated-database lifecycle is not approved by the latest no-DROP rule. Existing error1044 blocks isolated multi-connection verification; do not change grants or repoint it to application data.
