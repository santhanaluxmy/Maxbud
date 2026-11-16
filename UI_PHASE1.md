# MaxBud UI phase — 13 November 2026

## 1. Landing page

The approved hero JSX, images, copy, animations and CTA layout were preserved.
Its existing cream transition was retained. Only feature/section CSS changed:
six cards now use 3 desktop columns, 2 tablet columns and 1 mobile column,
20px copy padding, 18px gaps, smaller visuals and a 260px minimum height.
Sections/footer below the hero use Soft Cream. Content, links, Pricing and FAQ
were retained. The FAQ test respects the existing initially-open first item.

## 2. Dashboard design

Existing dashboard styles now provide shared cream surfaces, lighter glass cards,
consistent spacing/buttons/forms, bounded responsive tables and charts, smaller
empty states and readable headings. Safe to Spend is the first highlighted aqua
metric. Real backend budget progress and upcoming bills appear in Overview.
Financial calculations were not changed by the UI phase; Phase 2 subsequently
adds shared savings allocations under its separate authorization.

The layout uses hierarchy, alignment, responsive spacing, keyboard focus and
restrained motion, drawing on [Apple's design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles/)
and [Material foundations](https://m3.material.io/foundations/), while retaining
MaxBud's existing brand and typography. This is not an accessibility certification.

## 3. Sidebar

The same navigation component now groups Overview, Money Management, Smart Tools,
Household and Account. Subscription links to the existing `/dashboard/upgrade`
route. Labels/icons are consistent, with no duplicate sidebar links. Active states,
desktop collapse, mobile drawer focus trapping, Escape/close behavior and body-scroll
locking are retained/refined. Mobile targets have at least 44px heights. Moving an
open mobile drawer to a desktop viewport closes it and releases scroll locking.

## 4. Advisor

The existing `AI.jsx` and endpoints are reused. The advisor has a MaxBud chat header,
real remaining-message allowance, ordered history with separate user/assistant
bubbles, suggested questions that only populate the composer, a bottom composer,
Send/Enter behavior, loading state and provider-error feedback. No AI answers or
financial data were fabricated. Receipt controls remain in the same dashboard shell.

## 5. Subscription

The existing Upgrade component now displays Free LKR 0, monthly Premium LKR 990,
yearly Premium LKR 10,000, and the proposed three-month introductory trial. Prices
and trial duration live in `frontend/src/config/subscription.js`. They are provisional
marketing configuration, not billing configuration. Current plan and usage come from
`/ai/usage`, with loading/error/retry states. Eligibility, activation and checkout are
explicitly unavailable; no trial or payment is falsely shown as active. No billing
backend or payment gateway was changed.

## 6. UI phase files

- `frontend/src/pages/landingpage/LandingPage.css`
- `frontend/src/pages/userdashboard/layout/navigation.js`
- `frontend/src/pages/userdashboard/layout/DashboardLayout.jsx`
- `frontend/src/pages/userdashboard/layout/DashboardPremium.css`
- `frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx`
- `frontend/src/pages/userdashboard/dashboard/DashboardOverview.css`
- `frontend/src/pages/userdashboard/dashboard/AI.jsx`
- `frontend/src/pages/userdashboard/dashboard/Upgrade.jsx`
- `frontend/src/pages/userdashboard/dashboard/Reminders.jsx`
- `frontend/src/pages/userdashboard/dashboard/Settings.jsx`
- `frontend/src/pages/userdashboard/dashboard/Notifications.jsx`
- `frontend/src/config/subscription.js` (new)
- `frontend/tests/ui_browser.py` (new)
- `frontend/.gitignore` (local screenshot artifacts)
- `UI_PHASE1.md` (this report)

Phase 2 family-specific changes are documented separately in `FAMILY_MANAGEMENT.md`.

## 7. Actual checks

- Production build: passed; existing main-bundle warning remains.
- Targeted ESLint for changed JSX/config/navigation: passed.
- Frontend auth regression tests: 5 passed outside the sandbox. Sandbox Node reports
  only the file wrapper; the individual cases were verified outside it.
- Chrome sweep: all 12 user dashboard pages passed at 360px, 768px, 1280px and
  1600px, with no viewport overflow or page errors. Landing grid columns and FAQ,
  sidebar collapse/mobile links, overview order, subscription prices/current plan,
  and advisor suggestions/send/error state passed.
- The first FAQ assertion failed because it assumed the first FAQ started closed;
  the test was corrected to verify the existing state toggles both ways. No FAQ
  functionality was changed to satisfy the test.
- The UI harness disables rate limiting only on its isolated test server for the
  high-volume page sweep. Application rate limiting is unchanged.
- Hash checks confirm Auth router, Login, Register and Onboarding source unchanged,
  and the approved hero CSS block byte-for-byte unchanged.
- Python compilation and Git whitespace checks passed. No `.env` edits, purchases,
  new gateway, commits or pushes.

Screenshots are local, ignored review artifacts under `frontend/ui-artifacts/`:
`landing-desktop.png`, `landing-360.png`, `overview-desktop.png`,
`advisor-desktop.png`, `advisor-360.png`, and `subscription-desktop.png`.

## 8. Remaining issues

Live AI/Google provider setup, trial eligibility, billing activation and deployment
remain as described in the integration handoff; UI styling does not activate them.
Browser checks cover important flows and responsive layouts, not every device,
keyboard/screen-reader combination or real provider response. The final responsive sweep also passed after the mobile touch-target refinements,
including a check that resizing an open mobile drawer to desktop releases body
scroll locking.
