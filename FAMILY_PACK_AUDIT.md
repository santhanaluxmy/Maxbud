# MaxBud Family Pack functional and UX audit

**Audit date:** 17 November 2026, Asia/Colombo.  
**Verdict: PARTIALLY ready for a five-roommate real-world test.**

The basic shared-bookkeeping flow works in isolated API/browser tests: one sponsor, invitations, private personal accounts, household wallets, genuine shared income, shared expenses, splits, partial settlements, budgets and goals. However, the intended workflow is not fully implemented. The high-priority shared monthly cash-flow ledger, detailed wallet-funding/settlement histories, consolidated member shares and safe financial correction/reversal controls are missing or incomplete. Real payment purchase is not implemented. Do not treat the shared dashboard totals as a completed monthly cash-flow report.

This is a fresh inspection and execution against the current repository, not a repetition of earlier completion reports. Application code, tests, migrations, private environment files, live MySQL records and subscription settings were not modified. No commit, push, deployment or backup operation was performed. The only repository addition for this audit is this report. Hash comparison confirmed **132 of 132** inspected application/test/configuration files unchanged.

## 1. What the current UX actually does

For the five boys in the boarding-room example, the present flow is:

1. **The payer gets Family Pack access.** The Subscription page offers a Free Trial, Premium Individual and Family Pack. Checkout is explicitly a simulation, not a real purchase. In the inspected private configuration, demo checkout is disabled. A user cannot currently complete a real purchase inside MaxBud.
2. **The payer separately creates the household in Family Management.** Buying/activating a period does not automatically create the household. The person becomes its owner through the household record; this is distinct from being a platform administrator.
3. **The owner invites four roommates** (or up to five additional people). They enter an email and create a secure link, then share it themselves. No email is automatically sent. Pending invitations reserve seats; the owner counts toward the six-person maximum.
4. **Each roommate uses their own login.** The invited email must match the signed-in account. A new user is sent through the existing personal onboarding. The invitation is retained in sessionStorage, but registration/onboarding redirects to onboarding/dashboard rather than automatically back to invitation acceptance. They must find Family Management again and click Accept invitation. This is a discoverability gap, not a demonstrated token-security failure.
5. **Personal sections remain personal.** Accounts, income, transactions, budgets, personal goals/reminders, Advisor and personal reports are under the member's own account. The household owner does not receive permission to inspect those records.
6. **The owner creates shared wallets and category budgets.** Members given shared-entry permission can add common income, shared expenses and shared-goal contributions. Members with view-only permission can read but cannot write. Budget definitions and wallet management remain owner-only.
7. **The household chooses one of two spending workflows:**
   - Put money into a shared wallet, then pay expenses from it. Funding reduces the contributor's personal account and increases the wallet; it is a transfer, not household income. Wallet-funded expenses cannot create personal reimbursement splits. The system does not automatically calculate/enforce who still needs to fund their LKR10,000 monthly contribution.
   - A member pays from their personal account and records a split across selected roommates. MaxBud creates per-expense reimbursement obligations. Debtors settle from their own tracked accounts to the payer's original account. Settlement means a recorded transfer, not merely acknowledging an external cash payment.
8. **Family Management shows shared records; the shared dashboard shows aggregates.** They can see income/expense tables, wallet balances, budget progress, debt totals and goal contribution history. They cannot yet open a full dated shared-wallet ledger or shared monthly running-balance report.

Two separate actions both use the word contribution:

| Action | What happens to money | What it means |
|---|---|---|
| Contribute to shared wallet | Personal account decreases; household wallet increases | Money moved into the common pot |
| Contribute to shared savings goal | No account or wallet money moves | An allocation toward a goal, not a deposit or expense |

Those distinctions are implemented, but the user must understand them. The current UI does not combine wallet funding, budget shares and goal allocations into a single roommate contribution statement.

## 2. Evidence and safe execution

| Evidence | Fresh execution / inspection | Actual result |
|---|---|---|
| E1: existing backend suite | From backend: `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 timeout 180 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` | **84 tests passed, 104.867s.** Covers subscriptions, capacity, invitations, privacy, permissions, wallet transfers, income/expenses, splits, settlement, goals, personal cash flow and admin denial. |
| E2: MySQL read-only inspection | Temporary helper `/tmp/maxbud_family_audit_db.py`: `SELECT 1`, table/column/FK/unique metadata, Alembic revision, OpenAPI paths; read-only transaction and rollback | Connection succeeded; **36 tables**; revision **20261115_beta**. All mapped columns present in all 26 mapped tables inspected, including reminder/payment and Advisor tables. No genuine financial/user row contents queried or reported. Demo-checkout flag read as false; not changed. |
| E3: exact user scenarios | Temporary helper `/tmp/maxbud_family_roommates_probe.py`, using the existing BetaTests SQLite fixture and synthetic accounts | Five-roommate, LKR50,000 splits, partial/full settlement, wallet50,000→42,000, genuine income5,000, budget20,000/12,000/8,000 and goal300+200 scenarios passed. Also directly established report/history and removed-debtor limitations below. |
| E4: original existing browser runner, attempt1 | `PYTHONDONTWRITEBYTECODE=1 timeout 240 .venv/bin/python tests/family_pack_browser.py` | **BLOCKED:** test services did not become ready; Vite logged ECONNREFUSED to temporary API port8793. No successful UI assertion claimed for that attempt. |
| E5: unchanged browser runner, attempt2 | Same existing runner after unit tests finished | **BLOCKED:** `Page.goto` timed out after30000ms waiting for full `load` at `/dashboard/family`. This is a navigation/test-runtime failure, not proof of a failed financial calculation. |
| E6: supplemental browser audit | Temporary wrapper `/tmp/maxbud_family_audit_browser_dom.py` changes only the default Playwright navigation wait to `domcontentloaded`; it calls the same existing runner with all feature assertions unchanged | **PASS, exit0.** Free/Premium gating, demo Family Pack checkout, two-session invite/accept, owner budget/wallet, member income/expense, private salary/account isolation, shared dashboard, permission-save rollback/revocation and downgrade/history checks all passed; no browser JS errors. |
| E7: preservation check | SHA256 comparison before/after execution for132 source/test/config/private-env files | **132 unchanged; zero application/test/config changes.** Private hashes were not printed. |

Before running E1, the fixture was read: `FAMILY_TEST_MYSQL=0` creates an in-memory SQLite database, overrides `get_db`, uses TestClient without the real MySQL lifespan, and patches receipt storage/provider calls in relevant tests. E3 uses that same disposable fixture. Browser tests use a temporary SQLite file, override both API sessions and `/health` engine, and disable external AI/Google. Demo settings are scoped only to the synthetic test process; live settings and `.env` remain unchanged. No MySQL write-mode test, destructive race harness, migration command or live-user login was run.

The supplemental browser runner prepares users and marks personal onboarding complete in its **temporary fixture**. It therefore does not prove that a brand-new invitee can discover and complete registration→onboarding→invitation acceptance unaided. That UX was inspected from source, and remains a separate acceptance gap.

Status vocabulary below follows the requested five classifications. **FULLY IMPLEMENTED AND VERIFIED** refers only to the explicitly scoped behavior tested with isolated data; it never means production or MySQL mutation/concurrency certification. **MySQL yes** means fresh connectivity/schema presence, not live write verification.

## 3. Feature-by-feature assessment

| Feature | Classification | Implemented? | Backend working? | Frontend working? | MySQL connected? | Test evidence | Missing functionality | Relevant files |
|---|---|---|---|---|---|---|---|---|
| Real Family Pack purchase | PARTIALLY IMPLEMENTED | Entitlements and labeled demo checkout | Demo verified; no real gateway | Demo tested; actual flag currently off | Yes: subscriptions/demo_checkouts | E1,E2,E6 | Real payment authorization/webhook/reconciliation; automatic renewal | backend/app/routers/subscriptions.py; backend/app/services/subscriptions.py; frontend/src/pages/userdashboard/dashboard/Upgrade.jsx |
| Family Pack-only shared editing | FULLY IMPLEMENTED AND VERIFIED | Yes, including legacy Free/Premium restrictions | Yes for exercised writes | Locked/unlocked UI verified | Yes: subscriptions/families | E1,E6 | Independent MySQL concurrent downgrade/write verification | backend/app/core/plans.py; services/subscriptions.py; services/household.py |
| Owner household creation | FULLY IMPLEMENTED AND VERIFIED | Explicit create step | Yes | Yes | Yes: families/memberships | E1,E6 | Purchase does not itself create household; guide should explain separate step | backend/app/routers/household.py; frontend/src/pages/userdashboard/family/FamilyPage.jsx |
| Owner plus five additional members | IMPLEMENTED BUT NOT BROWSER VERIFIED | Yes, at most six total; configuration can reduce limit | API test joins all five; seventh denied | Two-user flow verified; six-user UI not exercised | Yes: memberships/invitations | E1,test_family_pack owner_can_grant_exactly_five | Full five-additional-member browser exercise | backend/app/core/plans.py; services/subscriptions.py; routers/household.py |
| Secure invitation issue/accept/expiry/wrong email | FULLY IMPLEMENTED AND VERIFIED | Hashed, email-bound, seven-day tokens; fragment links | Yes for tested cases | Existing-account acceptance works | Yes: family_invitations | E1,E6 | Actual email delivery absent; new-user return flow unclear | backend/app/routers/household.py; frontend/src/App.jsx; FamilyPage.jsx |
| Reject every reused invitation | PARTIALLY IMPLEMENTED | After removal409; active-member retry200 | Safe idempotent replay; differs from literal requested rejection | No duplicate membership observed | Yes | E1,E3 | Decide whether strict rejection or current replay behavior is required | backend/app/routers/household.py respond |
| New invitee signup/onboarding→accept UX | PARTIALLY IMPLEMENTED | Token retained; user must navigate back | Auth/onboarding exist | Full unaided journey not freshly verified | Yes | Source; E6 bypasses onboarding via fixture | Explicit safe return destination or pending-invitation prompt | frontend/src/App.jsx; pages/register/RegisterPage.jsx; pages/onboarding/Onboarding.jsx; family/FamilyPage.jsx |
| Member removal and shared-history preservation | FULLY IMPLEMENTED AND VERIFIED | Membership removed, financial rows retained | Tested; removed token loses scope | Remove control exists; removal not part of E6 | Yes | E1,E3 | Debt-aware removal warning/workflow; no owner transfer | backend/app/routers/family.py; services/family.py; FamilyPage.jsx |
| Independent personal finance/privacy | FULLY IMPLEMENTED AND VERIFIED | Separate owner/member accounts and records | Tested denial/isolation | Private salary/account not shown in shared UI | Yes: personal scope columns | E1,E6 | Not an exhaustive penetration test or real-MySQL write proof | backend/app/services/account.py; routers/transaction.py; budgets.py; goals.py; settings.py |
| Personal Advisor context | IMPLEMENTED BUT NOT BROWSER VERIFIED | Authenticated personal summary/history | Mocked-provider isolation tests pass | Page exists; no real AI call in audit | Yes: advisor_messages | E1 + routers/ai.py source | Fresh authorized provider/browser acceptance, if required | backend/app/routers/ai.py; frontend/src/pages/userdashboard/dashboard/AI.jsx |
| Shared wallet create/rename/archive/balance | FULLY IMPLEMENTED AND VERIFIED | Existing Accounts model with family scope | Exercised | Creation/display exercised | Yes: accounts | E1,E6 | No shared-wallet movement/history screen | backend/app/routers/household.py; services/account.py; HouseholdFinance.jsx |
| Wallet funding and transfer neutrality | IMPLEMENTED BUT NOT BROWSER VERIFIED | Atomic paired entries and replay key | Exact20k+30k−8k API probe passes | Contribute form exists; not exercised by E6 | Yes: account_transfer_records/transactions | E1,E3 | Dated funding history, contributor statements, safe reversal | backend/app/services/household.py fund/move; HouseholdFinance.jsx |
| Who funded the wallet | PARTIALLY IMPLEMENTED | Actor retained; monthly contributor summary | Aggregate available | Shared dashboard monthly sums; no deposit ledger | Yes | E2,E3 + source | Per-wallet dated contributor history with safe source redaction | backend/app/services/household.py household_report; DashboardOverview.jsx |
| Shared expenses: entry/list/payer | FULLY IMPLEMENTED AND VERIFIED | Explicit family_id, source and authenticated actor | Exercised | Add/list exercised | Yes: transactions | E1,E3,E6 | Wallet-funded “Paid by” is recorder, not necessarily owner of the funds | backend/app/routers/household.py; services/household.py; HouseholdFinance.jsx |
| Shared expense update/delete/reversal | NOT IMPLEMENTED | No shared mutation/reversal API | Not available | No controls | Tables exist, workflow absent | OpenAPI + source | Audited correction/reversal that also handles splits/settlements | Same files; models/platform.py; models/finance.py |
| Equal/custom/percentage splits | IMPLEMENTED BUT NOT BROWSER VERIFIED | Decimal cent allocation and validation | Equal five-person probe + existing custom/percentage tests pass | Split-entry controls exist; split table after save missing | Yes: household_expense_shares | E1,E3 | Visible full saved split breakdown, including payer's own share | backend/app/services/household.py split_amounts; HouseholdFinance.jsx |
| Per-member monthly share/amount owed | PARTIALLY IMPLEMENTED | Per-expense shares/debts, not consolidated monthly statement | Aggregate obligations calculable | Debt cards, not a clear “my monthly share/net position” | Yes | E3 | Monthly contribution/share/net debt statement and all-member totals | services/household.py debts/household_report; HouseholdFinance.jsx |
| Partial/full reimbursement | IMPLEMENTED BUT NOT BROWSER VERIFIED | Transfer to original payer; no duplicate expense | Exercised exactly; overpay/replay denied | Settlement form exists, not exercised by E6 | Yes: household_settlements | E1,E3 | Full browser settlement acceptance and explicit cash/offline semantics | services/household.py settle; routers/household.py; HouseholdFinance.jsx |
| Settlement history | PARTIALLY IMPLEMENTED | Records/timestamps stored | API exposes only cumulative settled/remaining | No payment-by-payment history | Yes: settlements.created_at/transfer_id | E2,E3 | Read-only history endpoint/UI with payer, payee, date and amount | models/platform.py; services/household.py debts; routers/household.py |
| Genuine shared income entry/list/report | FULLY IMPLEMENTED AND VERIFIED | Separate from funding/personal salary |5k probe and reporting pass | Add/list/chart verified | Yes: transactions | E1,E3,E6 | Full CRUD is not included in this row | routers/household.py income/income_history; services/household.py; HouseholdFinance.jsx |
| Genuine shared income edit/delete/reverse | NOT IMPLEMENTED | GET/POST only | Not available | No controls | Existing ledger could support approved extension | OpenAPI + source | Auditable corrections, not arbitrary row deletion | Same income/transaction files |
| Shared recurring category budget progress | FULLY IMPLEMENTED AND VERIFIED | Owner create/update/delete; eligible monthly spending |20k/12k/8k seen consistently by five members | Create/progress verified | Yes: budgets/family_scope | E1,E3,E6 | Current limit applies across selected months; no monthly limit versions | routers/household.py; services/household.py; HouseholdFinance.jsx |
| Shared goal contributions/history/archive | IMPLEMENTED BUT NOT BROWSER VERIFIED |300+200 ledger, actor, replay, archive/restore | Exercised; balances/expenses unchanged | Goal/history controls exist; not in E6 | Yes: goals/goal_contributions | E1,E3 | Goal allocation is not a wallet deposit; browser contribution/history journey still needed | routers/goals.py; services/goals.py; FamilyPage.jsx |
| Shared recurring bills/payment | IMPLEMENTED BUT NOT BROWSER VERIFIED | Create/pay/unique due occurrence | Existing bill/replay tests pass | Create/pay controls exist | Yes: payment_reminders/reminder_payments | E1 | Shared bill edit/archive and payment-history UI absent; browser acceptance needed | routers/household.py; routers/reminders.py; HouseholdFinance.jsx |
| Personal monthly cash-flow table | IMPLEMENTED BUT NOT BROWSER VERIFIED | Period rows and running personal-account balance | Current/prior month contract tests pass | Reports table/month selector exists; not exercised in E6 | Yes: accounts/transactions | E1 test_cash_flow + source | Opening-account dates absent; payer implicit “self”; no exact requested single-amount/payer columns | services/cash_flow.py; Dashboard.jsx; CashFlow.jsx |
| Shared household monthly totals | FULLY IMPLEMENTED AND VERIFIED | Selected-month income/expense/funding totals | Current/prior API amounts verified | Current month summary/chart verified | Yes | E1,E3,E6 | Shared UI lacks month selector; current wallet balance is all-time snapshot | services/household.py household_report; DashboardOverview.jsx |
| Shared monthly dated cash-flow/running ledger | NOT IMPLEMENTED | No shared cash_flow payload | include_cash_flow ignored in family branch; recent rows empty | No monthly shared running-balance table | Tables present; feature absent | E3 + dashboard early return | Shared opening/closing balance and date/amount/actor/running rows | routers/dashboard.py; services/household.py; services/cash_flow.py; Dashboard.jsx; CashFlow.jsx |
| Personal/Shared report navigation | PARTIALLY IMPLEMENTED | Personal Reports; separate shared dashboard | Separate scope filters exist | Overview has scope switch; Reports has no equivalent | Yes | Source,E6 shared overview | Carry scope/month into report UI and provide two real reports | DashboardOverview.jsx; Dashboard.jsx; family/FamilyPage.jsx |
| Household activity feed/change attribution | PARTIALLY IMPLEMENTED | Financial actors stored for some records; one household-created platform event | No household activity API | No chronological family activity view | Yes: platform_events + ledger tables | E2 + source | Wallet/budget edits lack modification actor/time; define scoped audit events | models/platform.py; models/finance.py; routers/household.py; FamilyPage.jsx |
| Subscription expiry, revoked permissions, oversized household | FULLY IMPLEMENTED AND VERIFIED | Shared writes denied; history retained | Gates/oversized cases pass | Revocation and downgrade tested | Yes | E1,E6 | In-flight permission/deactivation races need MySQL concurrency test | services/subscriptions.py; services/household.py; services/goals.py |
| MySQL concurrent integrity/release acceptance | BLOCKED | Row locks/unique keys in source/schema | Not executed with concurrent MySQL writes | Not applicable | Read-only connection/schema yes | E2 only | Dedicated isolated MySQL DB/harness, not live maxbud_db | backend/tests/family_mysql_races.py; database.py; relevant services |

The separate income/expense lists return at most100 recent rows and have no pagination parameters. They cannot substitute for a full historical ledger as the household accumulates data.

## 4. Exact roommate examples: what was executed

All amounts and people below are synthetic. This section reports direct API/SQL-fixture verification, not genuine household data or browser actions.

### LKR50,000 split across five people

The owner paid rent25,000 and groceries18,000; roommate B paid electricity5,000 and water2,000. All four expenses selected the same five active participants using equal splits.

| Result | Observed |
|---|---:|
| Household expense total | LKR50,000 |
| Each participant's summed share | LKR10,000 |
| Reimbursement obligation rows excluding payer's own share |16 |
| Gross unsettled reimbursements initially | LKR40,000 |

Gross reimbursement debt is not the same as the expense total or a netted roommate balance. Payers already absorb their own shares. The app represents individual per-expense obligations and does not automatically net reciprocal debts into one monthly amount per person. In this fixture the owner's net position is a credit of33,000; B's net position is a debt of3,000; each of the other three owes10,000. Those net figures can be derived from the obligations but are not a dedicated current UI statement.

For one roommate's LKR5,000 rent obligation, paying2,000 left3,000; repeating that request did not create another settlement; paying3,000 left0. Stored settlement rows=2. Household expense total stayed50,000. The reimbursement API returned share/expense IDs, debtor/creditor, agreed amount, cumulative settled and remaining, but no dates or individual settlement history.

### Wallet, genuine income, budget and goal

- Two members funded a wallet20,000 and30,000: balance50,000. An8,000 wallet expense left42,000. Funding counted as0 genuine income.
- Common equipment rental income5,000 then raised the wallet to47,000 and genuine household income to5,000. It was not a private salary or a transfer.
- A separate budget category limit20,000 with expense12,000 showed remaining8,000 for all five authorized members.
- Refrigerator allocations300 and200, each replayed once, produced saved500, exactly two contribution-history entries and two contributors. Neither wallet balance nor expense total changed.

These are staged checkpoints in one synthetic household; later probe entries intentionally change its totals. They must not be mistaken for a single unchanged final household balance.

### Previous-month report limitation

The probe added previous-month shared income10,000 and expense1,000, then requested `scope=family&year=2026&month=10&include_cash_flow=true`.

Observed: monthly income10,000 and expenses1,000 were correctly filtered. Nevertheless, `cash_flow` was absent, `recent_transactions` was empty, and both previous-month and current-month `total_balance` returned44,000—the same current/all-time wallet snapshot. A previous-month cash-flow closing balance of9,000 was not provided. The current snapshot is not inherently wrong when labeled as current balance; it simply does not meet the requested period running-balance report.

### Removing someone with unpaid debt

A roommate still owed5,000 across other obligations. Removal returned200; their attempt to settle afterward returned404 because membership was gone. Their personal account remained accessible200, and the household retained the historical debt.

This preserves history/privacy but can strand an unsettled member. The UI offers ordinary removal without a debt-resolution warning/guard, and there is no authorized former-member settlement or reassignment workflow. Settle before removal until that policy is designed.

### Invitation replay

The already accepted link, replayed by its still-active intended member, returned200 idempotent success. It did not add another membership. Reuse after removal is rejected409 by source/existing tests. Wrong email and expired pending links are rejected. The accepted-member replay branch precedes the expiry check, so an already accepted link is treated as an idempotent replay rather than as a new expired invitation. This differs from the attachment's literal rule that every reused token must be rejected; it is not evidence that arbitrary users can reuse the token.

## 5. Accounting and privacy findings

**Working evidence:** money validation/persistence uses Decimal/Numeric, transfers have paired entries, account balances derive from non-deleted ledger rows, shared queries use family_id and current membership, and personal ownership checks do not grant owners a cross-user bypass. The exercised tests deny foreign private accounts, foreign household wallets, revoked/removed members, unauthorized contributions and non-owner budget creation. Platform admin role is separately checked and admin projections do not expose private finance. The personal Advisor uses the authenticated user's personal summaries/goals/reminders/history, not pooled household salaries.

**Report bases are intentionally different in one important respect:** personal dashboard expense totals exclude explicitly shared expenses, but the personal account cash-flow table includes a shared expense the person actually paid from their own account. That is a real movement of their money and is marked `shared_payment`; it is not a cross-user leak. Shared-wallet movements are excluded from that personal account table. Therefore personal dashboard totals and personal-account cash movement need a clear reconciliation, not forced equality across different bases.

**Personal running-balance basis:** recorded opening balances of all personal accounts, including archived accounts, plus earlier movements, then chronological entries. Accounts have no opening-date field, so the report cannot reconstruct true opening-date history that was never recorded. Shared running-balance basis is absent entirely.

**No fresh privacy exploit was demonstrated.** Passing isolated tests does not certify every endpoint or concurrent MySQL access. InnoDB lock behavior, rollback after connection failure, duplicate concurrent posting and downgrade/removal during in-flight writes still require a dedicated disposable MySQL environment. No genuine data consistency/row reconciliation was attempted in this audit.

## 6. UX assessment

The broad division—personal navigation versus Family Management/shared overview—is understandable. Shared income/expense tables identify an actor, owners can see invitations and permission toggles, and plan/error/loading states exist. E6 exercised these controls successfully with prepared users.

The complete boarding-room workflow is **not yet easy to understand without guidance**:

- Purchase/access, household creation, invitation creation, external link sharing, personal onboarding and final acceptance are separate steps; no complete new-member onboarding checklist or automatic return-to-invitation is shown.
- A roommate must choose between funding a shared wallet and paying personally with splits. The app does not connect a wallet-funded boarding budget to monthly amounts still owed by each person.
- Saved expense shares are returned by the API but not rendered as a full participant breakdown. Reimbursement cards omit the payer's own share and do not consolidate one person's total monthly obligation.
- Wallet funding can be seen as monthly member sums on the shared overview, but not as a dated per-wallet deposit history. Settlements show cumulative values, not a receipt-like list of payments.
- The shared “Paid by” column names the recorder for a wallet expense, while Source says Household wallet. This should distinguish recorder from actual funding source more explicitly.
- Reports navigation leads to personal reports; the family link opens a shared overview, not the requested shared monthly cash-flow table.
- Different contributions—wallet funding and goal allocation—have different money effects. Existing explanatory text helps, but the household needs a simple contribution/share/settlement statement.
- There is no supported way to correct a mistaken shared income/expense or reverse a settlement through the UI. Generic personal mutation routes deliberately cannot edit shared rows.

This is a workflow/control inspection and automated interaction assessment, not a measured usability study with five real roommates or an accessibility certification.

## 7. Prioritized minimal changes (recommendations only)

### P0 — Financial correctness and privacy

| Gap | Exact relevant files | Recommended minimal change / acceptance |
|---|---|---|
| Safe shared financial corrections | backend/app/routers/household.py; backend/app/services/household.py; backend/app/models/platform.py; frontend/src/pages/userdashboard/family/HouseholdFinance.jsx | Add explicit authorized, idempotent reversal/correction actions preserving original rows. Reverse paired money movements and related shares/settlements atomically; recheck available balances and actor permissions. Never fix genuine records with ad hoc deletion. Test income, expense, funding, full/partial settlement correction and conflicting retries. |
| Actual-engine concurrency confidence | backend/tests/family_mysql_races.py; backend/tests/test_family_pack.py; backend/app/services/household.py; backend/app/services/subscriptions.py | Review/replace the isolated race harness and provision a separate disposable MySQL DB. Verify simultaneous funding/spends/settlements/goal final cents/invitations, plus revoke/downgrade during writes. Do not point a create/drop/reset harness at maxbud_db. |
| Preserve privacy in every new ledger/history API | backend/app/routers/household.py; backend/app/services/household.py; backend/app/services/cash_flow.py | Query explicit family scope plus current membership/permissions. Whitelist shared wallet names and actor fields; do not serialize members' private source account names, balances, salary notes or unrelated transactions. Add cross-user/family/removed-member tests before exposing history. |

### P1 — Missing essential household functions

| Gap | Exact relevant files | Recommended minimal change / acceptance |
|---|---|---|
| Shared monthly cash-flow report (high-priority requirement) | backend/app/routers/dashboard.py; backend/app/services/household.py; backend/app/services/cash_flow.py; frontend/src/pages/userdashboard/dashboard/Dashboard.jsx; frontend/src/pages/userdashboard/dashboard/CashFlow.jsx | Implement a separate household-wallet ledger payload with selected year/month, opening/closing wallet balance and dated rows: description/type/amount/actor/running balance. Keep wallet funding and reimbursements as movement types, not genuine income/expense. Identify personally paid shared expenses separately so they do not falsely reduce wallet running balance. Verify prior-month close and all-time/current snapshots separately. |
| Wallet-funding and settlement histories | backend/app/routers/household.py; backend/app/services/household.py; backend/app/models/finance.py; backend/app/models/platform.py; frontend/src/pages/userdashboard/family/HouseholdFinance.jsx | Expose paginated, household-scoped movement/contribution and settlement reads using existing transfer/settlement actor/date fields. Show date, member, amount, recipient, original expense and remaining balance. Add history/replay/removed-member privacy tests. |
| Roommate share/contribution statement | backend/app/services/household.py; backend/app/routers/household.py; frontend/src/pages/userdashboard/family/HouseholdFinance.jsx | Render existing expense shares including payer's own share. Add selected-month per-person total paid, agreed share, wallet funding, settled, still owed/owed to them, and optional clearly labeled net position. Do not infer that wallet funding creates a debt or that it settles a personal IOU. |
| Debt-aware removal/leave | backend/app/routers/family.py; backend/app/routers/household.py; backend/app/services/household.py; frontend/src/pages/userdashboard/family/FamilyPage.jsx | Detect outstanding shares before removal/leave; show exact unpaid totals and require an approved settlement/closure policy. Preserve history. Test removal of a debtor and creditor; do not restore full shared access merely to permit settlement. |
| Shared activity/provenance | backend/app/models/platform.py; backend/app/routers/household.py; backend/app/routers/goals.py; frontend/src/pages/userdashboard/family/FamilyPage.jsx | Write household-scoped, whitelisted actor/timestamp events in the same transaction as create/change/reverse actions, then expose `/family/activity` or equivalent. Existing PlatformEvent is not a ready shared feed. Any new indexed schema field would need a separately approved additive migration. |
| Real subscription access for a real paid pilot | backend/app/routers/subscriptions.py; backend/app/services/subscriptions.py; frontend/src/pages/userdashboard/dashboard/Upgrade.jsx | Either explicitly authorize a controlled demo/access trial or implement an approved provider-backed purchase with verified payment events before access activation. Current disabled demo and absent real gateway do not provide a real purchase journey. No subscription setting should be silently changed. |

### P2 — Reports and usability improvements

| Gap | Exact relevant files | Recommended minimal change / acceptance |
|---|---|---|
| Personal/Shared report switch and period navigation | frontend/src/pages/userdashboard/dashboard/Dashboard.jsx; DashboardOverview.jsx; CashFlow.jsx; frontend/src/pages/userdashboard/family/FamilyPage.jsx | Add an explicit report scope switch/separate report destinations, preserve selected month, and label current wallet snapshots versus period closing balances. Do not route “shared report” to personal data. |
| Invitation return path | frontend/src/App.jsx; frontend/src/pages/register/RegisterPage.jsx; frontend/src/pages/login/LoginPage.jsx; frontend/src/pages/onboarding/Onboarding.jsx; frontend/src/pages/userdashboard/family/FamilyPage.jsx | Retain a safe internal return path or show an invitation banner after login/onboarding. Test the whole unauthenticated invitee journey without a prepared session; never send tokens in access-log query parameters. |
| Contribution/payer language | frontend/src/pages/userdashboard/family/HouseholdFinance.jsx; FamilyPage.jsx; frontend/src/pages/userdashboard/dashboard/DashboardOverview.jsx | Distinguish wallet deposit, goal allocation, member-paid expense, wallet-paid expense and reimbursement. Show “Recorded by” separately for wallet payments and explain why personal account and shared expense summaries have different bases. |
| History pagination and search | backend/app/routers/household.py; frontend/src/pages/userdashboard/family/HouseholdFinance.jsx | Add validated pagination/date/wallet/category filters; current income/expense endpoints truncate to100 rows. Verify older records remain discoverable. |
| Historical budget limits and period views | backend/app/models/finance.py; backend/app/services/household.py; backend/app/routers/household.py; frontend/src/pages/userdashboard/family/HouseholdFinance.jsx | Define recurring versus month-specific budgets. Preserve versions if historical limits must remain unchanged; do not silently repurpose legacy monthly_budgets rows or apply a migration during this audit. |
| Invitation replay requirement | backend/app/routers/household.py; backend/tests/test_beta.py; backend/tests/test_family_pack.py | Decide whether active-member replay should remain idempotent200 or become explicit409. Preserve no-duplicate membership and post-removal rejection in either policy. |

No recommended fix above was implemented.

## 8. Direct answers to the ten questions

1. **Can one payer invite five additional members?** Yes, with an active Family Pack, subject to a maximum of six total users and reserved invitation slots. Six-person capacity is API-tested; the fresh browser journey uses owner plus one member.
2. **Can everyone maintain private personal finances?** Yes for the exercised own-account flows. The owner cannot read their private accounts; individual account/history records survive removal or sponsor expiry. Personal editing still follows their own/sponsored entitlement rules.
3. **Can everyone manage permitted shared household finances?** Yes for current supported operations. Owners manage wallets/budget definitions/membership; authorized members add common income/expenses and goal contributions. Corrections, some histories and full shared reports are missing.
4. **Can all members see who contributed and who spent?** Partially. Expense/income actors, goal contributors and monthly wallet-funding summaries exist. Complete dated wallet-deposit and reimbursement histories and a per-person monthly share statement do not.
5. **Are shared income, expenses and wallets calculated correctly?** The requested numerical scenarios passed in disposable SQLite. Funding/reimbursements were not added as new household income/expenses. This is not a full concurrent MySQL financial certification.
6. **Are personal and household cash-flow reports completely separate?** Their financial scopes are separated, but the household cash-flow report itself is incomplete: only aggregates exist, not a dated monthly running-balance ledger. The personal account report deliberately includes a shared expense personally paid from that user's account, clearly marked as such.
7. **Does the UI make the workflow easy to understand?** Partially. Basic entry/navigation works; invitation continuation, two funding workflows, full shares, settlement history and report navigation need clearer guidance and controls.
8. **Which functions are partial?** Real purchase, new-invitee continuation, full income/expense CRUD, funding/settlement histories, monthly per-person shares, activity feed, shared cash flow, historical budget limits and removal with debt.
9. **Which endpoints/controls are missing?** Shared monthly cash-flow/movement history; detailed settlement history; household activity; authorized shared corrections/reversals; their UI screens/scope/month navigation. Current API exposes `/family/income` GET/POST and `/family/expenses` GET/POST only, `/family/reimbursements` cumulative GET plus per-share settle POST, and no household activity or cash-flow endpoint/payload.
10. **What must be fixed before successful five-roommate use?** At minimum: agree a controlled access/payment mode; deliver the shared monthly ledger and visible contribution/share/settlement statements; handle mistaken entries and removal with debt safely; guide new invitees back to acceptance; and verify financial/permission races in isolated MySQL. A supervised synthetic walkthrough can happen now, but current functionality should not be presented as the completed intended system.

## Final readiness decision

**Is MaxBud Family Pack ready for a five-roommate real-world test? PARTIALLY.**

It is suitable for a supervised, explicitly non-production walkthrough of existing bookkeeping features. It is not yet ready to be the roommates' sole trusted real-world household ledger under all of the requested requirements. The principal reasons are missing shared monthly cash-flow/history and correction workflows, the demonstrated debt-removal trap, no real purchase flow, and unverified MySQL concurrency. Basic arithmetic/privacy tests and a supplemental two-user browser journey passed; those successes do not erase the missing requirements.
