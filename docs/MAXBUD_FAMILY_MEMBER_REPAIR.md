# Family member navigation and action repair

## Current behavior

Personal accounts, income/transactions, budgets, goals and reports remain in their existing `/dashboard/...` routes. The sidebar identifies these as **Personal Finance**. No personal ledger or backend financial calculation was replaced.

Family Management is now the shared workspace entry point. Its task links and section navigation lead directly to:

| Route | Purpose | Member actions |
|---|---|---|
| `/dashboard/family` | Household summary and task chooser | Choose a shared task; see available access |
| `/dashboard/family/wallets` | Shared wallets | Contribute from the signed-in user's own account |
| `/dashboard/family/income` | Common earnings/history | Record income into a shared wallet |
| `/dashboard/family/expenses` | Common costs and expense splitting | Pay from own funds or a shared wallet; split personal-funded costs |
| `/dashboard/family/budgets` | Household category limits/spending | Read limits, spent and remaining; owner manages definitions |
| `/dashboard/family/goals` | Common savings allocations/history | Contribute to an active goal; read contributor identity/history |
| `/dashboard/family/reimbursements` | Split obligations | Record partial/full repayment of own debts |
| `/dashboard/family/reports` | Shared totals, member summaries and trends | Read permitted household reports |
| `/dashboard/family/bills` | Common bills | Pay assigned shared-wallet bill occurrences |
| `/dashboard/family/members` | Membership, invitations and permissions | Read own membership or leave; administration stays owner-only |

The shared dashboard's **Manage goals** and **View Shared Budget** links target the corresponding routes. Each route survives refresh. Unknown shared sections show a recovery link rather than silently opening an unrelated screen.

Wallet rename/archive, budget edit/delete and goal edit/archive remain available to owners under expandable management details. Joining instructions are shown only when joining is relevant. Members are not shown owner administration controls. View-only and missing-access states explain the restriction; backend authorization remains authoritative. Expense splitting requires selected participants and a personal payment account. Reimbursements identify the expense and cap the input at its remaining debt.

Data fetching is limited to the selected task. A failure in an unrelated shared feature no longer blocks a member's wallet/expense screen. Save failures remain visible in the dialog; failed reads have retry controls. Financial submissions retain request IDs and prevent repeated concurrent submissions.

## Browser verification

`backend/tests/family_member_browser.py` uses the existing marked `backend/.local-family-test` database and the designated owner and Roommate 2. It refuses missing/inactive/unonboarded accounts or an inactive household entitlement. It uses separate browser contexts and short-lived session fixtures signed with the sandbox key, so no password, real subscription or auth database row needs changing. This verifies authenticated financial actions, not password login.

The test starts loopback FastAPI 8796 and Vite 5186 against this same isolated database. Normal rate limits remain enabled; browser requests are paced. New QA accounts/wallets/goals/budget/expenses/bill/settlements have a unique printed `UX QA ...` prefix. It edits/deletes only definitions created in that run, preserves their financial history and restores Roommate 2's original permissions in a `finally` block. All pre-existing rows in ten financial tables are compared before/after. It never resets, deletes or clones the existing database.

```bash
cd backend
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/family_member_browser.py
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

The browser asserts responses, refresh persistence, contributor identity, balances and forbidden actions. It exercises member 200 + owner 300 goal allocations, owner/member wallet contributions, shared income, personally funded equal splitting, a member wallet-funded expense, partial/full reimbursements, owner definition management, shared bill payment, reports, personal account isolation and permission revocation. Expected report deltas: shared income +700, expenses +470, wallet funding +1500 and wallet balance +2030. Settlements and goal allocations must not inflate income/expenses.

Logs: `/tmp/maxbud-member-acceptance.log`, `/tmp/maxbud-member-services.log`, `/tmp/maxbud-member-backend-tests.log`. Browser screenshots: `/tmp/maxbud-member-after-owner.png`, `/tmp/maxbud-member-after-member.png`. These are local test artifacts, not deployments.

### Results observed

- Owner and Roommate 2 browser navigation passed for all four task links, including the shared dashboard's Manage goals link and refresh persistence.
- Goal flow passed: Roommate 2 allocated 200, owner allocated 300, both saw 500 with correct identity/history, private balances stayed unchanged, and owner target editing/archive/restore worked.
- The remaining finance run (`--finance-only`, QA prefix `UX QA a6290fbb`) exited 0. Wallet funding/rename/archive/restore, both users' income entry, shared expense/split entry, budget creation/update/read/delete, partial/full repayment, household bill payment, reports and permission/privacy denial checks passed. All ten pre-existing financial table snapshots matched afterward. Roommate 2's original permissions were restored.
- The browser uses session fixtures; no password-login verification is claimed by this repair.
- Frontend lint, four Node test files and production build passed; the existing bundle-size warning remains.
- The broad backend run logged 83 passed cases before its 300-second timeout in the local-access group. A later full rerun was interrupted. Full regression completion is not claimed; successful browser operations also assert real backend responses and persisted reads.
- Removal/leave of existing memberships was deliberately not browser-executed against this persistent household. Existing backend removal checks passed in the broad run.

## Remaining boundaries

- Detailed dated shared cash-flow/running-balance ledger is not available; the reports screen explicitly says so.
- Wallet funding and reimbursement events lack separate dated history screens. Goal contribution history is available.
- Shared income/expense correction/reversal is not implemented.
- Invitation email delivery and automatic invitation return after onboarding remain separate gaps.
- Existing membership removal/leave safeguards are retained. The repair test does not remove the user's existing Roommate 2 membership or pre-existing household; backend regressions cover removal and retained history.
- No Stripe, production changes, MySQL data mutation, schema migration, commit, push or deployment is included.
