# Family Pack: shared income, expenses and budgets

16 November 2026. Implements the user's requirement that only Family Pack enables shared household financial management, with one primary owner and up to five other people. This supersedes historical Free/Premium family-sharing limits in earlier handoff/audit documents.

## Subscription behavior

| Subscription | Personal income, expenses and accounts | Shared household editing |
|---|---|---|
| Free / existing personal trial | Existing personal-plan rules remain | Not included |
| Premium (including legacy Premium and Premium Individual) | Personal Premium tools | Not included |
| Active Family Pack | Owner's personal tools; invited members retain their separate accounts/subscriptions | Owner plus up to five invited people |

The existing personal trial duration and billing lifecycle are unchanged. Internal plan identifiers remain compatible with the existing API; no real subscription is activated by a frontend flag. Existing demo checkout is clearly labeled, disabled by default and prohibited in production. No real gateway or charges were added.

The server enforces the same plan requirement for household creation, invitations/acceptance, wallets, income, expenses, budgets, bill payments and shared goal writes. Legacy Free/Premium subscriptions no longer bypass Family Pack restrictions. A current locking subscription read is used for shared writes after the household lock. Concurrent MySQL behavior still needs an isolated multi-connection test; no race-free production claim is made.

The capacity is at most six total users, including the owner. Existing server configuration may reduce this limit but cannot increase it past six. Pending invitations reserve slots. Inactive members retain their slot until the owner removes their membership. Owners cannot remove themselves. An oversized historical household is not deleted: shared writes are paused until the owner reduces active memberships to the allowed capacity, while history and membership management remain available.

## User flow

1. Open **Family Management**. Free/Premium users see the Family Pack route rather than shared editing controls.
2. Obtain a server-authorized active Family Pack. In an explicitly enabled test/demo environment, use the existing labeled demo checkout; no money is charged.
3. Create the household. An existing legacy household becomes eligible when its owner's valid Family Pack is recognized; its history is retained.
4. Invite up to five people by email and privately share the generated link. The app does not send email automatically or choose their passwords.
5. Invitees register/sign in to their own accounts and accept their email-bound invitation. The owner can grant view-only or shared-entry permissions and revoke them later.
6. The owner creates household wallets and category budgets. Authorized members record common income in those wallets, or record shared expenses using a household wallet/their own personal payment account.
7. Personal sections show each person's private financial records. Family Management and the shared dashboard show only explicitly shared records.

Members do not need their own Family Pack to join a sponsored household. Their own subscription is not overwritten or canceled. When the sponsor expires/downgrades/is suspended, new shared edits and invitations stop; authorized shared history remains readable. Members' personal account records are preserved and their own personal-plan entitlement continues independently. Removed members lose household access but retain their personal accounts and records.

## Shared income and financial accounting

New `POST /family/income` and `GET /family/income` endpoints reuse the existing transactions, accounts and transaction_requests tables. No table or migration is needed.

A shared income request includes a household wallet account_id, category, positive Decimal amount, date, shared description and stable request_id. The wallet must belong to the same household, be active and use LKR. The authenticated user is the contributor/recorder; a caller cannot forge another user_id. Shared income is credited once to the wallet. Reusing its key with conflicting details returns 409. Foreign/private wallets and unauthorized writes are rejected. The entire income/request record commits together or rolls back.

Common earnings are distinct from transferring personal money into a shared wallet. Example:

| Event | Household wallet balance | Shared income | Shared expense | Personal effect |
|---|---:|---:|---:|---|
| Owner funds wallet 100 | 100 | 0 | 0 | Owner's private account decreases 100; transfer |
| Common income 300 | 400 | 300 | 0 | No private account is credited |
| Shared expense 80 | 320 | 300 | 80 | Wallet decreases 80; personal accounts unchanged |

For this example shared income minus expenses is 220, wallet funding is 100 and wallet net movement is 320. Funding and reimbursements are transfers, never a second income/expense. Shared expenses paid from a member's personal account still affect that account balance and the explicit shared ledger, not another member's private ledger.

Household reports now expose actual shared monthly income, expenses, income-minus-expenses, wallet balance, wallet funding and wallet net movement. Six-month income charts and per-member shared totals use the same explicit family scope. Shared category budget spending includes eligible shared expenses, never unrelated private spending. Personal salaries, private account names/balances, personal budgets and notes are not pooled or disclosed to other members.

The new income listing exposes shared facts and the authenticated recorder's name, not private account identifiers. Existing shared transaction correction/reversal workflows are not expanded in this phase; shared records remain append-only through the exposed entry APIs.

## UI and permissions

- Family Management shows the household's shared income/expenses/net/wallet summary, a shared-income form/history, wallets, budgets, expenses, bills, reimbursements and shared goals using the existing pastel/glass design.
- Shared income can only select a household wallet. Expense/split flows retain their existing explicit funding-account choices.
- The shared dashboard's income card/chart now show genuine common income. Personal wallet contributions are displayed separately as transfers.
- Owners define shared budget limits and manage wallets/invitations. Members with shared-entry permission can add common income/expenses and participate in shared goals. View-only members can read shared reports but cannot add records.
- Permission toggles update immediately, retain the server as authority, and roll back visually when a save fails. Revoked permissions are rechecked by the backend.
- Subscription/capacity warnings disable shared editing while preserving history. No real subscription was enabled in the user's private environment for these tests.

## Files reused/changed

| Files | Purpose |
|---|---|
| backend/app/core/plans.py | Free/Premium have zero household seats; Family Pack capped at six. |
| backend/app/services/subscriptions.py | Family Pack-only writes, current subscription read, capacity check, no legacy Premium sponsorship, no inactive-household sponsorship. |
| backend/app/services/family.py | Updated overview, capacity/edit eligibility and membership messaging. |
| backend/app/services/goals.py; routers/goals.py | Remove legacy permission bypasses from shared goals. |
| backend/app/routers/household.py; services/household.py | Shared income APIs/service, scoped Decimal ledger/replay, report aggregation. |
| frontend/src/pages/userdashboard/family/FamilyPage.jsx | Plan/capacity messaging, owner/member controls and permission-save rollback. |
| frontend/src/pages/userdashboard/family/HouseholdFinance.jsx | Shared summary, income entry/history and permission-aware controls. |
| frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx; Upgrade.jsx | Actual shared income charts/totals and owner-plus-five plan description. |
| backend/tests/test_family_pack.py (new) | Ten subscription/capacity/income/privacy/permission/history acceptance cases. |
| backend/tests/family_pack_browser.py (new) | Two-session browser journey with isolated demo billing, invitation, shared ledger and revocation/downgrade checks. |
| backend/tests/test_family.py; test_shared_family.py; test_core_finance_flow.py; test_beta.py | Adapt prior legacy-sharing fixtures/expectations to the newly required Family Pack contract while retaining privacy/financial regressions. |
| README.md; this document | Current contract and verification. |

Existing uncommitted authentication work was preserved. Private environment files, genuine subscriptions, memberships, financial records and database schema were not modified by testing. No dependency installation, migration, real payment, production deployment or commit was performed.

## Verification and reproduction

From backend:

```bash
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/family_pack_browser.py
```

The browser test starts temporary FastAPI 8793/Vite 5183, uses an isolated SQLite file and two separate authenticated browser contexts, and disables external AI/Google. Demo billing is enabled only inside that synthetic test process. Actual payment configuration and subscriptions are unchanged. Test services stop afterward.

From frontend:

```bash
npm run lint
npm test
npm run build
```

Actual results so far:

- The first nine new Family Pack acceptance cases passed in 5.402s; the initial full suite with those cases passed 83 tests.
- The final browser journey **passed (exit 0)**: Free/Premium block household creation, Family Pack demo checkout permits it, owner invite/member acceptance works, common income 1000 and expense 200 produce wallet 800 and budget spending 200, private salary 3000 remains personal, permission failure rolls back, revocation blocks a member's writes, downgrade preserves readable shared history and personal account balance 3500, and no browser JavaScript errors occurred.
- Lint and the final production build passed. The build retains the existing large-bundle warning (~835kB JS). Node tests passed all four frontend test files.
- The oversized-household case initially failed because its synthetic memberships were not committed between fixture registrations. The fixture was corrected to persist each membership and explicitly verify seven users before testing the limit; no production logic was relaxed.

Final full-suite result: **84 backend tests passed in 37.926s (exit 0)**. The Family Pack browser runner exited 0; lint, four frontend test files, production build and `git diff --check` passed. All temporary browser/API test services stopped afterward.

## Remaining boundaries

- Financial write/permission/browser tests use disposable SQLite. Real MySQL connectivity was already verified read-only in the core-flow phase; no genuine MySQL mutation or isolated MySQL concurrency test is claimed here.
- No real payment gateway, automatic invitation email delivery or background subscription renewal was added. Keep existing demo labels and production guards.
- Personal trial expiry, password recovery, JWT revocation after password changes and unrelated advanced features remain their existing separate roadmap work.
