# Family invitations — implementation and local testing

18 November 2026. This change covers household invitations/membership and the authentication handoff needed to accept them. Existing private `.env` files, Stripe settings, genuine accounts and financial data were not modified. No deployment was performed.

## What was wrong

- The generated link used `window.location.origin` and a small unstyled input, so it inherited localhost and clipped the URL visually.
- The invitation endpoint never called an email service. The existing SMTP service was used only for password recovery.
- Fragment capture happened once at module import; client-side navigation and malformed fragments were not handled reliably.
- Login/register redirected invitees into personal onboarding. Returning members without personal onboarding also returned there after login.
- Invitations had no separate persisted email-submission status, loading/empty treatment or collapsed history.
- Owner counts did not refresh when an invitee joined in another browser. Close/revoke actions lacked the requested deliberate confirmation flow.

## Implemented behavior

- The membership section uses the existing cream/aqua/blush palette, member cards, a pending-invitations table and collapsed invitation history. The full-width link wraps and has a real clipboard Copy Link action, accessible status feedback and a manual-selection fallback.
- The backend generates `/invite#invite=…` from `PUBLIC_FRONTEND_URL`, falling back to `FRONTEND_ORIGIN`. The configured value must be an HTTP(S) origin, with HTTPS required in beta/production. Incoming request Host/Origin headers cannot choose email link destinations.
- `/invite` is a public review page. Preview uses POST; the secret stays out of request paths. Possession of the unguessable token allows invitation metadata preview, never financial data. Only an authenticated account with the exact invited email can accept.
- A pending token stays in sessionStorage through login, registration, account switching and refresh. Legacy `/dashboard/family#invite=…` links are supported. Accepted members can use shared household routes before setting up their personal budget. Personal routes retain their onboarding guard.
- Login returns a current `has_household` hint so a joined member without personal onboarding returns to the shared household. This hint grants no API authorization; existing backend membership and permission checks remain authoritative.
- Expired, revoked, declined, invalid and closed-household links have clear states. Retrying acceptance for the same active member is idempotent; a removed member cannot rejoin using an old accepted link. The owner plus five invited people remains the limit, with pending invitations reserving spaces.
- Membership refreshes after the action, on window focus/visibility and every five seconds while the membership view is visible. A second browser joining updates the owner's displayed count without a manual reload; this is polling, not a websocket.
- Revoke/remove actions use confirmation dialogs with keyboard/focus handling. Closing requires typing the household name. The server refuses closing if other memberships or shared accounts, transactions, goals, budgets or bills exist. Closing an empty household revokes its pending invitations, preventing their reuse if the owner later recreates the household.

## Email submission is separate from acceptance

Email status is recorded in existing PlatformEvent rows; no database migration is required and no plaintext token, email body or SMTP credentials are stored in these events.

| Email status | Meaning |
|---|---|
| `not_configured` | Invitation exists; **email not sent**. Manual sharing works. |
| `unconfirmed` | Invitation was saved before the SMTP attempt; final submission is not recorded yet. |
| `submitted` | SMTP accepted submission for the intended recipient. Inbox delivery/read receipt is not promised. |
| `failed` | Submission failed/refused; invitation remains usable through Copy Link. |
| `unknown` | Historical invitation without a recorded submission outcome. |

Invitation states (`pending`, `accepted`, `revoked`, `expired`, `rejected`) remain independent. The application does not interpret “pending” as an email-delivery failure. SMTP runs after the invitation transaction commits, so a failed provider does not discard the link or hold the household seat lock through a network call. Duplicate invitation requests cannot send a second email for the same active pending invitation.

The current local settings were inspected only as a boolean: **SMTP is not configured**. Real inbox delivery was not tested. Tests mock SMTP success, refusal and failure; no genuine invitation emails were sent.

## Test on this computer

1. Restart FastAPI and Vite to load the changes. Keep `FRONTEND_ORIGIN=http://localhost:5173` when that is the frontend address you use. Leave `PUBLIC_FRONTEND_URL` empty to inherit it, or use that same origin explicitly.
2. Sign in as an existing authorized Family Pack owner. Open **Family Management → Household membership**.
3. Enter the member's exact email and select **Create Invitation**. With no SMTP, the response says **“Invitation created — email not sent”**.
4. Select **Copy Link**. Open Chrome Incognito on the same computer and paste the complete link, including its fragment.
5. Choose sign in or create an account using the invited email. Review the household and choose **Accept Invitation**. Personal budgeting setup is optional for access to the shared household.
6. Confirm the member's dashboard opens, and the owner's membership count/list updates. Sign out using the mobile navigation drawer when testing narrow widths, then sign in again to verify membership persistence.

A localhost link points to the device opening it. It works for Chrome/Incognito on this computer, and does not make your app accessible on another person's device. A future hosted frontend needs its actual publicly reachable HTTPS origin in `PUBLIC_FRONTEND_URL` and the matching CORS origin in `FRONTEND_ORIGIN`. This task did not deploy anything.

Configure email privately through the backend environment when ready:

```dotenv
SMTP_HOST=<your provider's SMTP host>
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=<your SMTP login>
SMTP_PASSWORD=<your provider's SMTP/app password>
SMTP_FROM=<your verified sender address>
```

For an implicit-TLS provider, use its documented port (commonly 465) with `SMTP_SECURITY=ssl`. Both modes verify TLS certificates. Restart FastAPI after environment changes. Never put these variables in frontend `VITE_*` settings or commit the populated `.env`. The local example is documentation only; no credentials were populated automatically.

If you navigate away before saving a manually shared link, revoke the pending invitation and create a new one. Raw invitation tokens are not retrievable from the database because only their hashes are stored.

## Validation

- Focused backend suite: `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_family_invitations.py' -v` — **10 passed**, disposable SQLite and mocked SMTP.
- Full canonical backend regression: `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 SMTP_HOST='' SMTP_USERNAME='' SMTP_PASSWORD='' SMTP_FROM='' timeout 600 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` — **121 passed**, 0 failures, no skipped tests, 449.920 seconds. Provider integrations are mocked; this does not establish MySQL concurrency or live delivery.
- Frontend tests: `npm test` — **6 passed, 0 failed, 0 skipped** in the runner's file-level output (23.506 seconds); includes token handoff/account switching, return destinations, malformed links and public preview/error behavior.
- Frontend lint: `npm run lint` — **passed**, exit 0 with no errors or warnings.
- Production build: `npm run build` — **passed**, exit 0 (8.39 seconds). Vite retains the existing large-bundle warning; this change does not claim to resolve that separate performance issue.
- Browser acceptance: from backend, `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/invitations_browser.py`. This builds a separate temporary frontend and uses a temporary SQLite API and isolated Chrome contexts. It disables SMTP, Groq and Stripe. It checks clipboard, 360/1440 layouts, wrong-account switching, registration/acceptance, owner count refresh, shared wallet LKR 4,000/privacy, logout/login, duplicate/invalid/revoked/expired links and close/revoke confirmation.

Browser acceptance completed six successful milestone groups: layout/copy/email-status checks; authentication/registration/token retention/count update; shared wallet/privacy; logout/login and duplicate acceptance; invalid/expired/revoked states and collapsed history; typed close confirmation/cancellation and successful close. No browser JavaScript page errors were recorded. Financial test writes went through the real local API; SMTP submission tests were mocked, and actual inbox delivery remains unverified because SMTP is unconfigured.

The initial browser attempts found two test-harness selector issues (mobile sign-out requires opening the navigation drawer, and the revoke-confirm button's capitalization). Those selectors were corrected before the completed run; they were not represented as product defects. The focused ten backend tests are included in the full 121 count, not additional unique tests. Earlier full-QA findings remain a historical snapshot; this invitation change does not establish readiness of unrelated financial features.
