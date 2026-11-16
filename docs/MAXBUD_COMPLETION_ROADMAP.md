# MaxBud completion roadmap and implementation sequence

16 November 2026. This is a proposed implementation plan. No implementation begins until the user explicitly says **START IMPLEMENTATION**. Obtain the actual PRD before approving missing advanced scope; repository documents are secondary requirements. Preserve all genuine records, current visuals and uncommitted changes. Reuse React JSX/FastAPI/SQLAlchemy/MySQL and current endpoint names. New files below are proposals, not created application files.

## Exact recommended first implementation task

**P0-01: Make personal savings contributions retry-safe.** This is a narrow reproduced defect: submit amount `10.00` with the same request_id twice to one personal goal; the current saved amount becomes `20.00`. Reuse the current shared-contribution ledger pattern without rewriting historic saved amounts or subtracting account money. Define backwards compatibility for keyless callers, use a stable key per form submission, reject conflicting key reuse, and verify one increment on sequential/concurrent retries. Inspect legacy goal_contributions foreign keys before deciding whether to extend its current_goal_id ledger or use the existing request mechanism. No migration or historic balance backfill should occur automatically.

First approved phase: add failing regression cases; implement server replay/locking and stable frontend key; run targeted finance/API/Node checks plus production build; review the diff and evidence; report actual results before moving on. This task does not depend on a real AI/payment provider. Run concurrency proof only in a dedicated disposable MySQL database; never repurpose the existing financial database.

## Phase order and dependency gates

1. Establish a reproducible isolated test baseline; align the PRD when available. Begin P0-01 (personal contribution retries).
2. P0-02 linked financial correction/reversal policy, P0-03 balance correction rules, P0-04 schema contract alignment and P0-05 session invalidation. Keep each change independently reviewable.
3. P0-06 isolated MySQL concurrency and startup/schema gates; no core release until financial invariants and authorization pass on the intended engine.
4. P1 core forms, budgets, dashboards and report reconciliation; add missing browser mutation/validation coverage using temporary data.
5. P1 password recovery if required; review notification and profile/export requirements.
6. P2 AI validation/merchant memory; then household collaboration and plans/admin, reusing their substantial existing implementations.
7. Implement dedicated AI planner/predictions only after the PRD defines them. Keep checkout labeled demo unless real gateway work is explicitly approved.
8. P3 design/accessibility/performance, reproducible deployment, documentation and final evidence-based acceptance.

Every phase report must list files changed and why, run instructions, expected and actual test outcomes, remaining issues and data/migration risks. Never label a module COMPLETE from source presence or a smoke page alone.

## P0-01 — Personal contribution idempotency

- **Reuse:** backend/app/routers/goals.py; models/finance.py; services/goals.py; frontend/src/pages/userdashboard/dashboard/Dashboard.jsx; backend/tests/test_features.py.
- **Proposed new files:** backend/tests/test_personal_goal_retries.py; migration only if required after schema review.
- **API requirements:** Keep POST /goals/{goal_id}/contribute; stable request_id, same payload replay, conflicting payload 409, ownership/plan checks.
- **Database changes:** Prefer current_goal_id contribution ledger and existing unique user/request; preserve initial saved_amount without a historic backfill. Review compatibility before choosing storage..
- **Dependencies:** None; reuse isolated test fixture.
- **Testing:** Same key twice => saved 10 not 20; conflicting amount/goal =>409; unauthorized =>404/403; completed-goal replay; failure retry; isolated MySQL parallel final-cent case.
- **Acceptance criteria:** Exactly one allocation, one attributable request record, no account debit/expense, historic saved totals unchanged.
- **Risk:** High: financial allocations/legacy ledger.

## P0-02 — Linked payment/receipt correction and reversal

- **Reuse:** routers/transaction.py; routers/reminders.py; routers/ai.py; models/reminder.py; models/ai.py; models/finance.py.
- **Proposed new files:** backend/tests/test_linked_financial_corrections.py; explicit reversal service only if approved.
- **API requirements:** Keep transaction routes; protect linked edits/deletes or introduce an explicit reversal action with documented response and UI feedback.
- **Database changes:** Prefer no schema change for protected mutations; reviewed additive reversal fields/migration if chosen. Never remove original payment/receipt records..
- **Dependencies:** P0-01 baseline; approve correction semantics.
- **Testing:** Pay then delete/edit expense; confirm receipt then delete/edit; recurrence replay after reversal; unauthorized linked IDs; injected failure between stages.
- **Acceptance criteria:** A payment/receipt never claims a valid expense that is absent/replaced without an auditable atomic correction.
- **Risk:** High: multi-record financial history.

## P0-03 — Consistent resulting account balance on corrections

- **Reuse:** routers/transaction.py; routers/account.py; services/account.py; schemas/account.py; Dashboard.jsx.
- **Proposed new files:** backend/tests/test_balance_corrections.py.
- **API requirements:** Define policy for income deletion/reduction/move, kind change and opening-balance reduction; preserve sorted account locking.
- **Database changes:** None expected; no cached-balance rewrite.
- **Dependencies:** P0-02 policy; clarify whether deliberate negative correction is allowed.
- **Testing:** Income 100/expense80/delete income; edit income to10; move income; lower opening; duplicate requests; transactions crossing month; archived account.
- **Acceptance criteria:** Every correction follows one documented negative-balance policy, returns controlled errors, computes totals once.
- **Risk:** High: balance correctness.

## P0-04 — Align live schema and input contracts

- **Reuse:** models/user.py; models/finance.py; schemas/auth.py; schemas/onboarding.py; routers/settings.py; migrations/env.py.
- **Proposed new files:** backend/tests/test_mysql_schema_contract.py; additive migration if widening approved.
- **API requirements:** Preserve register/onboarding/settings endpoints; reject too-long input as422 or safely support approved expanded columns.
- **Database changes:** users name100/email254 vs ORM150/255; income name100 vs120 and precision14 vs12; nullable transaction fields; inspect legacy constraints before changes.
- **Dependencies:** Read-only schema snapshot; backup/recovery verification; use intended Alembic branch.
- **Testing:** Boundary names100/101/150, income100/101/120; 254 email; old null categories/descriptions; clean clone migration; unchanged prior-row hashes.
- **Acceptance criteria:** No accepted value fails solely because real column capacity is smaller; legacy nullable data serializes predictably; no genuine row updates.
- **Risk:** High: legacy schema compatibility.

## P0-05 — Session invalidation after credential changes

- **Reuse:** core/security.py; core/deps.py; models/user.py; routers/settings.py; routers/auth.py; services/authApi.js.
- **Proposed new files:** backend/tests/test_session_revocation.py; additive token-version migration if selected.
- **API requirements:** Keep login/password endpoints; include/check session version or issued-before cutoff; local logout cleanup.
- **Database changes:** Additive user token_version/password_changed_at only if chosen; existing tokens need a deliberate rollout policy.
- **Dependencies:** P0-04 migration safety.
- **Testing:** Old token after password change =>401; new login succeeds; other users unaffected; expired/tampered/missing versions; suspension/re-enable policy.
- **Acceptance criteria:** Pre-change stolen token cannot access protected data after password change; active sessions and rollout behavior documented.
- **Risk:** High: authentication rollout.

## P0-06 — Disposable MySQL concurrency and migration/startup verification

- **Reuse:** backend/tests/test_family.py; tests/family_mysql_races.py; app/database.py; app/main.py; migrations/versions/*.
- **Proposed new files:** Safe dedicated-db concurrency harness; CI definition in later P3 phase.
- **API requirements:** No product API additions; health continues read-only.
- **Database changes:** Dedicated disposable test DB with reviewed schema setup; no grants/drop/reset on current database.
- **Dependencies:** P0-01 through05; separately provisioned isolated DB; approval for setup when required.
- **Testing:** Simultaneous spend/transfer/reminder/receipt/goal/split/settlement/quota; revoke membership during write; lock-order/deadlock retry; crash rollback; blank DB install plan.
- **Acceptance criteria:** No duplicate postings/overdraft race/lost updates; current data never used as mutable fixtures; known branch/revision startup.
- **Risk:** High: engine-specific concurrency.

## P1-01 — Complete core account/transaction/budget UI workflows

- **Reuse:** Dashboard.jsx; transaction/Transaction.jsx; routers/account.py; transaction.py; budgets.py; API client.
- **Proposed new files:** Extend isolated browser tests and domain tests; avoid duplicate unused pages.
- **API requirements:** Reuse /accounts,/transactions,/transfers,/budgets; consistent error/pagination/month semantics.
- **Database changes:** None unless P0 schema review demands it.
- **Dependencies:** All P0 gates.
- **Testing:** Create/edit/archive/restore/transfer; transaction filters+pagination; budget category rename/duplicate/case; deleted/moved transaction usage; validation/errors/empty/loading.
- **Acceptance criteria:** Each core workflow round-trips through API and MySQL test DB, browser failure retries preserve intended submission key, existing design retained.
- **Risk:** Medium.

## P1-02 — Dashboard/report reconciliation and month accuracy

- **Reuse:** routers/dashboard.py; services/cash_flow.py; DashboardOverview.jsx; Dashboard.jsx; CashFlow.jsx; tests/test_cash_flow.py.
- **Proposed new files:** Reconciliation fixture tests; update existing browser assertions after format decision.
- **API requirements:** Keep /dashboard?year=&month=&include_cash_flow=true; clarify personal expense versus personal-account shared movement.
- **Database changes:** No change expected; account opening-date limitation must be documented or separately approved.
- **Dependencies:** P0 finance fixes; P1-01.
- **Testing:** Same-basis dashboard/budget/report totals; shared expense paid personally; reimbursements; archives; past/future month; empty month; actual cents; format tests independent of optional .00.
- **Acceptance criteria:** Numbers reconcile through explicitly labeled bases and selected month; no cross-scope double-counting; browser checks assert values appropriately.
- **Risk:** Medium.

## P1-03 — Goal/reminder completeness and recovery UX

- **Reuse:** routers/goals.py; reminders.py; Dashboard.jsx; Reminders.jsx; common error/loading components.
- **Proposed new files:** Extend feature/browser tests; loan schedule service only if PRD requires it.
- **API requirements:** Reuse goal archive/restore/contribute and reminder create/edit/pay; keep due_date replay contract.
- **Database changes:** None for basic reminders/goals; amortization schema is unapproved scope.
- **Dependencies:** P0-01/02/03.
- **Testing:** Remaining target exact cents; active limits; annual/leap/month-end recurrence; restored/archived items; failed pay retry; full forms; blank/whitespace fields.
- **Acceptance criteria:** All supported goal/bill operations persist/reload correctly; no duplicate deductions or payment markers; generic loan reminder labeled accurately.
- **Risk:** Medium.

## P1-04 — Forgotten-password recovery

- **Reuse:** auth.py; security.py; config.py; login/register layouts; password-change validation.
- **Proposed new files:** ForgotPasswordPage.jsx; ResetPasswordPage.jsx; reset-token model/migration; mail adapter; isolated tests.
- **API requirements:** Propose consistent /auth/forgot-password and /auth/reset-password; neutral response, single-use expiry, rate limits and current password rules.
- **Database changes:** Add hashed single-use reset token records and expiry/consumption indexes; never store plaintext tokens.
- **Dependencies:** Actual PRD/recovery delivery approval; P0-05; configured authorized sender.
- **Testing:** Known/unknown email indistinguishable; token expiry/reuse/tamper; delivery failure; new login; old session invalidated; no token logs.
- **Acceptance criteria:** Real authorized recovery works end-to-end without account enumeration or token reuse; synthetic tests only until delivery approval.
- **Risk:** High: security/delivery.

## P2-01 — Receipt/Advisor provider validation and merchant memory

- **Reuse:** routers/ai.py; services/ai.py; models/ai.py; AI.jsx; AdvisorMessage.jsx; advisorText.js.
- **Proposed new files:** Synthetic receipt fixtures and targeted browser/provider tests; rule manager only if PRD requires it.
- **API requirements:** Reuse /ai/categories,/usage,/receipts,/confirm,/advisor; propose rule CRUD only with approved UX.
- **Database changes:** None for automatic memory; retention policy/migration only if approved.
- **Dependencies:** P0 linked corrections/concurrency; consent for provider requests/costs; categories configured.
- **Testing:** Tamil/English/Tanglish; unknown total/currency; malicious receipt text; corrupted/large images; timeout/truncation; quotas; conflicting replay; user-isolated merchant reuse; no tool writes.
- **Acceptance criteria:** One confirmed transaction, reliable missing-data review, only authenticated context, no credit on failure, secrets stay backend-only.
- **Risk:** High: provider privacy/financial confirmation.

## P2-02 — Household collaboration end-to-end

- **Reuse:** FamilyPage.jsx; HouseholdFinance.jsx; routers/family.py; household.py; services/household.py; services/goals.py.
- **Proposed new files:** Extend household permission/browser/concurrency tests.
- **API requirements:** Reuse /family and /goals?scope=family; no new parallel household API.
- **Database changes:** Existing families/memberships/scope/shares/settlements/contributions reused; migration only if proven gap.
- **Dependencies:** P0 authorization/concurrency and core ledger; approved legacy/sponsor semantics.
- **Testing:** Invite/join/revoke/remove/leave; view-only/edit denial on every shared route; private income exclusion; funding; split rounding; simultaneous debt settlement; former contributor history.
- **Acceptance criteria:** Personal records remain private; authorized members see explicit shared ledger; settlement never recreates expense; contribution actor retained.
- **Risk:** High: cross-user finance.

## P2-03 — Plan/demo/admin verification

- **Reuse:** Upgrade.jsx; Admin.jsx; config/subscription.js; routers/subscriptions.py; admin.py; services/subscriptions.py; scripts/bootstrap_admin.py.
- **Proposed new files:** Extend isolated plan/admin/browser tests.
- **API requirements:** Reuse catalog/checkout/simulate/cancel/schedule and /admin; real gateway/webhooks only if explicitly approved.
- **Database changes:** Reuse subscriptions/demo_checkouts/platform_events; new real payment ledger is a separately approved design.
- **Dependencies:** PRD plan/price confirmation; P0 sessions; P2-02 sponsorship; authorized operator setup.
- **Testing:** Trial calendar/expiry/read-only export; sponsorship/revocation; monthly/yearly renewals; demo disabled/prod rejection; forged price/status; replay; admin metadata exclusion/search/paging/suspend.
- **Acceptance criteria:** Frontend cannot grant a real paid period; revenue clearly simulated; authorized admin sees metadata only; prices server-owned.
- **Risk:** High: entitlement trust boundaries.

## P2-04 — Dedicated AI goal planner and spending predictions

- **Reuse:** services/ai.py; goal/dashboard data; existing branded common components.
- **Proposed new files:** Planner/prediction services, schemas, UI and tests after PRD approval.
- **API requirements:** Proposed /ai/goal-plan and /ai/spending-predictions only after naming/requirements review; read-only outputs requiring explicit confirmation for writes.
- **Database changes:** Avoid new table until persistence/cache/audit needs approved.
- **Dependencies:** Actual PRD; P1 accurate totals; P2-01 provider validation; plan entitlement policy.
- **Testing:** Known baseline/horizon, empty/sparse history, outliers, seasonality if required, future data leakage, uncertainty, impossible targets, privacy/quota.
- **Acceptance criteria:** Defined requirements produce explainable validated output, never present invented certainty or silently mutate financial records.
- **Risk:** High: new undefined AI scope.

## P2-05 — Notifications/profile/export privacy completeness

- **Reuse:** Notifications.jsx; Settings.jsx; routers/notifications.py; settings.py; notification model.
- **Proposed new files:** Extend export/notification permission tests; delivery adapter/queue only if approved.
- **API requirements:** Reuse existing endpoints; external delivery only with consent/provider requirements.
- **Database changes:** Reuse notification_reads; optional delivery outbox only if required.
- **Dependencies:** P0 session/permissions; actual notification/privacy requirements.
- **Testing:** Notification read replay; removed shared member visibility; Google-only password UX; full export scope including shared actor entries; secret/hash exclusion.
- **Acceptance criteria:** Only authorized data exported/alerted; in-app state persists; no unsupported email/SMS claims.
- **Risk:** Medium/High.

## P3-01 — UI/accessibility/performance polish

- **Reuse:** common/Modal.jsx; layout/DashboardLayout.jsx; styles/variables.css; Dashboard.jsx; App.jsx; landing assets.
- **Proposed new files:** Focused keyboard/a11y tests; optional optimized assets.
- **API requirements:** No business API changes.
- **Database changes:** None.
- **Dependencies:** Stable P1/P2 functionality; browser formatting expectation decision.
- **Testing:** Focus entry/trap/return/Escape; labels/errors; mobile drawer; four widths plus real device; contrast/reduced motion; slow/error/empty; build sizes.
- **Acceptance criteria:** Pastel/glass identity retained; keyboard workflows complete; stale placeholders removed only where appropriate; sensible bundle/image budgets.
- **Risk:** Low/Medium.

## P3-02 — Deployment/reproducibility/documentation/final acceptance

- **Reuse:** DEPLOYMENT_GUIDE.md; README.md; env examples; requirements/package lock; main/config/database/migrations.
- **Proposed new files:** CI workflow and deployment manifests for approved target; safe setup guide; final E2E suite.
- **API requirements:** Read-only /health; configured HTTPS API/origin and SPA fallback.
- **Database changes:** Reviewed clean-install baseline/legacy branch procedure; TLS/persistent private storage/backup restore.
- **Dependencies:** All prior gates; approved host/secrets/sender/provider; real operator setup.
- **Testing:** Clean checkout install/build/tests; blank disposable MySQL setup; migration clone dry run; public TLS/CORS/OAuth; backup restoration to isolated DB; 10 consenting beta testers if desired.
- **Acceptance criteria:** Reproducible deploy with no destructive steps against genuine data; rollback/recovery reviewed; evidence recorded per feature and known limits explicit.
- **Risk:** High: operational data safety.

## Safe acceptance procedure for every approved phase

Use disposable SQLite for rapid deterministic cases and a separately isolated MySQL database for engine-specific acceptance. Run targeted tests first, then relevant existing regression suites, lint/build and the affected browser workflows. Do not seed, update or roll back write-tests inside the genuine database merely because a harness promises rollback. Record failures accurately and preserve historical financial records through additive reviewed migrations. No production deployment, external messaging, real payment activation or destructive database operation is implied by approval to implement code.

Before claiming COMPLETE, record the precise environment, successful UI/API/database workflow, validation/permissions, financial invariants and test results, then compare with the actual PRD. If the PRD remains unavailable, mark PRD matching BLOCKED.
