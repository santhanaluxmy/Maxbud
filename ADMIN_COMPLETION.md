# Card contrast and admin completion — 16 November 2026

## Implemented scope

Cards3 (AI Receipt Scanner) and6 (Family Sharing) now use **#F6E7B5** over the entire card surface. Their previous aqua illustration-stage background/divider is removed, leaving a continuous surface behind the original artwork. The surrounding section remains **#EEEAD7**. Other card colors, markup, dimensions, spacing, text and animations remain unchanged. No hero markup or hero CSS rule was edited; no gradients or replacement illustrations were introduced.

The existing admin page and APIs were extended, not replaced. Admin login now redirects to `/dashboard/admin`, including admins without personal-finance onboarding. Route access still verifies the actual `/auth/me` role; stored frontend role changes do not authorize API access. Idle expiry clears access, logout removes stored sessions, and suspended admins are rejected by the backend.

Admin data remains queried from the existing MySQL tables. The user view now exposes explicit billing-plan/cycle metadata, and user/subscription filters support monthly/yearly plans. User, subscription, billing and audit views support pagination. Responses are keyed to the current request so old data does not appear as current filtered results; loading, error/retry and empty states are provided. Monthly/yearly subscription breakdowns distinguish all five current experiences without altering entitlement logic. Legacy-free accounts without a subscription row match their displayed Free filter. Demo billing remains explicitly simulated; verified real revenue remains zero.

## First administrator: developer action required

The read-only check found **0 active platform admins** in `maxbud_db`, revision `20261115_beta`. No real user was created/promoted or had a password changed. Existing accounts and financial data were not reset.

Use a private interactive terminal. Replace `YOUR_ADMIN_EMAIL` with an unused real operator email:

```bash
cd /home/uki-jaffna/Documents/MaxBud/backend
.venv/bin/python -m scripts.bootstrap_admin --email 'YOUR_ADMIN_EMAIL' --create
.venv/bin/python -m scripts.bootstrap_admin --email 'YOUR_ADMIN_EMAIL' --create --apply
```

The first command previews without writing. The second prompts for a new password twice, with hidden input. Password:8–128 characters including uppercase, lowercase, a number and a symbol. Never put it in command arguments, environment variables, chat or documentation. Optional `--name` accepts2–100 characters. Existing emails cannot be overwritten.

For an existing active password account, omit `--create`, preview first, then repeat with `--apply`; the CLI verifies its current password before changing only its platform role. Existing hashes, finance, subscription and household ownership remain intact. OAuth-only accounts without password login should use a new operator email; no credential-reset mechanism is added. Bootstrap is an operator CLI requiring database access, never a public HTTP signup. Successful creation/promotion is audited.

Login: `/login`, normally `http://localhost:5173/login` in development. A verified administrator redirects to `/dashboard/admin`. Ordinary users retain their personal onboarding/dashboard flow. Real MySQL administrator login awaits the developer's chosen credentials and explicit CLI execution.

## Module status

| Module | Status | Evidence/boundary |
| --- | --- | --- |
| Cards3/6 | IMPLEMENTED AND VERIFIED | Exact background and transparent internal stage checked at360/768/1024/1440; no page overflow |
| Secure bootstrap | IMPLEMENTED AND VERIFIED | New creation, verified promotion, rejected overwrite/weak credentials, unchanged existing hash and ownership in isolated tests; CLI help verified |
| Real operator provisioning | BLOCKED | Developer must choose the real email/password and execute the private CLI; no default credentials exist |
| Authentication/authorization | IMPLEMENTED AND VERIFIED | Valid/wrong password, missing/expired/tampered JWT, normal/owner denial, session expiry, logout, suspended admin and forged frontend role rejection |
| Overview/statistics | IMPLEMENTED AND VERIFIED | Actual MySQL read-only reporting queries; five plan/cycle groups covered in isolated tests and browser rendering |
| User Management/search/filters | IMPLEMENTED AND VERIFIED | Name/email/activity/plan/cycle filters, empty state, pagination API and browser suspension/reactivation; sensitive actions audited |
| Subscription Management | IMPLEMENTED AND VERIFIED | Monthly/yearly metadata/filtering, existing-period suspend/reactivate, no invented paid period; API and browser actions |
| Demo Billing | IMPLEMENTED AND VERIFIED | Actual table query, safe metadata/empty state and explicit simulated-revenue labels; no live provider or charge |
| AI Usage | IMPLEMENTED AND VERIFIED | Actual scan/message/failure counts, no private prompt/image exposure |
| Platform Audit Logs | IMPLEMENTED AND VERIFIED | Bootstrap/user/subscription events; metadata only, paginated read view |
| Admin Settings | IMPLEMENTED AND VERIFIED | Existing read-only nonsecret settings preserved; browser error/retry tested; no key/config editor added |

All browser administrative changes used a disposable SQLite fixture. Real MySQL reporting was checked directly in a read-only operator session; it is not evidence of a live authenticated MySQL admin login while no admin exists.

## Verification evidence

- Full backend pytest: **108 passed**,150.10s. Inherited unittest cases contribute to this count; it is not108 distinct scenarios. SQLite forced with `FAMILY_TEST_MYSQL=0`.
- Targeted admin suite: **5 scenarios passed** after bootstrap/reporting fixes; final result retained in `frontend/ui-artifacts/admin-backend-tests.log`. Covers the13 requested security/reporting areas across these scenarios. Final bootstrap row-refresh and legacy-free filter refinements were rechecked with this suite after the full run.
- Frontend: **3 test files passed** (`auth`, advisor normalization and rendered output), targeted ESLint passed. Production build passed,20.51s. Existing main-JS-size warning remains (828.75KB uncompressed /240.39KB gzip).
- Chrome: **PASS** at360/768/1024/1440 for both requested card colors and all7 admin modules. Actual login form validation/wrong password/redirect, search/status/plan filters, user suspend/reactivate, subscription status actions, settings503/retry, idle session expiry, suspended admin, logout and protected/forged-role denial passed. No JS page errors.
- Actual MySQL read-only query check:14 users,14 active users,3 active subscriptions,5 plan/cycle groups,3 subscription records,0 billing rows,1 AI-usage user and1 audit row at inspection time. These are existing database counts, not new beta participants or synthetic production activity.
- Preservation: both `.env` files, entire landing JSX/hero markup and both supplied backups match their protected checksums. No schema migration, real account write, commit, push or deployment occurred.

Two initial admin fixture failures (required transaction date and fixture subscription persistence) were corrected; all final targeted cases passed. An initial frontend command used the repository root instead of `frontend`; rerunning from the correct package directory passed. No unresolved application test failure remains.

Logs and fixture screenshots are stored in ignored `frontend/ui-artifacts/`; they contain isolated test data, not real credentials or financial histories. No fresh live Groq call or payment integration was needed for these two tasks.

## Files changed for these two tasks

- `frontend/src/pages/landingpage/LandingPage.css`
- `backend/scripts/bootstrap_admin.py`
- `backend/app/routers/admin.py`
- `frontend/src/pages/login/LoginPage.jsx`
- `frontend/src/App.jsx`
- `frontend/src/pages/userdashboard/dashboard/Admin.jsx`
- `backend/tests/test_admin.py`
- `frontend/tests/admin_browser.py`
- `ADMIN_SECURITY.md`, this file, and appended task notes in `TEST_REPORT.md` / `MAXBUD_HANDOFF.md`.

The extensive earlier modified/untracked work was preserved. The remaining operational blocker is real operator setup with developer-supplied credentials; no real MySQL admin login or deployment is claimed.
