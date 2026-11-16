# MaxBud test report

Audit date: 16 November 2026, Asia/Colombo. Fresh results only. Existing historical TEST_REPORT.md was read as context, not counted as evidence for this run.

## Environment and safety

Existing local Node dependencies and `backend/.venv` were used. Installed Python versions: FastAPI 0.162.0, Starlette 1.10.0, SQLAlchemy 2.0.55, Pydantic 2.14.1, PyMySQL 1.2.3, pytest 9.2.0, httpx 0.28.1, Groq 1.7.0, Playwright 1.65.1, AnyIO 4.15.1. Vite build reports 8.3.5. No package was installed/upgraded.

Backend suite: `FAMILY_TEST_MYSQL=0` explicitly selects in-memory SQLite; tests override get_db. Receipt tests patch storage to temporary directories and mock the provider. TestClient in the unit fixture does not enter the actual MySQL lifespan. Browser suite uses a temporary SQLite file, a seeded synthetic operator fixture, local FastAPI :8766 and Vite :5175, headless Chrome and disabled external AI. Screenshots/build/logs and extra audit scripts were written to `/tmp`; only the four requested reports are persistent audit additions in the repository.

Live MySQL was used only for `SELECT 1`, metadata inspection, migration revision SELECT, application lifespan and `/health`. Metadata operations used a READ ONLY transaction and rollback. No financial/user row contents were read into reports; no financial DML, seed, migration upgrade, drop/reset, real admin creation or payment was performed. No external Groq/Google call was made. A configured key does not prove valid provider access. Browser registration/login only used synthetic SQLite accounts.

## Commands and results

Paths below are relative to repository root unless a working directory is specified. Temporary helper scripts are audit tooling outside the application; their exact purpose and results are detailed below.

| Command / check | Result | Details |
|---|---|---|
| `git status --short`; `rg --files` / targeted source reads | PASS, inventory | Extensive pre-existing modified/untracked files; preserved. Searched repository and supplied attachment for PRD/PDF/DOCX; no PRD located. No applicable AGENTS.md found in checked ancestor/project locations. |
| `npm run lint` (frontend) | PASS, exit 0 | ESLint existing configured active source; inactive src_backup excluded by config. |
| `npm test` (frontend) | PASS, exit 0 | Node runner reports 3 passing test files, 0 failing: auth.test.mjs, advisor.test.mjs, advisor-render.test.mjs. Do not interpret this as three total assertions or broad UI coverage. |
| `npm run build -- --outDir /tmp/maxbud-audit-build` (frontend) | PASS, exit 0 | 2352 modules; Vite 8.3.5; ~9.94s. Existing dist untouched. Large-chunk warning described below. |
| `.venv/bin/python -m pip check` (backend) | PASS, exit 0 | No broken requirements found. Cache permission warning did not affect dependency inspection. |
| Python `ast.parse` over app/migrations/tests | PASS, exit 0 | 61 Python files parsed without writing bytecode or importing opt-in live-provider scripts. |
| `from app.main import app; app.openapi()` | PASS, exit 0 | 73 paths / 93 API operations, including health. Import alone does not test DB startup; lifespan tested separately. Current FastAPI lazily includes routers: initial flat app.routes listing omitted included operations; OpenAPI generation verified the full registered routes. |
| `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` (backend, sandbox) | BLOCKED / interrupted, exit 130 | Stalled on first registration in TestClient; stopped after retry diagnosis, not counted as an application assertion failure. |
| Same sandbox diagnostic under `timeout 30`, with `faulthandler.dump_traceback_later(15)` | BLOCKED, exit 124 | Main thread waits in AnyIO blocking portal / Starlette TestClient.handle_request; event-loop thread in selector. Does not establish a financial/API bug. |
| `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 timeout 240 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` (backend, approved outside sandbox) | PASS, exit 0 | **48 tests, 65.310s, OK.** Same SQLite-only fixture; no live MySQL writes. |
| `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/maxbud_readonly_audit.py` (backend, sandbox) | BLOCKED initially, exit 2 | SQLAlchemy OperationalError / PyMySQL code **2003**, unable to connect to configured MySQL from sandbox. Connection target/credentials suppressed. |
| Same read-only helper, approved outside sandbox | PASS | SELECT 1=1; 36 real tables; 26 ORM tables; no missing mapped table/column; revision 20261115_beta. |
| `.venv/bin/alembic heads` (backend) | PASS, exit 0 | Two heads: 20261104_accounts; 20261115_beta (maxbud_features). This is source graph inspection, not a migration application. |
| `PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 timeout 45 .venv/bin/python /tmp/maxbud_schema_details.py` (backend, approved outside sandbox) | PASS | Introspected FK/index/unique details for all 26 mapped tables, no missing ORM unique column combination reported. App lifespan entered; `/health` returned 200 with database connected. |
| `FAMILY_TEST_MYSQL=0 PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 timeout 60 .venv/bin/python /tmp/maxbud_audit_probes.py` (backend, approved outside sandbox) | Executed, 4 reproduced gaps | Uses FamilyTests disposable fixture; outputs below. Script exits successfully because it records observed behavior, not because invariants passed. |
| `PYTHONDONTWRITEBYTECODE=1 timeout 180 backend/.venv/bin/python /tmp/maxbud_browser_audit.py` (approved outside sandbox) | FAIL, exit 1 | Invokes original frontend/tests/polish_browser.py via import; ARTIFACTS points to /tmp. All 12 dashboard pages at four widths passed before a stale trailing-.00 assertion failed. |
| `PYTHONDONTWRITEBYTECODE=1 timeout 180 backend/.venv/bin/python /tmp/maxbud_browser_followup.py` (approved outside sandbox) | PASS, exit 0, supplemental run | Reads original browser suite and changes only `'LKR 1,950.00'`→`'LKR 1,950'` and `'LKR 750.00'`→`'LKR 750'` in memory. Screenshots go to /tmp/maxbud-audit-ui-followup. Repository tests/application files unchanged. Does not erase the original failure. |

The broad initial ancestor `find` was superseded by scoped ancestor/project instruction-file checks; it is not functional test evidence. No browser test requiring real Groq, legacy destructive race harness, MySQL write fixture, live-user login, external email, real payment or migration upgrade was run.

## Existing backend cases that passed

The 48 cases cover normal flows and important negative cases, but are not exhaustive. Custom `load_tests` hooks select newly defined cases in subclasses; do not multiply case counts by inherited fixture methods. SQLite does not enforce the same MySQL VARCHAR length/locking behavior, and these fixtures do not prove compatibility with every legacy row.

- `test_admin.AdminTests.test_secure_creation_login_wrong_password_and_no_public_admin`
- `test_admin.AdminTests.test_promotion_verifies_password_and_preserves_hashes_and_finances`
- `test_admin.AdminTests.test_missing_expired_tampered_and_suspended_admin`
- `test_admin.AdminTests.test_user_actions_search_filters_cycles_and_private_metadata`
- `test_admin.AdminTests.test_trial_monthly_yearly_statistics_and_simulated_revenue`
- `test_beta.BetaTests.test_new_registration_trial_calendar_expiry_and_export`
- `test_beta.BetaTests.test_demo_checkout_trust_failures_replays_cancellation_and_renewal`
- `test_beta.BetaTests.test_invitation_security_sponsorship_and_revocation`
- `test_beta.BetaTests.test_invite_expiry_duplicate_and_capacity`
- `test_beta.BetaTests.test_shared_wallet_funding_expenses_budgets_and_private_isolation`
- `test_beta.BetaTests.test_equal_split_partial_reimbursement_does_not_duplicate_expense`
- `test_beta.BetaTests.test_percentage_and_custom_splits_are_decimal_exact`
- `test_beta.BetaTests.test_family_expiry_preserves_records_and_own_paid_member_subscription`
- `test_beta.BetaTests.test_shared_permission_revocation_covers_goals`
- `test_beta.BetaTests.test_shared_bill_payment_month_report_and_retry_conflict`
- `test_beta.BetaTests.test_yearly_checkout_expiry_and_family_downgrade_keeps_history`
- `test_beta.BetaTests.test_receipt_missing_total_review_categories_confirmation_and_usage`
- `test_beta.BetaTests.test_provider_failures_and_authorized_advisor_context`
- `test_beta.BetaTests.test_admin_metadata_security_demo_labels_and_audit`
- `test_cash_flow.CashFlowTests.test_brought_forward_transfers_shared_payments_archives_and_privacy`
- `test_cash_flow.CashFlowTests.test_empty_month_opt_in_and_period_validation`
- `test_family.FamilyTests.test_dashboard_totals_budgets_transfer_and_isolation`
- `test_family.FamilyTests.test_expired_and_inactive_auth`
- `test_family.FamilyTests.test_free_limit`
- `test_family.FamilyTests.test_invalid_and_duplicate_inputs`
- `test_family.FamilyTests.test_legacy_user_not_changed_during_login`
- `test_family.FamilyTests.test_member_and_cross_family_authorization`
- `test_family.FamilyTests.test_member_login_list_and_password_safety`
- `test_family.FamilyTests.test_premium_limit_and_expiration`
- `test_family.FamilyTests.test_registration_overview_and_refresh`
- `test_family.FamilyTests.test_removal_preserves_data_and_revokes_existing_token`
- `test_features.FeatureTests.test_goal_completion_limits_and_isolation`
- `test_features.FeatureTests.test_reminder_payment_is_idempotent_and_isolated`
- `test_features.FeatureTests.test_advisor_provider_failure_does_not_consume_usage`
- `test_features.FeatureTests.test_receipt_review_confirmation_and_invalid_upload`
- `test_features.FeatureTests.test_admin_is_separate_from_owner_and_settings`
- `test_features.FeatureTests.test_notification_state_is_personal`
- `test_features.FeatureTests.test_transaction_submission_key_prevents_duplicate`
- `test_features.FeatureTests.test_safe_to_spend_reserves_bills_once`
- `test_features.FeatureTests.test_new_user_onboarding_and_persistence`
- `test_features.FeatureTests.test_ai_limits_and_premium_test_subscription`
- `test_features.FeatureTests.test_rate_limit_has_cors_and_retry_header`
- `test_features.FeatureTests.test_google_verification_and_verified_email`
- `test_shared_family.SharedFamilyTests.test_full_family_journey_and_history_after_removal`
- `test_shared_family.SharedFamilyTests.test_shared_goal_owner_permissions_and_duplicate_requests`
- `test_shared_family.SharedFamilyTests.test_inactive_members_keep_seats_and_cannot_contribute`
- `test_shared_family.SharedFamilyTests.test_currency_and_subscription_expiry_preserve_history`
- `test_shared_family.SharedFamilyTests.test_household_bills_omit_private_names_and_accounts`

## Financial/security probes: expected versus actual

All values below belong to disposable synthetic fixtures, not genuine users.

| Probe | Expected invariant / recommended policy | Actual observation | Result / verified root cause |
|---|---|---|---|
| Same personal goal request_id, amount 10, sent twice | One allocation; repeat returns existing result | HTTP200 saved10.00 then HTTP200 saved20.00 | **BROKEN FIN-01**: personal branch increments saved_amount directly; request_id handling exists only in shared branch. Frontend omits key for personal contributions. |
| Income100, expense80, delete income | Consistent explicit correction policy; insufficient-funds protection should not be bypassed accidentally | Expense201; delete200; balance −80.00 | **BROKEN FIN-03 policy gap**: deletion soft-deletes without final-balance check. Arithmetic is correct for the remaining ledger; accepting negative correction is an undefined/inconsistent business rule, not a rounding error. |
| Reminder10 paid from100, delete linked expense, pay same occurrence again | Paid state and ledger remain consistent | Delete200; replay200 `{transaction_id:3, already_paid:true}`; account100.00 | **BROKEN FIN-02**: ReminderPayment persists while generic deletion hides its expense; editable() only protects transfers. Original synthetic ID is not a genuine record identifier. |
| Change password then reuse original bearer JWT | Recommended security policy: old sessions revoked | Password change200; old token `/auth/me`200 | **BROKEN AUTH-01 under recommended revocation policy**: no password-version/revocation comparison. Current source implements expiry/suspension only; actual PRD session policy unavailable. |

No probe was implemented as a committed application test during this audit. Add regressions during the approved first implementation phase. Account income edits/moves, opening-balance reductions, receipt-linked mutation and concurrency risks are source findings, not separately executed reproductions.

## Live database structural findings

Read-only retry unblocked database verification; live checks are **not left marked BLOCKED** after successful retry. Verification does not assert genuine-row consistency or end-to-end MySQL financial writes. No data-row reconciliation/checksum was run.

| Table/column | ORM/input contract | Live metadata | Interpretation |
|---|---|---|---|
| users.full_name | VARCHAR150; register/profile max150 | VARCHAR100 | Material capacity mismatch; accepted long names may fail at persistence. |
| users.email | VARCHAR255; EmailStr | VARCHAR254 | Contract drift; boundary handling requires MySQL test. |
| income_sources.name | VARCHAR120; onboarding max120 | VARCHAR100 | Material capacity mismatch. |
| income_sources.amount | Numeric12,2 | DECIMAL14,2 | Live schema can hold amounts beyond current input/model precision; review compatibility, not missing data. |
| transactions.category/description | Non-null mapped strings | Nullable legacy columns | Possible output validation problem if actual NULL rows exist; private rows not inspected to claim occurrence. |
| budgets.family_scope | Computed COALESCE(family_id,0), ORM non-null | Generated integer reported nullable | Definition/nullability metadata drift; expression itself yields non-null. |
| Other Numeric/Boolean/string metadata | NUMERIC/BOOLEAN/strings | DECIMAL/TINYINT/explicit collation | Dialect aliases/collation rendering alone are not incompatibility. |

Introspection retrieved foreign keys and indexes; expected ORM unique constraints by column combination were all present. Key enforced combinations include transfer user/request, transfer/kind entries, budget user/family_scope/category, goal-contribution user/request, advisor user/request, merchant user/name, reminder occurrence, transaction user/key, checkout user/request, expense transaction/member and settlement user/request. Existing extra legacy columns/foreign keys were preserved. No performance EXPLAIN or load test was run.

Real tables verified:

- `account_legacy_map`
- `account_transfer_records`
- `account_transfers`
- `accounts`
- `advisor_messages`
- `ai_scans`
- `ai_usage`
- `alembic_version`
- `auth_identities`
- `authentication_identities`
- `budgets`
- `categories`
- `demo_checkouts`
- `families`
- `family_invitations`
- `family_memberships`
- `financial_accounts`
- `goal_contributions`
- `goals`
- `household_expense_shares`
- `household_settlements`
- `income_sources`
- `merchant_rules`
- `monthly_budgets`
- `notification_reads`
- `onboarding_profiles`
- `payment_reminders`
- `platform_events`
- `reminder_payments`
- `savings_goals`
- `subscriptions`
- `transaction_audit_logs`
- `transaction_requests`
- `transactions`
- `user_profiles`
- `users`

## Browser/UI observations and failure root cause

Original suite successfully checked landing grid layout at 1440/1024/768/360, feature artwork bounds, login mobile layout, FAQ toggle, all 12 dashboard paths at 1440/1024/768/360 without document horizontal overflow, dashboard card hierarchy, navigation collapse and subscription data. Paths: overview, accounts, transactions, budgets, goals, reminders, reports, family, ai-scan, ai-advisor, upgrade, settings. Notifications is not one of these 12 paths. This is page rendering, not every page's CRUD acceptance.

It then failed at `frontend/tests/polish_browser.py:115`: expected `LKR 1,950.00`, actual summary text `LKR 1,950`. `api/client.js` money() uses minimumFractionDigits0/max2, so whole-number display is intentional; DashboardOverview uses a different fixed-cent display. Values were correct. This is a stale test expectation/presentation consistency issue, not evidence that the account balance calculation is wrong. Recommend a deliberate formatting standard and robust value assertions.

Supplemental follow-up (two currency expectations changed in memory) passed all remaining checks: reports list synthetic salary/groceries/running balance, historical empty-month selection and return, advisor suggestion filling and real 503 disabled-provider error, escaped/rendered synthetic advisor history, mobile navigation/drawer close/reset on desktop, and all admin monitoring tabs without alerts. Browser reported no page errors. This does not verify real AI answers, full household mutations, payment simulation browser flow, profile password change in UI, public signup/onboarding forms or real operator credentials.

Desktop overview screenshot inspected: existing aqua/pink/cream cards, clear sidebar/chart headings, empty states and synthetic totals render consistently. Source review found missing common-modal focus/escape management and absent bundled Vescura font definition. These visual/accessibility findings are separate from financial defects; no WCAG certification, measured contrast score or mobile hardware review is claimed.

## Build warnings and other diagnostics

Production asset sizes: JavaScript828.75kB /240.39kB gzip; CSS96.57kB /18.49kB gzip; large logo/hero assets approximately625kB,963kB,1.07MB. Vite warns chunk exceeds500kB; consider route splitting and image optimization after correctness fixes. `/tmp` output warning simply indicates an external output directory will not be emptied; it was intentional.

Unit suite warns that Starlette TestClient use of httpx is deprecated in favor of httpx2; existing requirement stack still runs. Some tests use datetime.utcnow(), producing a deprecation warning. Neither warning is an assertion failure. Do not upgrade dependencies during an audit.

## Still blocked / not tested / missing

- **BLOCKED:** requirement-by-requirement PRD comparison, because no actual PRD supplied/found.
- **NOT TESTED:** all genuine-row consistency queries and financial MySQL write flows (intentionally excluded), clean database install, actual migration application, isolated multi-connection MySQL races, production host/TLS/backup recovery/load, real devices/full accessibility, fresh Groq/Google OAuth. No external call was needed for safe contract verification.
- **MISSING:** forgotten-password recovery, dedicated planner/prediction service, real gateway/webhooks, outbound email/SMS/job delivery, dedicated loan amortization. Real gateway/amortization/email/planner details remain subject to the actual PRD; the audit request explicitly allows clearly labeled demo subscriptions.
- **BROKEN:** reproduced allocation replay, payment-ledger mutation consistency, balance-correction policy and password-change session revocation gaps; original browser suite has one stale expectation failure.

## Exact additional regression cases recommended

1. Personal goal: same request twice/parallel increments once; same key different amount/goal rejected; replay after completion succeeds; foreign user denied; failed response retry returns original allocation; saved_amount initial balance retained without historic writes.
2. Linked transactions: reminder/receipt-linked edit/delete blocked or atomically reversed; repeat correction; original audit history retained; recurring occurrence replay never charges next month; foreign-user references denied.
3. Balance corrections: reduce/delete/move spent income, change kind/account, lower opening balance, edit expired/archived account, rollback all touched records, deterministic account-lock order.
4. MySQL schema: name/email boundary lengths, legacy NULL category/description serialization, income precision, generated budget uniqueness, indexes/constraints on dedicated clone, blank-install and branch precondition behavior.
5. MySQL races: competing spends, opposite transfers, same idempotency key, final goal cents, simultaneous recurring pay/receipt confirm, quota boundary, split settlements and revoke membership during pending writes. Never use genuine DB as a mutable race fixture.
6. Auth: token revocation on password change, suspended accounts, per-endpoint household/admin/user denial, reset token expiry/reuse/enumeration and provider delivery failures once recovery is implemented.
7. Reports: match totals on the same scope/period; reconcile account movements containing shared payments/reimbursements; deleted/backdated/future/archived records; opening balance basis; exact Decimal cents and stable UI display assertions.
8. AI/merchant: actual synthetic Tamil/English receipt, missing total, invalid category/currency, prompt injection, timeout/truncation, failed credits, category change and per-user merchant isolation/reuse; one confirmation only.
9. Browser full journeys: signup/five onboarding steps with reload, account/transaction/budget/goal/bill CRUD, errors/duplicate click/retry, household invite/permission/settlement, enabled demo checkout, admin actions, notification reads/export and keyboard modal accessibility.

## Outcome

Existing unit/contract suites are green; the original browser test has a verified stale formatting assertion; supplemental browser continuation passes. These facts do not certify the product: targeted probes exposed missing invariants, and the actual PRD plus production/concurrency/external integrations remain unverified. Implement only after `START IMPLEMENTATION`.
