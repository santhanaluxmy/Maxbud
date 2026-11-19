# Family Management: five-person capacity and full-width pages

Only Family Management, its capacity configuration, and related tests/fixtures were updated in this task. Existing working-tree changes were preserved.

## Completed

- Family Pack now defaults to and is capped at five people: one owner and four members. An older `FAMILY_PACK_MEMBER_LIMIT=6` setting cannot raise the enforced limit above five.
- Existing invitation creation and acceptance both use that central capacity. Pending invitations continue reserving seats. Available slots remain total capacity minus active memberships (including the owner) minus unexpired pending invitations, bounded at zero.
- Updated family counts, capacity labels and invitation/access copy. Existing memberships and invitation records are not migrated, deleted or automatically revoked. Older oversized households retain history and the existing over-capacity controls.
- Removed the entire inner sidebar and its CSS. Family content occupies the full available application workspace.
- Kept all ten existing overview navigation cards and their destinations. Every family subpage has a “Family Overview” return link.
- Main application sidebar source and styles are byte-for-byte unchanged from the start of this task. No unrelated application pages, Stripe code, financial calculations, database schemas or genuine MySQL data were changed.

## Changed application files

- `backend/app/core/config.py` — default Family Pack capacity.
- `backend/app/core/plans.py` — enforce the five-person cap, including older environment overrides.
- `backend/app/services/subscriptions.py` — family over-capacity message only; payment and entitlement calculations are unchanged.
- `frontend/src/pages/userdashboard/family/FamilyPage.jsx` — remove inner navigation, add overview return links, update capacity display.
- `frontend/src/pages/userdashboard/family/FamilyPage.css` — remove sidebar styles and use the full content width.
- `frontend/src/pages/userdashboard/family/FamilyInvitations.jsx` — capacity copy from the family API.
- `frontend/src/pages/userdashboard/family/HouseholdFinance.jsx` — five-person shared-access copy.

## Changed tests and fixtures

- `backend/tests/test_family_invitations.py` — four invitees, pending reservations, blocked sixth acceptance, preserved legacy invitations, replay protection and released reservations.
- `backend/tests/test_family_pack.py` — five-person contract and preservation of oversized legacy memberships.
- `backend/tests/test_family.py` — family limit expectation.
- `backend/tests/test_beta.py` — family pending-reservation expectations only.
- `backend/scripts/local_family_test.py` — new isolated fixtures use one owner and four members; existing sandbox databases are not changed.
- `backend/tests/test_local_family_access.py` — matching fixture counts and family sponsorship expectations.
- `backend/tests/local_family_browser.py` — matching fixture descriptions.
- `backend/tests/ui_polish_browser.py` — expect the removed inner sidebar to be absent.
- `backend/tests/family_capacity_browser.py` — new family-only browser coverage.
- `docs/MAXBUD_FAMILY_CAPACITY_UPDATE.md` — this report.

## Verification

- Frontend lint: passed.
- Frontend tests: all seven test files passed.
- Production build: passed; the existing Vite warning for a JavaScript chunk over 500 kB remains.
- Selected backend family tests: all 25 passed. Covered capacity, reservations, invitation acceptance/replay/revocation/expiry, legacy pending links, oversized households, permissions, preserved records and local family fixtures. SQLite was isolated and external provider credentials were disabled.
- Browser integration: passed against the production React build and real local FastAPI endpoints with temporary SQLite. Clicked every one of the ten overview cards and returned from each page at 1440, 768 and 390 pixels. Verified full-width content, no inner sidebar and no horizontal page overflow.
- Browser membership test: passed with an intentional legacy environment setting of six. One owner plus four members joined; counts were five total and zero available slots, the invite button was disabled, and the backend rejected a sixth invitation. All four existing invitation records remained present.
- Browser JavaScript error collection was empty. Screenshots: `/tmp/maxbud-family-review/`.
- `git diff --check`: passed.

No push or deployment was performed.
