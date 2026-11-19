# MaxBud UI polish

Implemented the eight requested UI areas. Existing working-tree authentication and invitation changes were preserved. No push or deployment was performed.

## Completed

- Landing: preserved the hero; added keyboard focus and hover treatment to feature cards and their arrow links, removed the pricing demo disclaimer, and organized the footer into compact feature lists. Actual checkout disclosures remain unchanged.
- Authentication: reused the Login piggy-bank asset on Register, consolidated logo proportions, added field-specific validation with stable accessible names, and placed general errors above the submit button.
- Onboarding: four visible steps (About you, Accounts, Budgets, Goals). New setups skip income; legacy persisted step IDs and the old income endpoint remain compatible. The budget page includes an interactive spending-limit example and live opening-balance/allocation/difference guidance. Resuming the budget page reloads opening balances from the account API. Budgets do not alter account balances.
- Dashboard: narrowed the desktop sidebar, aligned and resized the original logo, and replaced the global search form with the current page title.
- Personal finance: removed repeated page descriptions, metric footnotes and bottom informational notes. Kept validation, errors, over-budget guidance, essential financial cautions and existing CRUD operations.
- Advisor: a page-level conversation with document scrolling and a bottom composer, retaining message history, loading states, usage limits and the existing API.
- Family: grouped section navigation, clearer household context, task cards, member and invitation presentation, and responsive content layouts. Existing actions, permissions and routes remain in place.
- Receipt review: searchable merchant suggestions, an explicit new-merchant option, currency selection defaulting missing extraction currency to LKR, existing categories, editable extracted fields, and guarded confirmation. Changing currency clears the account selection. Scanning does not create a transaction; confirmation retains backend idempotency.

Only two backend application files changed: the accounts onboarding endpoint accepts the skipped-income path, and a read-only authenticated endpoint supplies the current user's saved merchant rules. No models, migrations, authentication logic, billing logic or financial calculations were changed for this task.

## Files changed for this task

Paths below are relative to the repository root. Other changes already present in the working tree are excluded.

| Area | Files |
| --- | --- |
| Landing | `frontend/src/pages/landingpage/LandingPage.jsx`, `frontend/src/pages/landingpage/LandingPage.css` |
| Authentication | `frontend/src/pages/login/LoginPage.jsx`, `frontend/src/pages/login/LoginPage.css`, `frontend/src/pages/register/RegisterPage.jsx`, `frontend/src/pages/register/RegisterPage.css`, `frontend/src/styles/auth.css` |
| Onboarding | `frontend/src/pages/onboarding/Onboarding.jsx`, `frontend/src/pages/onboarding/Onboarding.css`, `frontend/src/pages/onboarding/onboardingUi.js`, `backend/app/routers/onboarding.py` |
| Dashboard layout | `frontend/src/pages/userdashboard/layout/DashboardLayout.jsx`, `frontend/src/pages/userdashboard/layout/DashboardLayout.css` |
| Personal finance | `frontend/src/pages/userdashboard/dashboard/Dashboard.jsx`, `frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx`, `frontend/src/pages/userdashboard/dashboard/CashFlow.jsx`, `frontend/src/pages/userdashboard/dashboard/Reminders.jsx`, `frontend/src/pages/userdashboard/transaction/Transaction.jsx` |
| Advisor and scanner | `frontend/src/pages/userdashboard/dashboard/AI.jsx`, `frontend/src/pages/userdashboard/dashboard/MerchantSelector.jsx`, `frontend/src/pages/userdashboard/dashboard/TargetedModules.css`, `backend/app/routers/ai.py` |
| Family | `frontend/src/pages/userdashboard/family/FamilyPage.jsx`, `frontend/src/pages/userdashboard/family/FamilyPage.css` |
| Tests | `frontend/tests/onboarding-ui.test.mjs`, `backend/tests/test_ui_polish.py`, `backend/tests/ui_polish_browser.py` |
| Report | `docs/MAXBUD_UI_POLISH_REPORT.md` |

## Verification

- Frontend lint: passed.
- Frontend tests: passed (seven test files, including the new onboarding UI tests).
- Production build: passed. Vite reports a JavaScript chunk over 500 kB; code splitting is outside this UI request.
- Browser integration: passed using the production React build, real local FastAPI endpoints, temporary SQLite, synthetic accounts and mocked AI. Checked field validation/error placement, matching auth illustrations and logo dimensions, all four onboarding steps, budget explanation, over/under allocation, refresh/resume, unchanged balances after budgeting, merchant selection/new merchants, LKR fallback, category selection, currency/account reset, one confirmation request after a double click, advisor send/history reload, every family route, shared wallet creation/funding, shared budgets, shared goals and invitations.
- Responsive checks: passed at desktop 1440×1000 and mobile 390×844, including receipt review and family management. Browser JavaScript error collection was empty. Screenshots are available in `/tmp/maxbud-ui-review/`.
- Targeted backend integration tests: all three passed, covering the skipped-income path, compatibility with existing saved income, unchanged balances, private merchant suggestions, no transaction before confirmation, rejected invalid review and idempotent confirmation.
- Broader backend regression: 93 tests passed without a reported failure before the 180-second limit interrupted an existing local-family CLI test. This broad run is incomplete; the focused UI integration and browser suites passed separately. External provider credentials were disabled for this run.
- Landing hero JSX and onboarding first-step fields: verified unchanged against the starting tracked version.
- `git diff --check`: passed.

All test financial data is isolated from genuine MySQL records. Live AI, Google, SMTP and Stripe providers were not exercised. Actual checkout disclosure and subscription code were not edited.

## Remaining issues and limits

- The existing Vite bundle-size warning remains. No bundling or unrelated architecture changes were added.
- The full backend suite did not finish within its time limit. Its log is `/tmp/maxbud-ui-regression.log`; focused tests and complete browser checks cover the requested onboarding and scanner flows.
- Live third-party provider responses are outside these isolated checks.
