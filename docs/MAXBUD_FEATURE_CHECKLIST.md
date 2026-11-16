# MaxBud feature checklist

16 November 2026. PRD unavailable: PRD matching is **BLOCKED for every row**. No module is certified COMPLETE. Live table presence was verified read-only; all writes/tests below use disposable SQLite and synthetic accounts. `S` = source inspected, `A` = isolated API suite passed relevant cases, `N` = Node tests passed, `B` = browser page/viewport smoke passed (not every form action). Feature subrows inherit module context. Validation/permissions are assessed in the evidence table following the checklist. Status BROKEN is used only for reproduced behavior; PARTIAL includes unexecuted live integrations and incomplete coverage. Missing features have no table requirement until requirements are approved.

## All requested modules

| Feature | Frontend | Backend | Database | Tested | Status | Pending Work | Priority |
|---|---|---|---|---|---|---|---|
| 01 Landing/public navigation | LandingPage, Navbar | public plan catalog | No page table required | S,B | PARTIAL | Full link/CTA/accessibility checks; PRD comparison | P3 |
| 02 Registration/login | LoginPage/RegisterPage | /auth/register, /auth/login, /auth/me | users/auth_identities/subscriptions live | A,N; login B | PARTIAL | DB-01 length alignment; complete browser signup flow | P0 |
| 03 Password reset/authentication | Password change in Settings; no recovery page | JWT/password change; no forgot/reset endpoints | No recovery token model found | A; AUTH-01 probe | PARTIAL | Recovery workflow; invalidate sessions on credential change | P0/P1 |
| 04 Five-step onboarding | Onboarding.jsx | Five persisted steps + /status | users/income_sources/accounts/budgets/goals live | A,S | PARTIAL | Real MySQL length boundaries; browser resume/validation | P0/P1 |
| 05 User dashboard | DashboardOverview | /dashboard with personal/family scope | Core tables live | A,B | PARTIAL | Reconcile basis labels and all card/edit cases | P1 |
| 06 Accounts | Dashboard account panels | /accounts CRUD/archive | accounts live | A,B,S | PARTIAL | Resulting-balance correction policy; more account edit tests | P0/P1 |
| 07 Income/expenses | Dashboard transaction panels | /transactions list/create/read/edit/delete | transactions live | A,B; FIN-02/03 probes | BROKEN | Linked-entry mutation/reversal and negative-balance correction | P0 |
| 08 Account transfers | Dashboard transfer form | POST /transfers | account_transfer_records + paired transactions live | A,B,S | PARTIAL | Mandatory retry semantics decision; disposable MySQL races | P0/P1 |
| 09 Monthly budgets | Dashboard budgets | /budgets and /budgets/alerts | budgets live | A,B | PARTIAL | Month/category/edit/delete and concurrency edge coverage | P1 |
| 10 Savings goals/contributions | Dashboard goals | /goals CRUD/contribute/status | goals/goal_contributions live | A,B; FIN-01 probe | BROKEN | Personal contribution retry ledger and stable form key | P0 |
| 11 Bill/loan reminders | Reminders.jsx | /reminders CRUD/pay | payment_reminders/reminder_payments live | A,B; FIN-02 probe | BROKEN | Protect/reverse linked payments; loans are generic reminders | P0 |
| 12 Reports/analytics | Reports tab/CashFlow | /dashboard?include_cash_flow=true | Existing ledgers live | A,B; browser formatting failure | PARTIAL | Update stale assertions; extend scope reconciliation and mutation tests | P1 |
| 13 AI receipt scanner | AI mode=scan | /ai/receipts + confirm | ai_scans/ai_usage/transactions live | A mocked; B page | PARTIAL | Fresh real provider extraction, upload/review UI and linked reversals | P2 |
| 14 AI Money Advisor | AI mode=advisor/AdvisorMessage | /ai/advisor history/ask | advisor_messages live | A mocked,N,B page | PARTIAL | Fresh real provider evaluation and financial-context/privacy checks | P2 |
| 15 Merchant Memory | Automatic scanner behavior; no rule manager | Learn on confirm; lookup on scan | merchant_rules live | S; confirmation A | PARTIAL | Dedicated reuse/isolation/stale-category tests; approve management UX if needed | P2 |
| 16 AI planner/spending predictions | Landing illustrative/planned marketing | No dedicated planner/prediction service found | No dedicated model found | S | MISSING | Approve PRD contract and implement dedicated behavior | P2 |
| 17 Household management | FamilyPage | /family create/rename/leave/close/invites | families/memberships/invitations live | A,B | PARTIAL | Owner/member full browser journey and disposable MySQL races | P2 |
| 18 Household permissions | Owner permission toggles | Owner + view/add enforcement | family_memberships flags live | A,S | PARTIAL | All endpoint denial matrix after revocation/removal | P0/P2 |
| 19 Shared finance | HouseholdFinance/shared goals | /family wallets/expenses/budgets/bills + /goals?family | Scope columns + shares/settlements/contributions live | A,B page | PARTIAL | Concurrent retries/settlements; full real MySQL UI verification | P1/P2 |
| 20 Free/Premium plans | Upgrade/catalog | Entitlement/trial/read-only/legacy sponsorship | subscriptions live | A,B | PARTIAL | PRD reconciliation of trial/legacy/new-plan semantics | P2 |
| 21 Payment or labeled demo | Upgrade explicitly demo | Guarded checkout/simulate; no real gateway | demo_checkouts/platform_events live | A; demo disabled in current config | PARTIAL | Verify enabled demo UX; real payments only if approved requirement | P2 |
| 22 Admin authentication | Shared login + AdminRoute | current_user + admin dependency; private CLI | users/auth_identities live | A; B fixture route | PARTIAL | Authorized real operator setup/login; session revocation | P0/P2 |
| 23 Admin dashboard | Admin tabs/overview | /admin/overview | users/subscriptions/demo metadata live | A,B page | PARTIAL | Admin action journeys; scaling checks | P2 |
| 24 Admin user management | Admin table/search/actions | /admin/users + PATCH | users/platform_events live | A | PARTIAL | Browser search/paging/suspend/re-enable tests | P2 |
| 25 Admin billing/revenue/AI | Admin monitoring tabs | /admin/subscriptions,billing,ai-usage,activity,settings | Subscription/demo/usage/events live | A,B tabs | PARTIAL | Full admin action journeys; all totals labeled simulated | P2 |
| 26 Notifications | Notifications page/bell | In-app derived alerts/read state | notification_reads/reminders/budgets/goals live | A,S; not among 12 B paths | PARTIAL | No outbound email/SMS; notification permissions/completed shared goals review | P2 |
| 27 Profile/settings | Settings page | Profile/password/export | users/auth_identities + owned tables live | A,B | PARTIAL | JWT revocation; Google-only password UX; full export privacy cases | P0/P3 |
| 28 Security/privacy | Session guards/escaped advisor rendering | Auth/admin/scope/plan/upload/CORS/rate controls | Constraints present; no token revocation field | A,N,S; AUTH-01 probe | PARTIAL | Session version; multi-worker limiting; security/accessibility review | P0 |
| 29 Responsive UI/UX | Brand CSS/mobile drawer/common states | API error responses used | N/A | B four widths; screenshot review | PARTIAL | Common modal keyboard behavior; full a11y/real-device testing | P3 |
| 30 Deployment | Vite prod build/env examples | Health/config guards/deployment guide | Live connectivity verified; TLS not configured in dev | Build + health; no public deploy | PARTIAL | Clean install/CI/HTTPS/TLS/storage/backup restore/release gates | P3 |
| 02a Email/password validation | Native + server messages | RegisterIn strength/confirmation/email | users live; length drift | A,N | PARTIAL | Align name/email limits to live schema | P0 |
| 02b Google OAuth | GoogleAuthButton/provider | Verify Google ID token/audience/verified email | auth_identities live | A mocked; real NOT TESTED | PARTIAL | Real approved OAuth origin/login/cancel/link-conflict tests | P2 |
| 03a Forgotten-password recovery | Absent | Absent | Absent | S | MISSING | One-time expiring reset token, mail adapter and tests | P1 |
| 03b Password change/session invalidation | Settings form | Password hash changes, JWT stays valid | No token version field | A + old JWT probe | BROKEN | Revoke pre-change tokens under defined policy | P0 |
| 04a About you / currency | Step 1 | POST /onboarding/about-you | users live | A | PARTIAL | Whitespace, name limits and currency boundaries | P1 |
| 04b Planned income | Step 2 | POST /onboarding/income | income_sources live; name/precision drift | A,S | PARTIAL | Align lengths and weekly/yearly expectations | P0 |
| 04c Account opening balances | Step 3 | POST /onboarding/accounts | accounts live | A | PARTIAL | Browser empty/invalid/multiple account flow | P1 |
| 04d Initial budgets | Step 4 | POST /onboarding/budgets | budgets live | A | PARTIAL | Zero/duplicate/whitespace categories and retries | P1 |
| 04e Goals and resume | Step 5/status fetch | POST /onboarding/goals + step locks | goals/users live | A | PARTIAL | Plan limit boundary and browser reload on every step | P1 |
| 06a Create/edit/archive/restore | Account cards/modals | Create/patch/archive; history retained | accounts live | A,S,B page | PARTIAL | Lowering opening balance after spending; archived transfer checks | P0 |
| 07a Transaction replay keys | Stable key on create | Optional Idempotency-Key + payload hash | transaction_requests unique live | A | PARTIAL | Parallel same key; payload change; missing key policy | P0 |
| 07b Transaction edit/account move | Edit forms | Locks old/new account, derived balances | transactions/accounts live | S; incomplete tests | PARTIAL | Income decrease/move and source final-balance cases | P0 |
| 07c Delete linked financial entries | Delete action | Soft delete permits reminder-linked transaction | payment reference remains live | Probe failed invariant | BROKEN | Atomic reversal or protected linked edit/delete | P0 |
| 08a Transfer paired/atomic/replay | Transfer modal | Decimal, ownership, currency, balance, key checks | Unique user/request and transfer/kind live | A | PARTIAL | Fault-injected rollback and concurrent retries | P0 |
| 09a Budget usage/warnings | Progress/status cards | Eligible month expense totals; warning >=80% | budgets/transactions live | A | PARTIAL | Rename categories, midnight/month-end and deleted entries | P1 |
| 10a Personal allocation retry | Contribution form omits key | Accepted key ignored on personal branch | Personal saved_amount direct increment | Probe: 10 then 20 | BROKEN | Append-only personal contribution/key contract | P0 |
| 10b Shared contribution attribution | Family goal/history UI | Ledger user/request/replay/remaining checks | goal_contributions live | A | PARTIAL | Isolated concurrent final-cent contributions | P0/P2 |
| 11a Recurrence/mark paid | Due-date request + busy state | Unique occurrence; weekly/monthly/yearly | reminder_payments live | A | PARTIAL | Rollback/reversal and leap-year/yearly boundaries | P1 |
| 11b Loan amortization/principal | No dedicated UI | No dedicated calculation/model | No dedicated table | S | MISSING | Only implement if approved PRD requires more than reminders | P2 |
| 12a Month cash flow/opening balance | CashFlow table/month input | Brought forward + running ledger, archives included | No account opening-date field | A; B page | PARTIAL | Historical opening-date limitation; stale .00 assertions | P1 |
| 12b Shared/personal report reconciliation | Scope labels exist | Personal excludes family expense totals; account report includes paid movements | Explicit family_id live | A | PARTIAL | Add reconciliation case and clear report basis explanation | P1 |
| 13a Upload security | PNG/JPEG chooser | 5 MB, decode, bomb checks, re-encode/private file | ai_scans live | A mocked | PARTIAL | Boundary/corruption/privacy/retention and browser upload cases | P2 |
| 13b Receipt confirmation retry | Review/account/category selection | One linked transaction + replay | ai_scans transaction reference live | A mocked | PARTIAL | Protect linked reversal; conflicting replay payload behavior | P0/P2 |
| 13c Missing totals/currency review | Printed vs calculated extraction fields | Null unknowns, Decimal, selected category, currency matching | Receipt JSON details live | A mocked | PARTIAL | Fresh Tamil/English real-provider accuracy evaluation | P2 |
| 14a Advisor history/context/quota | Safe formatted text, no raw HTML | Authenticated aggregate context, quota/failure handling | advisor_messages/usage live | A,N | PARTIAL | Live synthetic advice quality, timeout and quota races | P2 |
| 15a Merchant learning/reuse | Automatic scanner suggestion | Scoped merchant rule set/lookup | Unique user/merchant live | S + confirm A | PARTIAL | Same merchant two users; category removed; retry learning | P2 |
| 15b Merchant rule management | Absent | No CRUD endpoints | Rule model exists | S | BACKEND ONLY | Management UI/API only if PRD requires user editing | P2 |
| 16a Goal planner | Marketing only | Absent | Absent | S | FRONTEND ONLY | Dedicated plan generation/validation contract | P2 |
| 16b Spending predictions | Marketing illustration only | Absent | Absent | S | FRONTEND ONLY | Define horizon/baseline/uncertainty and prediction API | P2 |
| 17a Invitations/join/leave/revoke | Secure fragment link workflow | Email-bound hashed token, expiry/capacity/owner checks | family_invitations live | A | PARTIAL | Full browser invite journey; no automatic email sender | P2 |
| 18a View/add/revoked membership | Permission controls | Current active membership + locks and flags | family_memberships live | A | PARTIAL | Every shared route, removed token and simultaneous revoke/write | P0 |
| 19a Shared wallets/funding | HouseholdFinance | Paired ledger funding, owner wallet management | accounts family_id/transfer records live | A | PARTIAL | Concurrent funding/insufficient balance and double-click UI | P0/P2 |
| 19b Shared expenses/splits | Personal/wallet source selection | Equal/custom/percentage Decimal cent allocation | transactions/household_expense_shares live | A | PARTIAL | Concurrent spend, custom zero/cent totals and rollback injection | P1 |
| 19c Reimbursements | Settlement controls | Debt ownership/remaining checks, paired transfers | household_settlements live | A | PARTIAL | Parallel partial/full settlements and revoked debtor cases | P0/P2 |
| 19d Shared budgets/bills | Shared feature forms | Owner/edit permissions and family-scoped report totals | budgets/payment_reminders family_id live | A | PARTIAL | Linked shared-payment mutation/reversal and month comparisons | P1 |
| 20a Trial/expiry/read-only export | Status/upgrade/export UI | 3 calendar months; expired editing denied | Trial dates/subscription source live | A | PARTIAL | PRD approval of legacy grandfathering and scheduled plan semantics | P2 |
| 20b Backend feature limits | Usage/upgrade UI | Server goal/reminder/AI/member quotas | Subscription/usage tables live | A | PARTIAL | Onboarding and concurrent quota-boundary cases | P0/P2 |
| 21a Demo checkout/simulated revenue | Clearly labeled demo | Disabled by default; production rejects simulation | Demo records live | A mocked configuration | PARTIAL | Enabled demo browser flow; never claim real revenue | P2 |
| 21b Real gateway/webhooks | Absent | Absent | No verified real-payment ledger | S | MISSING | Only if approved: signed webhook/reconciliation before activation | P2 |
| 22a Private admin provisioning | CLI, not public UI | Password-verified operator CLI + role checks | users/events live | A | PARTIAL | Actual operator provisioning is intentionally not performed | P2 |
| 24a Suspend/reactivate/search | Admin controls | Protected status changes and metadata filters | users/events live | A | PARTIAL | Browser action confirmation/paging and current-token suspension | P2 |
| 25a Private finance exclusion | Metadata tables | No private transaction/account/receipt projections | Metadata only | A,S | PARTIAL | Maintain denial/leak regression tests for all new endpoints | P0/P2 |
| 26a In-app alerts/read state | Notifications list | Derived bills/budgets/completed goals + unique read | notification_reads live | A | PARTIAL | Read retry; shared completed goal access after removal | P2 |
| 26b Email/SMS/background delivery | Absent | No scheduled jobs/mail/SMS adapters found | No delivery queue found | S | MISSING | Approve delivery scope/provider/consent before implementation | P2 |
| 27a Personal export | JSON download | Whitelisted own profile/finance/receipt/advisor fields | Existing tables live | A | PARTIAL | Former membership receipts/shared actor entries privacy matrix | P1 |
| 28a CORS/rate limit | API errors handled | Allowed origins; per-worker IP buckets | No distributed limiter store | A,S | PARTIAL | Reverse-proxy identity and multi-worker limits | P0/P3 |
| 28b Secret/upload environment | No exposed backend secrets found in inspected source | Config validation/private receipt path | MySQL TLS absent in dev | S | PARTIAL | Production secrets/TLS/storage/restore on actual host | P3 |
| 29a Brand/responsiveness | Pastel CSS, glass, fallback fonts | N/A | N/A | B four widths; screenshots | PARTIAL | Real device/a11y/contrast/font asset verification | P3 |
| 29b Common dialog keyboard | role=dialog only | N/A | N/A | S | PARTIAL | Focus trap/return, Escape and screen-reader tests | P3 |
| 30a Build/startup | Production build passes | Import/OpenAPI/lifespan/health pass | SELECT 1 + live schema verified | Executed | PARTIAL | Public deployment smoke, CI and restore drill | P3 |
| 30b Reproducible fresh database | N/A | Migrations expect existing schema | Two heads; clean baseline not demonstrated | Heads + schema inspected | PARTIAL | Disposable clean-install plan preserving legacy history | P0/P3 |

## Validation, authorization, connection and coverage matrix

This matrix makes the checklist dimensions explicit. `Yes (source)` is not execution proof. Live table verification applies to all named mapped tables; real-database mutation flows remain NOT TESTED. No PRD match can be asserted.

| Module group | Frontend/API connection | Validation/error handling | Access control evidence | Remaining execution gap |
|---|---|---|---|---|
| Public/auth/onboarding | Existing clients match registered routes; auth Node contracts pass | Strength/email/confirmation/step order; long-input DB drift | JWT tamper/expiry/suspension/admin denial tests | Full browser signup/onboarding/Google; MySQL boundary inputs |
| Accounts/transactions/transfers | Dashboard uses /accounts,/transactions,/transfers | Decimal/ownership/archive/insufficient funds/replay; FIN-02/03 failures | Own-account/transaction filters; isolation suite | Edit/move/delete matrix and concurrent MySQL writes |
| Dashboard/budgets/reports | /dashboard and /budgets; cash-flow optional payload | Period validation, scope totals, loading/error states | Personal scope; explicit household permission | Month/table supplemental checks passed; extend matching-basis reconciliation |
| Goals/reminders | Actual dedicated APIs connected | Target caps/recurrence/pay replay; FIN-01/02 failures | Owner/member and cross-user denial cases | Linked reverse operations and concurrent final contributions |
| AI/merchant | Upload fetch and advisor clients match /ai routes | Invalid image/provider failure/no-credit/schema/category/currency checks | Owned scan/chat and backend quota controls | Fresh provider calls, rule reuse matrix and full upload browser workflow |
| Household | /family and shared goal endpoints connected | Decimal splits, invitations, capacity, idempotency | Granular view/add, owner controls, revoke/removal cases | Every route permission race and actual MySQL concurrent validation |
| Subscription/demo | Public plans/current/checkout APIs connected | Server catalog, replay/expiry; production/demo guards | User checkout scope; sponsored entitlements | Enabled demo browser journey; no real processor |
| Admin | Role-guarded route + /admin APIs | Filters, status safeguards, simulated totals | Common login + backend admin-only dependency | Real operator login not performed; full action journeys remain |
| Notification/settings | /notifications,/settings connected | Derived read state, password/profile/export; old JWT failure | Own reads/exports and active-user checks | Notification UI path/full privacy export matrix |
| UI/deployment | Build imports/routes resolve; 12 feature pages rendered | Four widths no horizontal overflow; stale .00 browser assertion | Frontend guards supplement server checks | Full accessibility, real devices, TLS/public deployment, clean DB |

All pending cases and priorities map to MAXBUD_COMPLETION_ROADMAP.md. Across exactly 30 numbered module rows: 3 BROKEN, 1 MISSING, 26 PARTIAL; 0 COMPLETE. This is a verification classification, not a PRD completion percentage.
