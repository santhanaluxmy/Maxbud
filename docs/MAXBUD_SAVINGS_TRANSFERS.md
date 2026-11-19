# Savings goal contribution accounting

Personal goal contributions now require an active, owned source account in the
user's currency and a stable submission key. The source debit, goal contribution,
linked transfer and its two ledger entries commit together. Invalid amounts,
insufficient funds, archived/shared/foreign accounts, target overruns and reused
keys with different details are rejected.

The existing Account, AccountTransfer, Transaction and GoalContribution tables
are reused. No model changes, migration, backfill or new table is required.

## Accounting and historical records

- A protected `goal_savings` reserve account is created on the first new funded
  contribution, with zero opening balance. It is archived/nonspendable so normal
  account forms and spending APIs cannot access it. Existing account totals
  already include archived assets, preserving tracked net worth.
- Each contribution creates matching `transfer_out` / `transfer_in` entries.
  Existing income, expense, budget and cash-flow calculations remain unchanged.
- `AccountTransfer.client_request_id = goal:<contribution ID>` links the existing
  contribution and transfer records. Ordinary transfer requests accept UUIDs,
  keeping this namespace reserved. Existing unique constraints enforce one link.
- Existing saved amounts and old contribution rows remain untouched and are
  reported separately as `legacy_allocated_amount`. Only explicitly linked new
  transfers count toward `account_backed_amount`. No historical account debit is
  inferred. The existing “already saved” field remains a prior allocation when
  creating a goal; funded saved amounts subsequently use the transfer ledger.
- Reversals append a compensating transfer with a unique
  `goal-reversal:<contribution ID>` key, restore the source balance, reduce the goal
  and mark the contribution reversed in one commit. Original rows and dates are
  retained. Double reversals are rejected; replaying the original contribution
  after reversal never debits again. Refunds to archived source accounts work.
- Existing user/goal locks, account locks, current locking reads and unique
  submission keys protect concurrent requests. A goal with transfer history
  cannot have its saved amount overwritten through the edit form/API.

## UI and API

- Existing Add to Savings Goal modal: required Transfer From Account selector
  with eligible balances, pending-state controls and stable retry key.
- Existing Transactions page: Transfers filter, searchable savings history with
  date, source account, destination goal, currency/amount and reversal status.
- `POST /goals/{id}/contribute`: existing amount/request_id plus required personal
  `account_id`. Existing shared-goal behavior is retained.
- `GET /goals/transfers?limit=100&offset=0`: owned personal transfer history.
- `POST /goals/{id}/contributions/{contribution_id}/reverse`: atomic reversal.

## Verification

| Check | Result |
| --- | --- |
| New isolated savings API tests | PASS — 10/10 |
| Existing finance and family regressions | PASS — 35/35 |
| Combined backend run after MySQL fix | PASS — 45/45 |
| Actual configured MySQL schema integration | PASS — API transfer, duplicate protection, reversal, totals, failed-write rollback and cleanup |
| Production React + FastAPI browser flow | PASS — required eligible account/balances, rapid duplicate submits, history/search/reversal, lost-response retry, mobile layout and no JavaScript errors |
| Frontend `npm test` | PASS — 7/7 |
| Frontend `npm run lint` | PASS |
| Frontend `npm run build` | PASS — bundle-size warning remains |
| `git diff --check` | PASS |

The stale family test expectations are corrected: one owner plus four members
fills the five-person family, and removing the only member leaves four slots.
The inactive-member test still proves inactive members retain their seat and
cannot contribute. Both family tests now pass. The actual membership limit and
family implementation were not changed.

Tests use disposable SQLite, including the production session's disabled
autoflush setting in the browser harness. They verify balances, totals, history,
reversals, permissions, retry conflicts, direct linked-entry edit/delete guards,
source balance corrections and rollback after ledger writes/failed commits.
The frontend/browser results above are from the initial feature verification;
no frontend files changed in the MySQL verification follow-up.

## Real MySQL verification follow-up

Run from `backend`:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/savings_transfers_mysql.py --run
```

This uses the actual configured MySQL database and schema, without cloning,
creating or migrating tables. It checks InnoDB engines and absence of triggers,
creates UUID-named test users, and runs authenticated FastAPI requests against a
session bound to a single outer transaction. API commits release savepoints;
cleanup rolls back the outer transaction. An independent connection confirmed
the test users were never visible outside it. Sequential retries and real MySQL
unique constraints were tested; concurrent independent write races were not.

The initial MySQL run exposed error 1267 in the savings contribution-link join:
`account_transfer_records.client_request_id` uses `utf8mb4_unicode_ci`, while
`CAST(goal_contributions.id AS CHAR)` inherited the connection's
`utf8mb4_0900_ai_ci`. A read-only query with a nonexistent goal reproduced it.
The fix compares the ASCII link keys as binary values using SQLAlchemy casts.
No column collations, schema definitions or stored values were changed. Both
MySQL and SQLite suites pass with this fix.

The MySQL integration verified:

- Opening account 1,000 + income 50 - expense 20 = 1,030 available.
- A 125.50 contribution leaves source 904.50, goal 250.50 including its unchanged
  prior allocation of 125, and account-backed savings of 125.50.
- Linked debit/credit ledger entries and dated source/goal history are present.
- Retries, conflicting submission keys, underlying duplicate inserts,
  nonpositive amounts, insufficient funds and foreign accounts are handled.
- Reversal restores source to 1,030 and goal to its prior allocation of 125;
  double reversal is rejected and replaying the original request cannot debit.
- Tracked wealth stays 1,030 throughout; income stays 50 and expense stays 20.
  Budget spending and combined cash-flow totals also remain unchanged.
- An injected failure after real ledger writes leaves no partial financial data.
- All test records are rolled back. Row counts, row-content fingerprints and
  table-definition fingerprints match the baseline for all nine touched tables.
  Normal InnoDB auto-increment gaps from rolled-back inserts are not reset.

No existing MySQL records, credentials or financial data were modified. No push
or deployment was performed.

Files changed in this verification follow-up:

- `backend/app/services/personal_savings.py` — collation-independent key join.
- `backend/tests/savings_transfers_mysql.py` — opt-in rollback-isolated MySQL test.
- `backend/tests/test_family.py` — four available member slots after removal.
- `backend/tests/test_shared_family.py` — owner plus four members at capacity.
- `docs/MAXBUD_SAVINGS_TRANSFERS.md` — updated verification report.

## Files changed for this feature

- `backend/app/routers/goals.py`
- `backend/app/services/account.py`
- `backend/app/services/cash_flow.py` (report wording only)
- `backend/app/services/personal_savings.py` (new)
- `backend/tests/test_core_finance_flow.py`
- `backend/tests/test_features.py`
- `backend/tests/test_savings_transfers.py` (new)
- `backend/tests/savings_transfers_browser.py` (new)
- `backend/tests/savings_transfers_mysql.py` (new)
- `backend/tests/test_family.py` (capacity expectations only)
- `backend/tests/test_shared_family.py` (capacity expectations only)
- `frontend/src/pages/userdashboard/dashboard/Dashboard.jsx`
- `frontend/src/pages/userdashboard/dashboard/SavingsTransfers.jsx` (new)
- `docs/MAXBUD_SAVINGS_TRANSFERS.md` (this report)

Pre-existing workspace changes from other tasks were preserved.
