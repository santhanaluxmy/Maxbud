# Platform admin and security — November 16, 2026

Platform `admin` is independent of household owner/member roles. Public registration never accepts an admin role. Backend `current_user` verifies JWT signature/expiry/identity and current active database user; every `/admin/*` route requires actual database `role=admin`. The frontend AdminRoute independently loads `/auth/me`; editing session storage cannot authorize backend administration.

## Modules and endpoints

- `GET /admin/overview`: actual user/effective-plan and billing-state counts, registrations, successful/failed AI counts, demo events and labelled simulated totals. Verified real revenue is zero.
- `GET /admin/users`: search, activity/plan filters, registration metadata; `PATCH /admin/users/{id}` suspends/reactivates non-admin users. Self/other-admin suspension is blocked.
- `GET /admin/subscriptions`: status/plan/billing-cycle/period metadata; `PATCH /admin/subscriptions/{id}` supports audited suspend/past_due/reactivate within an existing legitimate unexpired period; cannot invent expiry or grant a paid plan.
- `GET /admin/billing`: demo history only, explicitly simulation-labelled.
- `GET /admin/ai-usage`: counts per user and safe failed-request events, not chat or image contents.
- `GET /admin/activity`: safe platform audit event metadata.
- `GET /admin/settings`: whitelisted nonsecret configuration flags/model IDs only.

The existing Admin page contains seven modules. Search, activity, billed-plan and monthly/yearly filters work. Users, subscriptions, billing and activity support paginated browsing with request-specific loading/error/empty states and retry. Support/activity is an audit viewer, not a ticketing or messaging system. Settings is read-only; secrets are never exposed or edited in the browser. This scope deliberately avoids unrestricted private finance access.

## Bootstrap

A read-only check on November16 found **zero active platform admins** in local `maxbud_db`. No real user was created, promoted, suspended or reset during this task. Provide an unused real operator email and choose the password privately in your terminal; never send it in chat or put it in `.env` or command arguments.

From an interactive terminal:

```bash
cd /home/uki-jaffna/Documents/MaxBud/backend
.venv/bin/python -m scripts.bootstrap_admin --email 'YOUR_ADMIN_EMAIL' --create
.venv/bin/python -m scripts.bootstrap_admin --email 'YOUR_ADMIN_EMAIL' --create --apply
```

Replace `YOUR_ADMIN_EMAIL` with the operator's unused real email. The first command is a dry run. The second requires a new password entered twice with hidden input. Use8–128 characters with uppercase, lowercase, a number and a symbol. Optional `--name 'Operator Name'` supports2–100 characters. Creation refuses an existing email; it never overwrites or resets an existing password. The operator is created with a normal hashed password identity and an audited platform role, without fake income/accounts or a household.

To deliberately promote an existing active password account, omit `--create`. Preview first, then use `--apply` and enter its **current password**. Promotion preserves all password hashes, personal finance, subscription and household ownership. OAuth-only accounts without password login must use a new operator email instead; this script does not reset credentials. Non-interactive password input/pipes are refused. No public admin signup exists. This CLI requires operator database access and is not exposed through HTTP.

Start the existing backend/frontend normally. Sign in at `/login` (normally `http://localhost:5173/login`); a genuine admin redirects to `/dashboard/admin`, bypassing personal-finance onboarding. Ordinary users retain their normal redirect. The frontend verifies `/auth/me`, checks session expiry while open, and backend permissions/status are checked on each request. Logout clears the session; suspended admins and expired/invalid tokens cannot use the APIs. Real operator login remains pending the developer's explicit CLI setup; isolated browser admin login has been verified.

## Other boundaries

Household reports use explicit family records and permission grants. Admin status is never granted by household creation. Invites use high-entropy tokens stored only as SHA256 hashes, seven-day expiry, invited-email matching, seat reservation and revocation. Frontend invitation tokens use the URL fragment and are stripped before routing. They are shared manually; no email-delivery claim is made.

Rate limits cover authentication, AI and general requests with CORS/retry headers. Monetary inputs use Decimal validation and account/household locks. File uploads validate bytes and safe storage. JWTs currently use sessionStorage; prioritize strong CSP, dependency review and HTTPS because an XSS compromise can access a bearer token. No claim of external penetration testing is made.

Local/development settings are not a public deployment profile. Beta/production enforce HTTPS frontend origin, verified MySQL TLS and enabled rate limits; production forbids unrestricted demo activation. See DEPLOYMENT_GUIDE for public-access gates.
