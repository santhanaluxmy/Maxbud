# MaxBud targeted UI polish — 16 November 2026

This work preserves the existing React/FastAPI architecture, hero, navigation, financial operations, schema, Groq integration and subscriptions. No migrations or live financial writes are required. No recording was found in the project; the changes follow the supplied written issues.

## Changes

- Landing feature visuals are existing HTML/CSS illustrations, not six replacement images. A bounded stage fits the full artwork inside the unchanged card dimensions. Cards3/6 receive subtle aqua contrast and clearer borders. Subsequent sections use the approved cream; hero markup/styles remain unchanged.
- Login logo is centered in its original form card. The square transparent asset is positioned inside a fixed brand window without stretching or replacing it. Sidebar uses the same alignment treatment, including collapsed/mobile modes.
- Overview illustration stays within the welcome area below the navbar. Navbar horizontal padding follows content gutters and its cream surface/border connects to the workspace. Menus and navigation remain unchanged.
- Account/goal Edit and Archive actions get compact scoped controls, consistent spacing and hover/focus treatment. Budgets and Reminders are not redesigned.
- Transactions summary uses existing authenticated `/dashboard` values plus an additive `active_tracked_balance` field. Balance includes opening balances and recorded signed movements, excludes archived accounts, and is explicitly separate from personal monthly income minus expenses. Loading placeholders, empty/error messaging and retry are included.
- Reports opt into `GET /dashboard?year=...&month=...&include_cash_flow=true`. No new endpoint or database write. The table sorts date thenID, carries earlier movements forward, includes archived personal accounts for history, and includes personally paid shared expenses. Combined opening balances are the stored account opening balances plus prior dated movements; account opening dates are not recorded in the existing schema, which is explicitly disclosed. Transfers/funding/reimbursements affect running balances but not income/expense columns. Goal allocations have no account movement. Household wallets and other users' records stay excluded. Existing personal-scope metrics/charts retain their policy, so the table explains personally paid shared costs separately.
- Advisor presentation unwraps recognized JSON replies, safely renders paragraphs/headings/lists/emphasis, converts Markdown tables to readable points, formats LKR amounts and wraps multilingual text. Malformed unknown structures get a readable retry explanation. No HTML injection/rendering, new dependency, financial-context rewrite or quota/history change.
- Household invitations use the existing secure link; recipients no longer copy/type technical tokens. Owner sees a copy-link action and honest manual-delivery wording. Existing email match, expiry, permissions and acceptance remain server-enforced. Short setup wording explains Family Pack→household→invite→shared planning.

## Admin setup

A read-only count found **zero active platform admin accounts**. No real account was elevated or reset. Register an operator normally using their chosen password, then use the existing bootstrap from `backend`:

```bash
PYTHONPATH=. .venv/bin/python scripts/bootstrap_admin.py --email YOUR_EXISTING_OPERATOR_EMAIL
```

This previews only. After verifying the exact account, the developer may deliberately repeat with `--apply`. The action is audited. There is no public admin registration or default password. Household ownership does not grant platform-admin access.

## Safety and verification

Current task tests force temporary SQLite and isolated browser fixtures. Live MySQL is used only for read-only revision/admin/hash checks. `.env` and existing backups are preserved. No commit, push or deployment is performed. Final test counts, browser outcomes and any remaining limitations are recorded below after actual completion.

## Final verification results

- Backend: **93 pytest cases passed**, 231.68s, on temporary SQLite (`FAMILY_TEST_MYSQL=0`). This includes inherited unittest cases; it is not93 distinct scenarios. Both new cash-flow scenarios separately passed. Coverage includes opening/brought-forward balances, active versus archived balances, chronological transfers, personally paid shared expenses, reimbursements, deleted/future entries, allocations, empty months, authorization and cross-user privacy. Existing subscription/family/admin/AI regressions passed.
- Frontend: **3 test files passed** (`auth`, advisor normalization, advisor rendered markup). The rendered-component test checks headings/lists, Tamil, LKR formatting, JSON unwrapping, table-to-list presentation, malformed-response fallback and escaping malicious HTML. These are not browser tests.
- Targeted ESLint: passed on the affected JSX/helper files. Production build: passed,7.26s. Existing large-bundle warning remains (main JS826.27KB /239.80KB gzip).
- Static preservation: original landing CSS remains an unchanged prefix; landing JSX differs only by the feature-visual wrapper. Hero layout/text/illustrations/animations/background are unchanged. `.env` preservation passed a hash comparison earlier in this task, with no subsequent environment-file edits. Both supplied backups match their original checksums. The temporary environment-hash snapshot was unavailable after interruption, so a second final environment checksum comparison could not be repeated. No migration, live MySQL write, commit, push or deployment was performed.
- Browser: **not completed**. The first new responsive harness timed out while starting its temporary servers. Subsequent reruns were interrupted before completed results. No current360/768/1024/1440 visual pass is claimed, and old November15 screenshots/results are not evidence for these new changes. `frontend/tests/polish_browser.py` retains all four viewport checks, report fixtures/month switching, logo/illustration geometry, advisor formatting and admin navigation for a future authorized run. All fixtures are temporary SQLite.
- Fresh live Groq/browser scanner and demo-checkout verification was not completed in this polishing session. Existing mocked receipt/subscription regressions passed; their earlier live November15 results remain historical. Groq/context/quota/scanner business logic was not rewritten.
- Initial lint caught a synchronous effect-state update; fixed with request-path-aware loading state. No unresolved unit/integration/lint/build failure remains. Browser startup/interruptions remain verification blockers.

## Requested-item status

| Item | Final classification |
| --- | --- |
| Landing images/contrast/cream, preserved hero | FIXED BUT NOT BROWSER VERIFIED; source preservation verified |
| Login logo | FIXED BUT NOT BROWSER VERIFIED |
| Overview image/navbar/sidebar logo | FIXED BUT NOT BROWSER VERIFIED |
| Account action buttons | FIXED BUT NOT BROWSER VERIFIED |
| Transactions summary | FIXED BUT NOT BROWSER VERIFIED; real-data backend calculations verified |
| Goal action buttons | FIXED BUT NOT BROWSER VERIFIED |
| Monthly cash-flow report | FIXED BUT NOT BROWSER VERIFIED; financial/authorization tests passed |
| Advisor response formatting | FIXED BUT NOT BROWSER VERIFIED; normalization and actual React rendered-markup tests passed |
| Household invitation wording/link acceptance | FIXED BUT NOT BROWSER VERIFIED; existing backend security regressions passed |
| Subscriptions / receipt scanner / Budgets / Reminders | ALREADY WORKING; automated regression coverage passed; fresh live browser/Groq checks incomplete |
| Admin authorization | ALREADY WORKING; API regressions passed |
| Real admin login | BLOCKED until developer provisions an operator; zero active admins, no credentials altered |
| Tests and source checks | FIXED AND VERIFIED for pytest/frontend tests/lint/build/hero and protected files; responsive browser verification BLOCKED |

## Files in this polishing change

Backend: `app/routers/dashboard.py`, new `app/services/cash_flow.py`, new `tests/test_cash_flow.py`.

Frontend: `pages/landingpage/LandingPage.{jsx,css}`, `pages/login/LoginPage.{jsx,css}`, `pages/userdashboard/dashboard/Dashboard.jsx`, `DashboardOverview.css`, `AI.jsx`, new `CashFlow.jsx`, `AdvisorMessage.jsx`, `advisorText.js`; `pages/userdashboard/layout/DashboardPremium.css`; `pages/userdashboard/family/FamilyPage.jsx`; new `tests/advisor.test.mjs`, `tests/advisor-render.test.mjs`, `tests/polish_browser.py`.

Documentation: this `UI_POLISH.md` and appended entries in `TEST_REPORT.md` / `MAXBUD_HANDOFF.md`. The working tree contains extensive earlier approved changes; they were preserved and should be reviewed separately when committing.
