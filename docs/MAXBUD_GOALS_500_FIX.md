# Savings Goals availability and frontend port fix

## Observed failure and exact error

At inspection, no process listened on port 8000. The existing
`maxbud-backend-local` service had stopped. One managed Vite process, PID 22512,
already listened on `127.0.0.1:5173`; no Vite process listened on 5174.

The reproduced unauthenticated request to `/api/goals` returned HTTP **502**,
rather than the previously reported 500. The matching actual service log was:

```text
[vite] http proxy error: /goals
Error: connect ECONNREFUSED 127.0.0.1:8000
    at TCPConnectWrap.afterConnect [as oncomplete] (node:net:1864:16)
```

There was no FastAPI exception traceback for that request: FastAPI was not
running. The retained backend service log did not contain a goals exception.
After restarting the existing application, authenticated goals requests passed
for all existing active goal owners. No new model/query defect was reproduced;
the earlier collation-independent savings join fix was already present.

## Fix

- Started the stopped local FastAPI service on `127.0.0.1:8000`, using the current
  application and `.env`. No migrations or startup data writes were introduced.
- Configured Vite with `host: "127.0.0.1"`, `port: 5173`, `strictPort: true`.
  The existing frontend stays accessible at `http://localhost:5173`.
- Kept the identified, working frontend service. No unrelated processes were
  killed. A controlled second `npm run dev` exited with status 1 and
  `Error: Port 5173 is already in use`; it did not fall back to 5174.
- Extended the opt-in MySQL regression harness to repeatedly list pre-existing
  goals and compare every saved amount with its stored value, before testing
  isolated new contributions and reversals.

## Schema and preservation checks

Account, Transaction, Goal, GoalContribution and AccountTransfer columns match
the actual MySQL schema. Contribution-to-goal, transfer-to-account and
transaction-to-transfer foreign keys are present. There are no goals with zero
or negative targets. No migration is required for the tested Savings Goals flow.

The database records revision `20261117_access`, which is the feature branch
head. The repository also has an independent `20261104_accounts` root/head that
is not separately stamped in `alembic_version`; its required account/transfer
structures are present. This pre-existing migration-history discrepancy was
left unchanged. No migration was run, reset, merged or stamped.

The real MySQL test used one outer transaction with API savepoints. All new
test records were rolled back. Row-content, row-count and table-definition
fingerprints matched their baseline for all nine touched tables. Existing goals
and contributions were preserved. No existing records were deleted or reset.

## Results

| Check | Result |
| --- | --- |
| Actual schema columns and required foreign keys | PASS |
| Live authenticated goals requests | PASS — 66 HTTP 200 responses: 3 direct and 3 proxied requests for each of 11 active goal owners |
| Existing goals in real MySQL regression | PASS — 11 goals, each read three times with saved amounts preserved |
| Actual MySQL contribution/reversal flow | PASS — debit, goal credit, linked history, retries, real duplicate-key constraints, invalid/foreign/overdrawn submissions, reversal and double-reversal guard |
| Wealth and income/expense classification | PASS — tracked wealth, income, expense, budget and cash-flow totals unchanged by transfers/reversal |
| Failure after real ledger writes | PASS — atomic rollback; no partial debit, goal contribution or transfer |
| Cleanup and existing-data fingerprints | PASS |
| Frontend only on loopback port 5173 | PASS — one Vite process; no listener on 5174 |
| Second Vite launch under strictPort | PASS — expected exit 1; no fallback server |
| Frontend `npm test` | PASS — 7/7 |
| Frontend `npm run lint` | PASS |
| Frontend `npm run build` | PASS — existing large-bundle warning remains |
| Frontend and proxied backend health | PASS — both HTTP 200 |
| `git diff --check` | PASS |

## Files changed in this task

- `frontend/vite.config.js`
- `backend/tests/savings_transfers_mysql.py`
- `docs/MAXBUD_GOALS_500_FIX.md`

No authentication implementation, UI design, Stripe, financial calculations or
database schema was changed. Pre-existing workspace changes were preserved.
Nothing was pushed or deployed.
