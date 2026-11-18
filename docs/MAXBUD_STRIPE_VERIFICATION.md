# MaxBud Stripe verification — 18 November 2026

The saved subscription implementation was continued, not replaced. The existing
paid sandbox purchase for **MaxBud user 7** has now been reconciled into MySQL.
No new payment, Stripe subscription, customer, or checkout was created during
verification. No migrations, database resets, or financial-record changes ran.

## Results

| Requested item | Result | Evidence and scope |
| --- | --- | --- |
| Backend subscription, webhook, authentication and entitlement tests | **PASS** | Full backend suite: **111 tests passed** in 328.868 seconds. Dedicated subscription suite: 10 passed; auth: 9 passed; existing improvements/webhook/trial/recovery: 8 passed. |
| Webhook route, signatures, HTTP responses and commits | **PASS** | Actual temporary FastAPI server, configured MySQL, registered `POST /billing/stripe/webhook`. Invalid signature returned **400**. Existing API-verified `invoice.paid` event replay returned **200**; duplicate returned **200** with `duplicate: true`. A new DB connection found the event and active Premium entitlement. |
| Automatic Stripe webhook delivery configuration | **FAIL** | At audit time Stripe returned **zero registered webhook endpoints**, no Stripe CLI listener was running, and no FastAPI server answered on port 8000. There was no active delivery path in this environment. See setup below. |
| Existing purchase ownership and reconciliation | **PASS** | All 21 ownership/payment checks passed. Customer metadata and email, checkout client reference and customer, subscription metadata, paid invoice customer/subscription, test mode, monthly price and paid-through date matched user 7. Fresh DB connection: exactly **one** subscription row, `premium_individual`, `active`, `stripe_test`, monthly, paid through **17 December 2026**. Other users' subscription rows were fingerprinted before/after and were unchanged. |
| Backend quotas and existing usage | **PASS** | Actual user 7: **1 / 100** receipt scans and **1 / 200** advisor messages; existing usage unchanged. API tests reject new scans at 100, messages at 200 and goals above 20. Tests also prove trial limits 5/10/3, existing usage preservation, cancellation/renewal, and household privacy. |
| Refresh, logout/login, another browser and restart | **PASS** | Browser tests with real FastAPI and disposable SQLite retained Premium after reload, sign-out/sign-in, a second isolated browser context and restarting FastAPI. Separately, actual user 7's entitlement was read from a fresh MySQL connection and by the newly started webhook server. The real user's password was neither requested nor bypassed. |
| Payment-return UI and shared subscription refresh | **PASS** | Browser -> Vite proxy -> FastAPI -> SQLite, with **mocked Stripe responses**. Incomplete payment stayed on “Activating your subscription…” with trial access. Verified activation showed Premium Active / Family Pack Active, Current Plan, preserved 3/100 scans and 2/200 messages, and household creation for Family Pack. Desktop 1440px and mobile 390px had no horizontal overflow or page errors. |
| Customer Portal configuration | **PASS** | Actual Stripe API returned an active default test configuration. Payment method updates and invoice history enabled; cancellation enabled at period end; subscription switching disabled. An explicit `STRIPE_PORTAL_CONFIGURATION` override is unnecessary while this default is used. **No Dashboard changes are required for the current portal configuration.** |
| Frontend tests/lint/build | **PASS** | Five Node test files passed. ESLint: zero errors/warnings. Production build passed, with the existing large-bundle warning. |
| New hosted Stripe Checkout/card payment and external forwarding | **NOT VERIFIED** | No new payment was performed. Browser tests mocked the payment provider; the real existing purchase was verified through Stripe's API. The HTTP replay used a locally generated signature over the existing API-retrieved event; it was **not** delivery from Stripe CLI or a registered event destination. |
| Hosted portal payment-method change/cancellation | **NOT VERIFIED** | Configuration and backend portal contract were checked; genuine customer payment methods and renewal settings were not changed. |

## Root cause and limits of the diagnosis

Stripe had a completed, paid checkout and an active Premium subscription for user
7, but MaxBud had no subscription row for that user and zero processed events.
The old return page neither reconciled the provider state nor waited for a
persisted activation. Consequently a missed/rejected webhook left the user on
legacy Free access despite payment.

The current route is correctly registered without an `/api` prefix on FastAPI.
`/api` is the frontend proxy prefix only. The actual HTTP handler and database
commit now pass. The adapter handles both older invoice `subscription` fields
and current `parent.subscription_details.subscription` fields; incoming events
in this sandbox use Stripe API version `2026-10-28.endive`.

The absence of any active destination/listener/server was observed directly.
Historical CLI output was unavailable, so the original CLI shutdown, forwarding
URL and original delivery-signature match cannot be reconstructed. No claim is
made that the original signing secret was wrong. A genuine CLI delivery and its
signing-secret match remain **NOT VERIFIED** until forwarding is started.

## Files completed or adjusted in this continuation

- `backend/app/services/stripe_test.py`: accept only verified test-mode entries in the read-only event, webhook-endpoint and portal-configuration list responses used by the audit.
- `backend/tests/test_stripe_subscriptions.py`: complete receipt category fixtures and exact backend quota checks; use a distinct image for the at-limit scan test because retrying an existing scan deliberately does not charge another scan.
- `frontend/tests/subscription-render.test.mjs`: fix the router import used by the rendering test; verify monthly cards, current-plan protection, preserved usage and no unverified active confirmation.
- `backend/tests/stripe_browser.py`: disposable browser integration harness, including pending activation, Premium and Family Pack, privacy of test data, reload/login/restart persistence and responsive controls. Stripe calls are mocked only inside this harness.
- `backend/scripts/verify_stripe_subscription.py`: read-only operator audit by default; optional explicit, single-user, provider-verified reconciliation and HTTP replay. It never creates payments or changes Stripe billing settings and never prints credentials.
- This report. The previously completed application UI/state/reconciliation work and unrelated workspace changes were preserved.

The database change was limited to user 7's subscription and Stripe association,
one reconciliation audit entry, and one processed existing Stripe invoice event.
No financial history or usage rows were inserted, edited or removed in MySQL.

## Verification commands and local evidence

Run from `backend`:

```bash
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=. .venv/bin/python scripts/verify_stripe_subscription.py --user-id 7
.venv/bin/python tests/stripe_browser.py
```

The browser harness requires Node/npm on PATH, Playwright in the backend venv,
and `/usr/bin/google-chrome`; it always uses its own temporary SQLite database.

The read-only audit checks the actual configured Stripe sandbox and MySQL. For
an independently verified existing purchase requiring repair, the operator can
add `--apply`; `--local-http-check` additionally replays a matching provider event
through a temporary server. It does not start a permanent webhook listener.
User 7 **already passed this repair** and does not need to pay again or rerun it.

Run from `frontend`: `npm test`, `npm run lint`, `npm run build`.

Logs from this run:

- `/tmp/maxbud-stripe-full-backend.log`
- `/tmp/maxbud-stripe-contract.log`
- `/tmp/maxbud-stripe-auth.log`
- `/tmp/maxbud-stripe-improvements.log`
- `/tmp/maxbud-stripe-frontend.log`
- `/tmp/maxbud-stripe-lint.log`
- `/tmp/maxbud-stripe-build.log`
- `/tmp/maxbud-stripe-reconciliation.log` — sanitized actual ownership/DB/HTTP evidence
- `/tmp/maxbud-stripe-browser.log`
- `/tmp/maxbud-stripe-desktop.png` and `/tmp/maxbud-stripe-mobile.png` — synthetic browser test accounts

## Restore real local webhook forwarding

1. Start FastAPI from `backend`:

   ```bash
   .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. In a private terminal with Stripe CLI installed and authenticated to the same
   sandbox as the configured test key, keep this listener running:

   ```bash
   stripe listen --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.async_payment_failed,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,customer.subscription.paused,customer.subscription.resumed,invoice.paid,invoice.payment_failed,invoice.payment_action_required --forward-to http://127.0.0.1:8000/billing/stripe/webhook
   ```

3. Privately put **that listener's** signing secret in `backend/.env` as
   `STRIPE_WEBHOOK_SECRET`, then restart FastAPI. Do not paste secrets into chat,
   logs, source files or frontend configuration. A Dashboard endpoint signing
   secret is not a replacement for the active local CLI listener's secret.
4. Start Vite from `frontend` with `npm run dev`. Use
   `http://localhost:5173`, matching the configured `FRONTEND_ORIGIN`. Using the
   same origin for login and return preserves the browser's existing auth session.
5. Log into user 7's existing account and open Subscription. It should already
   show Premium Individual, Current Plan, LKR 650/month, 1/100 scans, 1/200
   advisor messages and 20 active goals allowed. Reload and sign out/in; the
   values should persist. Do **not** buy another subscription for that account.

For a deployed backend, register a test-mode Stripe webhook event destination
at its public HTTPS `/billing/stripe/webhook` URL with the events above and use
that destination's signing secret. Localhost itself is not a public endpoint.
Stripe's [CLI forwarding guide](https://docs.stripe.com/cli/listen) and
[subscription webhook guide](https://docs.stripe.com/billing/subscriptions/webhooks)
describe these two delivery options.

## Optional fresh hosted-checkout acceptance test

This was deliberately **not executed** during this continuation. To verify
external forwarding and a fresh Checkout payment yourself:

1. With the listener/backend/frontend running, use separate fresh test accounts
   for **Premium LKR 650/month** and **Family Pack LKR 900/month**.
2. Choose Upgrade to Premium / Choose Family Pack. Verify the monthly LKR amount
   on Stripe's **test-mode** Checkout. Use a [Stripe test card](https://docs.stripe.com/testing#cards),
   such as `4242 4242 4242 4242`, a future expiry and a valid-format CVC.
3. On return, expect Activating your subscription, then Premium Active / Family
   Pack Active. Open Dashboard and Subscription without re-login. Premium limits
   are 100 scans, 200 messages and 20 active goals; prior monthly usage remains.
4. The CLI should show HTTP **200** for the mapped customer's
   `checkout.session.completed`, `customer.subscription.created/updated` and
   `invoice.paid` events. Event order can vary. Duplicate deliveries must remain
   200 without new subscription rows. Invalid signatures must return **400** and
   grant no access. HTTP 409/502/503 means confirmation needs investigation; a
   payment-success screen alone does not prove activation.
5. For Family Pack, create a household and invite up to five members. Verify
   permitted shared access while members retain their own personal AI limits.
6. Open Manage Subscription to inspect invoice history and payment-method
   controls. If testing cancellation yourself, cancel **at period end**, check
   the corresponding subscription event returns 200, and verify access remains
   until the paid-through date. No cancellation was performed automatically.
7. In MySQL, inspect only the intended account and the event audit:

   ```sql
   SELECT user_id, plan, status, source, billing_cycle,
          period_started_at, expires_at, cancel_at_period_end
   FROM subscriptions WHERE user_id = 7;

   SELECT user_id, COUNT(*) AS subscription_rows
   FROM subscriptions WHERE user_id = 7 GROUP BY user_id;

   SELECT id, kind, received_at
   FROM stripe_test_events ORDER BY received_at DESC LIMIT 20;
   ```

   Replace `7` with the intended fresh test account's ID when testing that
   account. After this verification run, the existing user 7 has one persisted
   Premium row and one processed `invoice.paid` event from the documented local
   replay. Do not mistake that replay for a new Stripe CLI delivery.
