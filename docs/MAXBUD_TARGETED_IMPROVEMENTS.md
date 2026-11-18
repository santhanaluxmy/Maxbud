# Targeted MaxBud improvements — configuration and verification

## Scope and data safety

Existing uncommitted Family Management routing, member UX, calculations and tests were preserved. The hero JSX and its styles were not changed. Only the cream feature-card border override changed; backgrounds, card content, dimensions, images and animations remain intact. Feature and pricing heading introductions were removed; card descriptions, pricing details, FAQ and hero content remain.

No existing MySQL, local-family sandbox, passwords, subscriptions, backups or financial rows were reset or migrated. Tests create disposable SQLite databases. Real Groq checks also use SQLite and a sample receipt. The only Stripe network operation performed for verification is a **read-only test-mode Price list**; no customers, Prices, payments or subscriptions were created by that inspection.

## Pricing and entitlement contract

`GET /subscriptions/plans` is the trusted catalog used by landing, Upgrade and server checkout validation. Premium Individual monthly is LKR 650; Family Pack monthly is LKR 900. Legacy monthly values in PLAN_PRICES_JSON cannot cause pages to disagree. Yearly prices continue to come from the existing configuration; no annual amount was invented. Both yearly amounts were unconfigured in the inspected installation and remain unconfigured.

New password/Google identities receive a single persisted three-calendar-month personal trial, using calendar arithmetic. Login does not recreate the trial or cancel a paid period. Expired personal trials preserve history/export and reject editing. Membership now confers **shared access only**: a member's personal plan, personal AI quota, personal editing policy and billing stay independent. Authorized shared goal contributions are checked against membership/Family Pack permission, not blocked by an expired personal trial. Shared bills and completed-goal notifications are scoped to currently authorized members. Shared financial activity reads existing ledgers and never exposes private payment account identifiers.

## Additive schema setup — not automatically applied

New migration: `backend/migrations/versions/20261117_access.py`. It adds only:

- `auth_session_versions`
- `password_recoveries`
- `stripe_test_accounts`
- `stripe_test_events`

There is no financial data backfill or destructive downgrade. Normal login remains compatible before the migration; recovery/Stripe endpoints return an explicit setup error if their tables are absent.

Review your current database/version and normal backups first. The existing `20261115_beta` migration must already be applied; do not stamp/reset an existing database to skip schema review. Then apply the new migration explicitly to the intended development database:

```bash
cd backend
PYTHONPATH=. .venv/bin/alembic upgrade 20261117_access
```

No migration was applied to the existing local-family sandbox in this task.

## Email recovery configuration

Set these in the backend environment yourself; `.env` was not edited:

```text
SMTP_HOST=<your supported provider's SMTP host>
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=<provider username>
SMTP_PASSWORD=<provider credential>
SMTP_FROM=<verified sender address>
```

Use `SMTP_SECURITY=ssl` with port 465 when required by your provider. Both modes verify TLS certificates. No SMTP values were configured during inspection, so real mailbox delivery is **not live-verified**. No phone/verified SMS integration exists; no unnecessary phone model was added.

Flow: `/forgot-password` → request email code → verify six-digit code → receive high-entropy reset proof → confirm new password → sign in again. Codes expire after ten minutes, allow five attempts and are stored as keyed hashes. Reset proofs are hashed and one-time. Per-email request limits and normal auth rate limits apply. Unknown/ineligible accounts receive the same generic response. Completing a reset invalidates every previous reset request and old JWT version. Codes, passwords and SMTP bodies are never logged. Provider failure logs only a generic configuration/connectivity warning; the UI never promises delivery succeeded.

Guidance: [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

## Stripe sandbox configuration

The configured test key authenticated a read-only Price query, but **no matching active LKR 650/900 monthly Prices were found**. Price IDs and the webhook signing secret were absent. API keys alone cannot enable checkout or activate access.

In the intended Stripe sandbox:

1. Create/reuse the Premium Individual and Family Pack Products.
2. Create recurring **monthly**, interval count 1, LKR Prices: Premium **650.00** (unit_amount 65000), Family **900.00** (unit_amount 90000). Copy the actual resulting IDs; do not put amounts into Price ID variables. Stripe Prices are immutable; replace a mismatched ID with a new matching sandbox Price.
3. Preserve any existing yearly Prices and approved annual amounts. Configure yearly IDs only when those amounts are already known; the app will not invent annual totals.
4. Configure a test webhook destination at `/billing/stripe/webhook`, using API version `2024-06-20`, for `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`, and `invoice.payment_action_required`.
5. For local forwarding, run `stripe listen --forward-to http://127.0.0.1:8000/billing/stripe/webhook` against the intended disposable/test application and copy its signing secret. Change the port to your intended test backend. Never forward test webhooks into an unrelated data instance.
6. Configure the sandbox Customer Portal: permitted Products/Prices, payment-method updates, invoices, plan changes and cancellation at period end. Enable supported resume/reactivation behavior. Copy the portal configuration ID if using a custom configuration.

Required backend values:

```text
STRIPE_SECRET_KEY=<sk_test_... or restricted rk_test_...>
STRIPE_WEBHOOK_SECRET=<whsec_... for the actual destination>
STRIPE_PRICE_PREMIUM_MONTHLY=<price_... for 650.00 LKR/month>
STRIPE_PRICE_FAMILY_MONTHLY=<price_... for 900.00 LKR/month>
STRIPE_PRICE_PREMIUM_YEARLY=<existing approved yearly price_... if configured>
STRIPE_PRICE_FAMILY_YEARLY=<existing approved yearly price_... if configured>
STRIPE_PORTAL_CONFIGURATION=<optional bpc_...>
FRONTEND_ORIGIN=<trusted development frontend origin>
```

The adapter pins its requests to `2024-06-20`, checks retrieved prices/objects are test-mode, validates amount/currency/interval/quantity and rejects live keys or production execution. A pending Checkout is reused, not duplicated. Checkout redirects never change entitlements. Signed webhooks re-fetch authoritative subscription state, require a paid matching invoice for activation, serialize per user and deduplicate event IDs durably. Delayed events therefore cannot roll back newer state. Renewal extends the verified period; cancellation-at-period-end retains paid access; failed/unpaid/canceled states restrict editing without deleting history. Customer Portal handles provider-side changes; signed webhooks synchronize the results.

Existing demo/test subscriptions are not silently converted to Stripe. An explicit reconciliation is required before replacing a source owned by that mechanism. Demo flags remain disabled by default and forbidden in production. Test Stripe entitlements are also invalid in production.

References: [Stripe Checkout API](https://docs.stripe.com/api/checkout/sessions/create), [subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks), [signature verification](https://docs.stripe.com/events/manage-webhook-endpoints), [Customer Portal](https://docs.stripe.com/customer-management).

## Verification commands and artifacts

```bash
cd backend
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
FAMILY_TEST_MYSQL=0 PYTHONPATH=.:tests PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/live_groq.py
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/improvements_browser.py
```

The browser runner uses a fresh temporary database, real FastAPI/Vite/Chrome, and **mocked AI and SMTP transports**. It cannot use the existing family sandbox. It checks real browser registration/login/recovery, receipt upload/review/save/refresh, advisor history, admin modules and widths 360/768/1024/1440. Its synthetic admin/paid-period fixtures affect only disposable users. The separate `live_groq.py` run uses the real configured Groq provider and a sample image.

Frontend checks: `npm run lint`, `npm test`, `npm run build` from `frontend`.

Logs: `/tmp/maxbud-improvements-tests.log`, `/tmp/maxbud-improvements-full.log`, `/tmp/maxbud-improvements-live-groq.log`, `/tmp/maxbud-improvements-browser.log`. Screenshots use `/tmp/maxbud-polish-<width>-<module>.png`.

Observed real Groq result: six extracted items, missing printed total retained as null, reviewed subtotal LKR 1017, exactly one transaction after retry, exact balance/budget updates, one persisted advisor response and one successful credit for each feature. No existing user data was used.

## Boundaries

Real SMTP delivery and a real Stripe Checkout/webhook/portal round trip are not verified without the missing configuration. MySQL financial writes/concurrency are not claimed by SQLite tests. Shared reports retain their current scope and calculations; a full dated shared running-balance report and all historical edit-attribution remain separate gaps. No unrelated page, dependency installation, real charge, commit, push or deployment is included.

## Final observed results

| Requested area | Classification | Evidence |
|---|---|---|
| Landing cards/headings/approved hero | IMPLEMENTED AND VERIFIED | Browser computed all six border treatments equal; hero section source unchanged; section introductions removed only where requested. |
| Monthly pricing/annual preservation | IMPLEMENTED AND VERIFIED | Catalog/landing show 650 and 900; unit tests preserve separately configured yearly values. |
| Trial/personal Premium/Family permissions | IMPLEMENTED AND VERIFIED | Full backend suite; independent member personal plan; owner + five; expiry/history/export; cancellation/renewal/denials. |
| Login/register branding | IMPLEMENTED AND VERIFIED | Browser registration, invalid credentials and login; centered logos at all four requested widths. |
| Password recovery | IMPLEMENTED BUT NOT LIVE-VERIFIED | Browser request/OTP verification/reset/new-password login and old-JWT rejection passed with mocked SMTP. Real delivery blocked by missing configuration. |
| Receipt scanner | IMPLEMENTED AND VERIFIED | Browser image upload/review/save/refresh; actual Groq image extraction and exactly-one persisted transaction, balance/budget reconciliation in fresh SQLite. |
| Advisor | IMPLEMENTED AND VERIFIED | Actual Groq response/history; browser English/Tamil/Tanglish safe rendering and persisted history; quota/privacy regressions. |
| Family, Scanner, Advisor, Admin polish | IMPLEMENTED AND VERIFIED | Scoped CSS; 360/768/1024/1440 browser checks and screenshots. Admin login, seven real data endpoints and confirmed test-user suspension/reactivation passed. |
| Stripe sandbox integration | IMPLEMENTED BUT NOT LIVE-VERIFIED | Verified-signature/retry/price/cancel/renewal/failure/paid-period tests mocked Stripe. Actual read-only Price API authenticated, but no matching monthly Prices/configured IDs or webhook secret were available. |
| Real Stripe Checkout / SMTP delivery | BLOCKED | Complete the external setup above; no live charges or fabricated delivery. |

Final full backend result: **101 tests passed in 123.588 seconds**. Four frontend test files, lint, production build and `git diff --check` passed. The build retains its existing large-bundle warning. The full browser run exited successfully with no JavaScript errors. A separate expired-personal-trial member browser run also passed: shared goal allocation 200, wallet funding transfer 100, expense 150, bill payment 10, shared notifications/activity/reports, personal editing/AI denial and owner permission revocation. Resulting shared totals: income 1000, expenses 160, funding 100, wallet balance 940.

Two issues found during verification were repaired: the Family mobile links forced page overflow, and schema inspection on a second connection rolled back an in-memory cash-flow fixture's pending transaction. Scoped Family wrapping and inspection on the existing transaction connection fixed them; the final checks above passed. Early browser test fixture/selector/startup failures were corrected, not counted as passing results.

The full suite and browser runner use test-only SQLite in-memory journaling to avoid slow disposable-file fsyncs on the host. This does not change application database durability, authorization, provider configuration or any existing data. No application migration has been applied automatically.

Final logs: `/tmp/maxbud-improvements-complete-suite-final.log`, `/tmp/maxbud-improvements-browser-stable-final.log`, `/tmp/maxbud-improvements-member-browser.log`, `/tmp/maxbud-improvements-final-security.log`, `/tmp/maxbud-improvements-live-groq.log`. The stable browser run waits for populated pages before checking widths/capturing screenshots. The final eight focused security/billing tests passed after adding current locked reads for webhook mappings and duplicate events.

## File map

Pre-existing uncommitted Family changes were retained and extended only for these requirements.

| Area | Files added/modified in this task |
|---|---|
| Backend configuration/session/auth | `backend/app/core/config.py`, `core/security.py`, `core/deps.py`, `app/main.py`, `app/routers/auth.py` |
| Recovery | `backend/app/models/access.py`, `app/routers/recovery.py`, `app/services/recovery.py` |
| Stripe/pricing/entitlements | `backend/app/routers/billing.py`, `app/services/stripe_test.py`, `app/routers/subscriptions.py`, `app/services/subscriptions.py` |
| Shared permissions/notifications/history/Admin catalog | `backend/app/routers/goals.py`, `household.py`, `notifications.py`, `admin.py` |
| Additive migration | `backend/migrations/env.py`, `migrations/versions/20261117_access.py` |
| Landing | `frontend/src/pages/landingpage/LandingPage.jsx`, `LandingPage.css` |
| Authentication | `frontend/src/App.jsx`, `pages/login/LoginPage.jsx`, `LoginPage.css`, `PasswordRecovery.jsx`, `pages/register/RegisterPage.jsx`, `RegisterPage.css` |
| Modules | `frontend/src/pages/userdashboard/dashboard/AI.jsx`, `Admin.jsx`, `Upgrade.jsx`, `TargetedModules.css`; `family/FamilyPage.jsx`, `FamilyPage.css`, `HouseholdFinance.jsx` |
| Tests | `backend/tests/test_requested_improvements.py`, `improvements_browser.py`, `test_beta.py`, `test_local_family_access.py` |
| Updated contract/setup documentation | `LOCAL_FAMILY_TESTING.md`, `docs/MAXBUD_FAMILY_PACK_FLOW.md`, `docs/MAXBUD_FAMILY_MEMBER_REPAIR.md`, this document |

Previously uncommitted `DashboardOverview.jsx`, `DashboardLayout.jsx`, `navigation.js`, family browser helpers and `family_member_browser.py` remain present; they were not replaced.
