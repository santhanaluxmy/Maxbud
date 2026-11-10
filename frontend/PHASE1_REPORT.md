# Phase 1 frontend refactor

Completed Phase 1 only. No backend, database, environment, credentials, or dependency changes.

Backup retained at `frontend/src_backup_phase1_20261106_120718/`. Earlier `src_backup_phase1/` is also untouched.

## Files moved (relative to frontend/src)

| Original | Destination |
| --- | --- |
| pages/LandingPage.jsx | pages/landingpage/LandingPage.jsx |
| pages/LoginPage.jsx | pages/login/LoginPage.jsx |
| pages/RegisterPage.jsx | pages/register/RegisterPage.jsx |
| pages/OnboardingPage.jsx | pages/onboarding/Onboarding.jsx |
| pages/onboarding.css | pages/onboarding/Onboarding.css |
| pages/UserDashboard.jsx | pages/userdashboard/dashboard/Dashboard.jsx |
| pages/dashboard.css | pages/userdashboard/dashboard/Dashboard.css |
| components/GoogleAuthButton.jsx | components/auth/GoogleAuthButton.jsx |

Moved JSX imports were adjusted to their new locations. The original combined dashboard content and API behavior remain together for the later page extraction phases; the shell and navigation have been extracted, with no duplicate legacy dashboard file left in live source.

## Files created

- `src/pages/landingpage/LandingPage.css`
- `src/pages/login/LoginPage.css`
- `src/pages/register/RegisterPage.css`
- `src/pages/userdashboard/layout/DashboardLayout.jsx`
- `src/pages/userdashboard/layout/DashboardLayout.css`
- `src/pages/userdashboard/layout/navigation.js`
- `src/components/common/GlassCard.jsx`
- `src/components/common/Modal.jsx`
- `src/components/common/Loading.jsx`
- `src/components/common/EmptyState.jsx`
- `src/styles/variables.css`
- `src/styles/animations.css`
- `src/styles/auth.css`
- `src/styles/controls.css`
- `PHASE1_REPORT.md`

Shared authentication CSS avoids duplicating identical login/register rules. Common components reuse the existing dashboard markup and styles. No empty page or API modules were added.

## Files changed

- `src/App.jsx`: updated page imports; nested protected dashboard routes with one layout and Outlet.
- `src/index.css`: base styles only, importing tokens, animations and shared controls. Landing rules are scoped to `.landing-page`; auth rules retain their existing prefixes and layout. Removed the font-face request for the absent `/fonts/Vescura.woff2`; existing fallback typography remains.
- Moved page JSX: updated relative imports and local CSS imports.
- `Dashboard.jsx`: URL-driven sections, shared components, and account response compatibility (`items`, `current_balance`, with legacy array fallback). Existing transaction saves/deletes still refresh summary, transactions and accounts. Reports continue using backend aggregate fields, not transaction-page totals.
- `DashboardLayout.jsx`: extracted existing sidebar/topbar; active route links, desktop collapse, original mobile drawer, profile and logout. Reminders has an explicit unavailable state; existing planned feature states remain.
- Moved dashboard CSS: separated shell styles from content and preserved media rules.
- Moved GoogleAuthButton: initialize missing-configuration error in state initializer to satisfy the existing hooks lint rule. Active login/register Google OAuth flows are unchanged.
- `eslint.config.js`: exclude retained source backups from lint targets.

## Verification

- `npm run build`: passed (Vite production build).
- `npm run lint`: passed, zero errors/warnings.
- Additional local server rendering: `/`, `/login`, `/register`, and all 11 dashboard URLs render. Each authenticated dashboard route has exactly one sidebar and dashboard main content. Unauthenticated and incomplete-onboarding gates prevent dashboard content from rendering. This checks renderability and route matching, not browser interaction or redirect completion.
- Static reference audit: all 48 relative imports resolve, including JSX, CSS and imported image assets.
- Existing tablet/mobile media rules were retained and separated with their owning styles. Browser visual comparison, drawer interaction, browser back/forward, and viewport overflow still require manual checks.
- `npm test`: failed before executing assertions: Node cannot resolve extensionless `../services/authApi` from `src/api/auth.js`. The existing suite also expects an older `/api` form-encoded login contract and omitted registration confirmation; the actual FastAPI auth router accepts JSON and the frontend sends confirmation. Auth code and tests were left unchanged rather than changing the working contract during a structural migration.
- No live authenticated FastAPI requests, financial writes, or Google sign-in were tested. No data was created or removed for verification. The route rendering check used an in-memory synthetic session only; it did not contact FastAPI.

## Remaining dependencies and later phases

- Phase 2: extract Accounts and Transactions views, state and API modules; add transaction search, server pagination and richer validation/states. The preserved transaction list currently loads at most 100 rows.
- Phase 3: extract Budgets, Savings Goals and Reports; add report date filters and safe CSV export using complete backend data.
- Existing dashboard mutation calls `POST /budgets`, `POST /goals`, and `POST /goals/{id}/contribute` have no matching routes in the mounted backend routers. Onboarding-only routes exist and must not be reused as dashboard CRUD. These existing forms remain, and requests will show their API error until compatible backend endpoints are approved.
- Minimal backend proposal for later approval: authenticated, owner-scoped budget creation using category/monthly_limit; goal creation using name/target_amount/saved_amount/optional target_date; goal contribution by owned goal ID using amount and decimal validation. Reuse current models without schema migrations. No such backend changes were made.
- No reminders API exists. AI scan, advisor and family remain explicitly planned/unavailable.
- No dedicated reports endpoint exists; current `/dashboard` provides real monthly totals, category spending and six-month trends. Future arbitrary date-range reporting can use the existing transaction date filters and paginate to exhaustion, or an approved aggregate endpoint.
- Phase 4: final brand/style review and real browser responsive testing. Existing logo and finance images, hero background, FAQ and pricing cards remain; the removed comparison table has not been reintroduced.

## Commands to run

From the project root:

```bash
cd /home/uki-jaffna/Documents/MaxBud/frontend
npm run build
npm run lint
npm run dev -- --host 127.0.0.1
```

Open the URL printed by Vite (normally `http://127.0.0.1:5173`). Use your existing configured FastAPI server on port 8000. If it is not running, start it in a separate terminal using your existing environment:

```bash
cd /home/uki-jaffna/Documents/MaxBud/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check landing sections/FAQ, registration, login, Google login, all five onboarding steps, logout, direct dashboard URLs, refresh, browser back/forward, transaction create/edit/delete, and desktop/mobile navigation with a test account. Financial writes in this checklist are manual user tests and were not executed by this refactor.

To reproduce the existing test-suite issue:

```bash
cd /home/uki-jaffna/Documents/MaxBud/frontend
npm test
```
