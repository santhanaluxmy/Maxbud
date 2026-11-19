# MaxBud — Full QA Audit and Deployment Readiness

Audit date: **18 November 2026 (Asia/Colombo)**. Repository inspected: commit `65f626b` (`Integrate Stripe subscriptions, family management, and full-stack improvements`). Application source and UI were not changed. This report is the only intended repository change.

## A. Executive summary

**NO-GO for an external beta or deployment in the current state.** There is substantial working implementation and meaningful regression coverage, but a reproduced accounting defect allows future income to fund present spending. Signed-out password recovery is blocked by the frontend API client, SMTP is unconfigured, ordinary password changes do not invalidate existing sessions, and Stripe reconciliation overrides an administrator's subscription suspension. Receipt persistence, database initialization, actual webhook delivery, and deployment configuration also remain release gates.

Evidence is deliberately separated:

- **Executed:** frontend tests, full frontend lint, production builds, backend pytest, independent API reproductions on disposable SQLite, dependency advisory queries, secret-pattern scans, and read-only MySQL/Stripe inspections.
- **Partially executed:** browser checks and canonical unittest discovery; browser registration, owner onboarding and separate-context invitation acceptance succeeded, while environment/startup failures and interrupted runs are reported separately.
- **Inspected:** active routes, clients, models, migrations, settings, entitlements, authorization, administration, AI adapters, public content, and deployment documentation.
- **NOT VERIFIED:** real Google sign-in, real SMTP delivery/reset, live Groq extraction/advice, current Stripe-to-server event delivery, actual hosted CORS/HTTPS/deep links, independent MySQL concurrency, backups/restores, and ten human beta participants.

The full pytest command finished with **237 passed, 2 failed, 0 skipped**, plus 21 successful subtests. The two failures are inherited Free-plan assertions running under a Family Pack fixture. They are genuine red-suite results, but do not demonstrate a Free-plan authorization bypass. Independent audit probes reproduced the accounting/session/control defects below; a probe that successfully reproduces a bug is not a PASS for that feature.

The requested Mathy/Yathis financial scenario **passed at API level**, with foreign keys enabled in disposable SQLite: Mathy funds 3,000; Yathis funds 2,000; Yathis spends 1,000; shared wallet = **LKR 4,000**. Shared goal contributions 300 + 200 = **LKR 500**, attributed individually. Replaying keyed writes did not duplicate these amounts. This is not a claim that the complete corresponding browser or concurrent MySQL journey passed.

### Scope and safety

No deployment, cloud configuration changes, migrations against existing MySQL, real administrator creation, new Stripe purchases, provider subscription changes, live AI requests, or changes to existing users/financial data were performed. Recovery/reset/write tests used disposable synthetic accounts only. Existing MySQL was inspected using `SET TRANSACTION READ ONLY` / `START TRANSACTION READ ONLY`, schema queries, and aggregate integrity checks, followed by rollback. Stripe inspection used **GET requests only**. Temporary scripts, databases, logs and build artifacts were placed under `/tmp`; synthetic account information was used in write tests. Credentials, tokens, invitation secrets, raw receipts, and private financial records are excluded from this report.

**Result meanings:** PASS means the specifically described executed check succeeded; FAIL means an observed defect or failed test; PARTIAL means implemented but incomplete or only partly verified; NOT VERIFIED means there is insufficient execution evidence. A code review alone does not establish an end-to-end PASS.

## B. Feature coverage matrix

FE = active frontend; BE = FastAPI; DB = mapped persistence. “Present” describes implementation, not runtime success.

| Feature | Frontend | Backend | Database | Tested | Result |
|---|---|---|---|---|---|
| Landing/navigation/FAQ/footer | Present | Public plan catalog | Catalog configuration | Source, build, five-width rendering; content discrepancies remain | PARTIAL |
| Current monthly prices | Public and upgrade cards | Canonical 650/900; price validation | Stripe mappings/subscriptions | Catalog regression + real read-only Stripe prices | PASS for prices |
| Registration/password validation | Present | Register, normalization, duplicate prevention | Users, identities, original trial | Isolated API; browser registration | PASS within tested scope |
| Password login/wrong credentials | Present | Argon2; legacy bcrypt support | Identities | API regressions; frontend tests | PASS within tested scope |
| Session expiry/protected API routes | Client expiry checks | Signed JWT, user activity/version checks | Session versions | Expired/tampered/disabled-user API cases | PASS for tested API cases |
| Logout/session revocation | Clears browser storage | No logout/revocation endpoint | Version table available | Source; old-token password-change probe | PARTIAL |
| Forgot/reset password | Public page uses authenticated client | Request/verify/reset implemented | Hashed challenge/proof, attempts, expiry | Client reproduction + mocked SMTP API tests | **FAIL** |
| Google OAuth | Google component/client ID | Token audience/verified-email checks | Google identities | Mocked verification; configuration presence only | NOT VERIFIED externally |
| Five-step onboarding | About you/income/accounts/budgets/goals | Ordered, row-locked writes | Persists each completed step | API regressions; browser five steps | PARTIAL: whitespace and navigation limits |
| Fixed-expense onboarding | No separate step | Not an onboarding module | Reminders created later | Source | PARTIAL: use later Reminders |
| Accounts/opening balances | Create/edit/archive/restore | Ownership, currency, correction guard | DECIMAL accounts | Isolated regressions | PASS for tested cases |
| Current balances/date semantics | Dashboard and accounts | All-date account balance | Dated ledger | Independent future-income reproduction | **FAIL** |
| Income/expenses | Create/view/edit/delete | Scoped CRUD; soft delete | DECIMAL transactions | API regression, correction/rollback cases | PARTIAL due date defect |
| Transfers | Dedicated transfer dialog | Atomic paired entries, keyed replay | Transfer header + unique paired legs | Isolated balance/report tests | PASS sequentially; MySQL races NOT VERIFIED |
| Categories | Transaction inputs/budget-derived choices | AI category listing; no standalone category CRUD router | Categories plus category strings | Source and scanner mocks | PARTIAL |
| Personal budgets/alerts | Create/edit/delete and progress | Scoped CRUD, normalized uniqueness | Budget scope/category uniqueness | Isolated CRUD/calculation tests | PASS for tested cases |
| Planned income sources | Onboarding capture | Saved planning inputs | Income sources | Onboarding/dashboard regressions | PARTIAL: no general post-onboarding CRUD API |
| Personal goals | Create/edit/contribute/archive | Limits, contribution ledger, status transitions | Goals/contributions | Completion/limits/retries/rollback tests | PARTIAL: keyless duplication remains |
| Shared goals | Owner manages; members contribute | Household permissions, attribution | Shared goal/contribution history | Exact 300+200 scenario and isolation tests | PASS sequentially |
| Recurring personal reminders | CRUD/payment UI | Recurrence anchor and payment replay | Reminder/payment occurrences | Recurrence/idempotency/isolation tests | PASS for tested cases |
| Notifications | In-app list/read | Computed personal/shared events | Read markers | Isolated privacy/read-state tests | PASS for tested in-app cases |
| External reminders/push/email | No general notification delivery | No scheduler/delivery service for bills | In-app persistence only | Source | PARTIAL: in-app reminders only |
| Personal reports/charts/cash flow | Implemented | Dashboard + chronological cash-flow service | Persisted ledger | Exact totals/edit/delete regressions; future-date probe | PARTIAL / **FAIL for date reconciliation** |
| Receipt upload/validation | Scanner/review/confirm | JPG/PNG, 5 MB, decoding, quotas | Scans/usage/merchant rules; local files | Mocked AI regression + source | PARTIAL; live AI NOT VERIFIED |
| Receipt duplicate confirmation | Review creates expense | Image hash and confirmed transaction replay | Linked scan/transaction | Isolated duplicate/failure/correction tests | PASS sequentially |
| Receipt persistence after cloud redeploy | No storage administration | Local private directory only | DB stores filesystem path | Source | **FAIL readiness without durable storage** |
| Advisor/history/formatting | Structured escaped multilingual rendering | Authenticated summary, bounded history | Messages and request IDs | Mocked API + rendering tests | PASS mocked; live AI NOT VERIFIED |
| AI monthly limits/reset | Usage display | 5/10 trial, 100/200 paid, UTC monthly counts | Successful scans/messages | Mocked quota/failure tests | PARTIAL: production concurrency/provider limits unverified |
| Household creation/membership | Owner/member pages | Requires owner's active Family Pack | Families/memberships | Creation/seat/permission API tests | PASS sequentially |
| Secure invitations | Link, acceptance/rejection/revocation | Email match, hashed token, seven-day expiry | Invitations | Isolated expiry/reuse/capacity tests; fresh member registration/link acceptance in separate browser | PASS for executed cases; member onboarding used API |
| Shared wallet funding | Existing personal account → wallet | Paired transfer, own source account | Explicit shared ledger | Exact 3,000/2,000/1,000 scenario | PASS sequentially |
| Shared income | Add/list | Own-family LKR wallet only | Explicit shared income | Isolation/funding-versus-income tests | PASS sequentially; no edit/delete flow |
| Shared expenses/splits | Add/list, split options | Equal/custom/percentage cent allocation | Transactions/expense shares | Rounding/privacy/replay tests | PASS sequentially; no edit/delete flow |
| Shared budgets | Owner create/edit/delete | Family-scoped writes | Scoped budgets | Family Pack regressions | PASS for tested cases |
| Household bills | Create/pay | Family permissions/payment occurrence replay | Shared reminders | Mocked/isolated bill tests | PARTIAL: no shared bill edit/delete API |
| Reimbursements | Outstanding debt/settle | Own-debt-only, transfer to payer | Shares/settlements/transfers | Partial settlement and no-double-expense tests | PASS sequentially |
| Shared activity/reports | Present | Explicit shared records only | Existing ledgers/events | Family privacy/report regressions | PASS API within tested scope |
| Member removal/permissions | Owner controls; member leave | Revokes shared access, retains history | Membership status, financial history | Existing-token/removal tests | PASS sequentially |
| Stripe Checkout | Monthly plan controls | Checkout ownership/paid invoice validation | Customer/session/subscription mapping | Mocked regressions; existing records read-only | PARTIAL; no new genuine purchase |
| Stripe webhook/reconciliation | Payment success polls reconciliation | Signature, event deduplication, authoritative fetch | Events/subscriptions | Mocked webhook/replay/out-of-order tests | PARTIAL; actual delivery NOT VERIFIED |
| Customer Portal/cancellation | Manage subscription | Portal validation, renewal/cancel reconciliation | Paid period and flags | Mocked cases; no portal session created | NOT VERIFIED with real portal |
| Admin access/user/subscription controls | Seven data modules | Current-user admin dependency | Metadata/event records | API authorization/search/privacy regressions; normal-user browser denial | PARTIAL: suspension overwritten; family statistics absent |
| Export/read-only expiry | Settings JSON export | Whitelisted own data; history retained | Existing records | Isolated expiry/export tests | PASS within tested scope |
| Hosting/deep links/backups/monitoring | Buildable SPA | Health and startup DB check | Existing local MySQL | Local checks and documentation review | NOT VERIFIED hosted |

### Architecture and actual route inventory

`frontend/src/App.jsx` owns routing. Public paths are `/`, `/login`, `/register`, `/forgot-password`; `/onboarding` requires a session. `/dashboard` requires a session plus onboarding, except admin accounts. Dashboard children: accounts, transactions, budgets, goals, reports, reminders, notifications, ai-scan, ai-advisor, settings, upgrade, payment-success, admin, family and `family/:section`. `/transactions` redirects to the dashboard route; unknown application paths redirect home. Unknown family sections are handled within FamilyPage.

The active dashboard overview is `DashboardOverview.jsx`, used by `Dashboard.jsx`; it is not dead code. The separate transaction component is also used by the dashboard. `frontend/src/config/subscription.js` has an unreferenced provisional 990/month/10,000/year offer object; active catalog prices are 650/900. Multiple `src_backup*` trees are historical duplicates, excluded from lint and not imported by the active entrypoint. Do not audit those copies as active features. Multiple authentication clients duplicate logout/session helpers and have diverging contracts, including the recovery defect.

FastAPI initialization in `backend/app/main.py` registers account, auth, recovery, billing, onboarding, transaction, dashboard, budgets, family, goals, reminders, settings, admin, AI, notifications, subscriptions and household routers. OpenAPI generation was used for the endpoint inventory; inspecting only top-level `app.routes` under the installed FastAPI version undercounts included routers.

Primary API groups:

- `/auth/register`, `/auth/login`, `/auth/google`, `/auth/me`, `/auth/recovery/{request,verify,reset}`.
- `/accounts`, `/accounts/{id}`, `/accounts/{id}/archive`, `/transfers`, `/transactions`, `/transactions/{id}`.
- `/onboarding/status` and POST about-you, income, accounts, budgets, goals; `/dashboard`, `/budgets`, `/budgets/alerts`, `/budgets/{id}`, `/goals`, `/goals/{id}`, `/goals/{id}/contribute`, `/reminders`, `/reminders/{id}`, `/reminders/{id}/pay`.
- `/family` GET/POST/PATCH, `/family/{close,leave,members,invitations,wallets,income,expenses,budgets,reimbursements,bills,participants,activity}` plus the member-permission, invitation-response/revoke, wallet-funding/archive and bill-payment endpoints.
- `/billing/stripe/{checkout,portal,reconcile,webhook}`; `/subscriptions`, `/subscriptions/plans` and separate demo checkout/simulate/cancel/schedule/resume endpoints. Demo checkout is disabled in the inspected configuration.
- `/ai/{categories,usage,advisor,receipts}`, `/ai/receipts/{id}/confirm`, `/notifications`, `/notifications/read`, `/settings/{profile,password,export}`.
- `/admin/{users,overview,subscriptions,billing,activity,ai-usage,settings}` with user/subscription PATCH controls; `/health`.

There is no refresh-token endpoint, backend logout endpoint, bank integration, standalone category management router, ownership-transfer workflow, general income-source CRUD router, shared income/expense correction API, or shared bill update/delete API. `/family/members` POST is deliberately disabled in favor of invitations; this is not a broken invitation route. No authenticated image-download/history endpoint serves stored receipt files.

## C. Complete user flow results

### Landing and public pages

Assets resolve during the production build. Navigation anchors target existing section IDs, and login/register links target real routes. FAQ buttons expose `aria-expanded`. No privacy/terms/support route was found in the active router/footer. Browser evidence, including viewport limitations, is recorded in G/I rather than inferred from JSX.

Public copy is inconsistent with implementation: FAQ says core budgeting is free and scanning is planned; paid cards still display a yearly-price line and “Explore demo plans”; the disclaimer says prices are not final; Family Pack advertises sponsored individual AI allowances that the backend intentionally does not grant. The trial actually becomes read-only after its original three-calendar-month window unless eligible access exists.

### Authentication and recovery

Registration tests verify normalized/case-insensitive email handling, duplicate rejection, password strength/matching, Argon2 storage, refusal to honor a public `role: admin`, personal trial creation without an automatic family, and rollback/no partial account on invalid input. Legacy bcrypt, corrupted hashes, wrong credentials, tampered/expired JWTs and inactive users have isolated regression coverage.

Sessions are HS256 JWTs stored in sessionStorage or localStorage when remembered. The inspected private setting specifies a **360-minute** token lifetime. There is no refresh token or rotation workflow. Client expiry cleanup and API 401 handling exist. Ordinary sign-out removes browser storage but does not invalidate a copied JWT. Password recovery increments a session version; normal Settings password change does not.

**Recovery is broken for its intended signed-out user.** `PasswordRecovery.jsx` calls `api()` from `frontend/src/api/client.js`, which throws before fetch if no token exists. Independent client execution returned `Please sign in to continue.` with **0 network calls**. Separately, SMTP is not configured; the backend explicitly returns 503 when delivery configuration is absent. Mocked backend reset tests establish challenge security, not a working public reset journey or email delivery.

Google client IDs are configured, and mocked audience/verified-email validation is tested. No real Google account or authorization-console change was used. Actual OAuth origins, credential issuance, and sign-in remain NOT VERIFIED.

### Onboarding

There are **five** steps: About you → Income → Accounts → Budgets → Goals. Income is planning data; it does not create actual income transactions. Opening balances are independently entered. Budgets are category limits, and goal contributions reserve allocations rather than transfer money. No fixed-expense onboarding step exists; bills are entered later through Reminders.

Completed steps persist with the user's current step, and repeated/out-of-order submissions return 409 instead of duplicating records. Browser registration and all five owner onboarding steps reached the dashboard in the independent browser run. There is no Back control or endpoint to revise earlier saved steps during onboarding; unsaved current-step input is component state and is not restored after reload. About-you accepts two spaces and persists an empty trimmed name, reproduced with HTTP 200.

### Personal finance

Sequential isolated tests cover account CRUD/archive, opening-balance correction, personal transaction create/edit/delete, transfer pairing/retries, budgets, goals, reminder payments, reports, reserved savings and rollback after failed writes. Linked transfer/bill/receipt transactions cannot be independently edited/deleted; this preserves links but requires a separate correction workflow which is not implemented for bills/receipts.

The future-income reproduction is a release blocker: start a zero-balance account, post income 1,000 dated 370 days ahead, then post expense 100 today. Both return 201. Dashboard balance becomes 900, while this month's cash-flow closing balance is −100 and this month's income is zero. `account_balance()` lacks an as-of date and expense checks use that all-date balance. This needs a consistent posted-versus-scheduled date policy across personal and shared writers, transfers, receipts and reports.

### AI

Receipt source implements JPG/PNG checks, a 5 MB read limit, Pillow decoding/decompression-bomb checks, EXIF normalization, resizing, safe category selection, null unreadable totals, separate calculated subtotal, review, confirmation and linked expense creation. Successful scan/advisor records drive quotas; provider failures do not consume successful-use credit. Image hashes, request IDs and confirmation links prevent the tested sequential duplicates.

Advisor input uses the authenticated personal summary and bounded prior history; the provider has no financial write tools. Rendering tests cover structured English/Tamil content and escape HTML. History is capped at 50 returned messages. Quotas use UTC calendar-month boundaries, not an explicitly configured Asia/Colombo month. Scans have no general persisted review/history retrieval endpoint: local component state may be lost on refresh, although re-uploading the same normalized image can retrieve its existing scan.

No live Groq quota was consumed. Real model availability, extraction accuracy, Tamil receipts, provider concurrency, transport failures and ten-user quota behavior remain NOT VERIFIED. Package advisories must be addressed before accepting untrusted beta uploads; MIME and dimension checks do not substitute for a patched decoder.

### Mathy owner / Yathis member

The independent API test created two synthetic trial users, directly staged a bounded Family Pack fixture for the owner (no checkout/payment), created a household/invitation, and accepted using the exact invited email. Membership became two.

| Action | Verified result |
|---|---|
| Mathy opening personal account 5,000; fund shared wallet 3,000 | Mathy personal balance 2,000 |
| Yathis opening personal account 4,000; fund wallet 2,000 | Yathis personal balance 2,000 |
| Yathis records wallet-funded groceries 1,000 | Shared wallet 4,000; expense counted once |
| Re-submit keyed funding and grocery requests | Same balances; no additional financial entries |
| Mathy shared goal allocation 300; Yathis 200; replay keys | Goal total 500 with Mathy 300 and Yathis 200 |
| Both request shared dashboard | Same 4,000 balance, zero shared income from funding, goal allocation 500 |
| Owner requests member private account; member requests owner private account | 404 in both directions |

Goals are allocations; their 500 does not reduce the wallet's 4,000. Household safe-to-spend intentionally becomes unavailable where the location of shared savings cannot be established. This is an explicit limitation rather than an invented wallet subtraction.

Existing API tests cover six seats including owner, pending invite seat reservations, invalid/revoked/expired links, accepted-link replay, exact-email match, owner-only changes, permissions, downgraded/expired sponsor, private salary isolation, split rounding, reimbursements and removal without history deletion. Sponsored members retain their own personal plan/AI allowance; they do not receive Individual Premium simply by joining.

An independent browser run additionally created the household/invitation through API fixtures, opened its fragment link in a separate 390px browser context, registered Yathis in the actual React form, completed the member's onboarding through API calls, and accepted the stored invitation in the UI. Both membership and wallet API checks succeeded. Owner registration and all five owner onboarding steps were UI-driven. Copy-to-clipboard itself, every member financial form, and immediate live synchronization were not all exercised. Shared components reload on navigation/manual refresh; there is no websocket/event stream or general polling for another member's edits. Immediate visibility on an already-open second page is NOT VERIFIED and is not guaranteed by the current update model.

### Subscriptions and admin

Actual configured Stripe monthly prices were read and validated: LKR 650 and 900, recurring monthly, active test-mode objects. Four existing mapped subscriptions were read; all were active, with no customer/user association mismatches in this check. No payment, checkout, cancellation, portal session or provider mutation was created.

Backend Checkout restricts Stripe purchases to monthly, validates exact LKR amount/interval and test mode, serializes user checkout, reuses open sessions, rejects conflicting existing subscriptions, and grants access only after a verified paid invoice. Webhook code validates raw-body HMAC/timestamp, deduplicates event IDs and fetches current provider subscription state. Mocked tests cover these behaviors, delayed activation, canceled/unpaid states, renewal, ownership and entitlement limits. They do not prove a live webhook reached this server.

The connected Stripe account returned **zero registered webhook endpoints**. Local tables contain nine stored Stripe events; these historical rows do not demonstrate current forwarding or genuine Stripe delivery. A CLI forwarding process, if one exists elsewhere, was not independently verified. No explicit portal configuration is supplied; the code can inspect Stripe's default portal configuration, so an empty variable alone does not prove the portal is broken. Its real behavior remains NOT VERIFIED.

Admin APIs enforce `role == admin` using the current database user. Isolated tests cover denied normal users/household owners, suspended admins, search/filter/offset, metadata-only lists, user suspend/reactivate, and simulated revenue labeling. No real administrator was created. Admin billing metrics remain demo-oriented: verified real revenue is hardcoded zero, billing lists demo checkouts, and explicit household/family statistics are absent. Stripe reconciliation restores a suspended subscription to active; suspension needs an independent durable policy flag if it is intended to block entitlement.

## D. Security findings

| ID | Severity / priority | Evidence and impact |
|---|---|---|
| SEC-01 | High / P1 | Ordinary password change returns 200, but an existing JWT still returns 200 from `/auth/me`; a copied session survives a password change for its remaining lifetime. |
| SEC-02 | High / P1 | Admin subscription suspension is overwritten by verified Stripe sync. Account suspension is separately enforced; this finding concerns subscription suspension. |
| SEC-03 | High exposure requiring triage / P1 | Installed Pillow 12.3.0 has current advisories; `Pillow>=11,<13` prevents adopting the reported fixed major release. Receipt parsing handles untrusted input. No exploit payload was executed. |
| SEC-04 | Moderate / P1 for public deployment | HTTP rate limits are in-memory and per worker/IP. They reset on restart, are not shared across replicas, and depend on correct trusted-proxy handling. AI quota checks separately use database user locks; those controls still require real MySQL concurrency validation. |
| SEC-05 | Moderate / P2 | JWTs live in JavaScript-readable browser storage; ordinary logout has no backend revocation. No refresh rotation, individual-session inventory or session revocation endpoint exists. |
| SEC-06 | Moderate / P2 | Public OpenAPI remains available through default `/openapi.json` even when beta/production disable the interactive docs. This reveals schema, not private data; decide the intended policy. |
| SEC-07 | Moderate / P2 | The 5 MB check occurs after multipart parsing; an edge request-body limit is still needed. Decoder CPU/memory exposure is not eliminated by the encoded byte limit. |
| SEC-08 | Moderate / P2 | No application CSP/frame-ancestor policy was found. Existing content-type/referrer headers and production HSTS are useful; hosting-level protections were NOT VERIFIED. |

Positive controls supported by review/tests: parameterized SQLAlchemy queries; bound legacy SQL; no concatenated user SQL found in app routes; explicit owner/member/user filters; admin dependency; Argon2; legacy hash compatibility; generic login errors; frontend escaping of advisor HTML; no `dangerouslySetInnerHTML` in active code; CORS restricted to configured origin in beta/production; no credentialed cross-origin cookies; invitation fragment avoids sending token in the URL request; invitation hashes; password recovery code/proof hashes, five attempts, ten-minute expiry, single use and version invalidation; Stripe raw-body signature verification; private receipt path outside webroot and restricted file permissions.

Secret-pattern scanning checked **285 tracked files**, reachable Git patch history, and generated frontend assets for common Stripe/Groq/Google private/AWS/private-key patterns. No matching credential material was found. `.env` files are untracked/ignored, and frontend environment names contain only `VITE_API_URL` and `VITE_GOOGLE_CLIENT_ID`. This is a bounded pattern scan, not a guarantee against every secret type, deleted unreachable Git object, remote branch, or deployed asset. No secret values were printed.

Dependency results are described in I. Do not interpret every package advisory as an exploitable MaxBud path: for example, Pillow's PDF/EPS-specific advisories do not automatically apply to the accepted JPG/PNG flow. PNG EXIF processing is relevant to review because the scanner calls EXIF transpose. The maintainer documents a PNG EXIF CPU issue and multiple other fixes in [Pillow 13.0.0 release notes](https://github.com/python-pillow/Pillow/blob/main/docs/releasenotes/13.0.0.rst). Review affected operations and upgrade compatibility before accepting uploads.

## E. Financial logic findings

1. **FIN-01 / P0 — future income changes present balance and spending permission.** Reproduced as detailed above. A future ledger entry funds an expense today and makes dashboard/report totals disagree. Source: `backend/app/services/account.py:54`, `backend/app/schemas/transaction.py`, transaction expense validation, dashboard/cash-flow services. Reject unsupported future posted dates or maintain scheduled entries separately; use explicit as-of balances consistently. Re-test personal/shared income, transfers, receipt confirmation and bills around date boundaries.
2. **FIN-02 / P2 — keyless contributions remain non-idempotent.** POST the same `{"amount":"10"}` twice to a personal goal without a request ID: saved amount becomes 20. This is accepted legacy behavior, covered by an existing regression; frontend keyed retries avoid it. If the API contract promises duplicate protection, require keys for all supported writers or clearly scope that promise.
3. **FIN-03 / P2 — savings edits and ledger corrections need a defined model.** Personal goal saved amount is directly editable, while contributions are retained separately. There is no general contribution reversal/correction UI/API. Shared goals correctly derive totals from their contribution history. Define baseline versus ledger adjustments so reports and audit history remain interpretable; no additional incorrect total beyond FIN-01 is claimed here.
4. **FIN-04 / P1 verification gate — real MySQL races are unverified.** Sequential SQLite passes do not prove InnoDB serialization, deadlock recovery, duplicate simultaneous requests, exhausted funds, seat reservations, or commits across two connections. Many writers use row locks and sorted account locks, but SQLite does not implement `FOR UPDATE`. Existing general tests also do not uniformly enable SQLite foreign-key enforcement; the independent Mathy/Yathis probe did.
5. **FIN-05 / P2 — date/time and history definitions need explicit policy.** DB timestamps are naive UTC; defaults use host `date.today()`; frontend date defaults use browser local time; database timezone is SYSTEM. Pin the reporting/business timezone. Cash-flow opening balances have no recorded opening date and include every account's baseline, including archived accounts. The report explains this limitation. Historical dashboard account balance is not a dated balance-sheet snapshot.

Transfers are paired and excluded from tested income/expense totals; wallet funding is a transfer rather than shared income; settlements repay shares through transfers instead of recording another expense. Goals allocate savings without moving actual account cash. Personal reports explicitly identify shared payments paid from personal accounts; the personal dashboard intentionally labels personal-only income/expenses. Do not sum personal and household expense reports without accounting for overlapping personally paid shared costs.

## F. Backend/API findings

Observed responses in disposable fixtures:

| Request/check | Observed response | Assessment |
|---|---|---|
| Future income 1,000, then today's expense 100 from zero opening balance | Both POST `/transactions` return 201; dashboard 900; month close −100 | FAIL, FIN-01 |
| PUT `/settings/password` with valid old/new passwords, then GET `/auth/me` with original JWT | 200 then 200 | FAIL session invalidation, SEC-01 |
| POST `/onboarding/about-you` with `full_name: "  "` | 200; persisted full name length zero | FAIL validation |
| POST personal goal contribution 10 twice without key | 200 twice; saved amount 20 | Accepted non-idempotent legacy path; duplicate risk |
| `billing.sync()` with suspended local Stripe subscription and active paid provider fixture | Status changes suspended → active | FAIL durable admin suspension |
| Cross-user personal account lookup in Mathy/Yathis test | 404 | PASS for these two lookups |
| Replayed keyed wallet funding/grocery/goal contributions | No duplicate totals | PASS sequentially |
| Signed-out frontend recovery action | Throws `Please sign in to continue.`; fetch count 0 | FAIL before backend request |

Additional reviewed limitations:

- Health/lifespan execute `SELECT 1`; MySQL outage prevents startup. The health route does not translate DB errors to a sanitized structured 503; it will fail through normal server-error handling. Pool pre-ping/recycle are configured. Controlled MySQL outage/recovery was not induced.
- Accounts/transactions/budgets/admin implement bounded list queries; shared income/expense/activity truncate at 100 and advisor at 50 without a complete paginated history interface. Bulk household reports load all family transactions and perform additional per-record queries. Ten-user load behavior is unverified.
- Broad exceptions generally rollback financial writes, and linked-transaction edits are guarded. Some household routes depend on session closure for rollback on exceptions and lack uniform conflict/deadlock response handling. No independent concurrent MySQL test proves these paths safe.
- Raw receipt files are stored privately but lack a deletion/retention policy, authenticated retrieval API, and orphan cleanup after an abrupt crash between filesystem and DB operations.
- Provider requests happen while DB locks/connections may be held (Groq timeout 45 seconds; Stripe timeout 20 seconds). With a pool of 5 plus 10 overflow connections, slow providers can reduce API capacity. No task queue/circuit-breaker/load result is claimed.

## G. Frontend/UX findings

Exact affected pages and reproducible issues:

- **Forgot password:** sign out, open `/forgot-password`, enter a valid address, submit. The authenticated client rejects the request locally. Expected a public recovery request. Backend SMTP must also be configured.
- **Landing `/`:** expand “Is MaxBud free?”, “Can I scan bills?” and “What is included in Premium?”; compare the actual three-month trial, live scanner implementation and separate Family Pack. Public copy contradicts the implemented product. Paid cards show a yearly line despite monthly-only checkout and misdescribe sponsored personal AI benefits.
- **Onboarding:** About you accepts spaces through the API; the frontend has no Back action. Refresh restores the step but not unsaved form data. Required income setup does not explain zero-income/irregular-income alternatives beyond available frequency choices.
- **Modal component:** generic `components/common/Modal.jsx` declares a dialog but has no Escape close handling, initial-focus management, focus trap or focus restoration. The dashboard mobile navigation implements stronger focus handling; do not assume every modal inherits that behavior.
- **Household shared transaction/bill pages:** supported creation/payment actions exist, but shared income/expense edit/delete and shared bill editing/cancellation are absent. Document intentional audit-preserving corrections rather than leave users with an uncorrectable mistake.
- **Settings/export:** available; full account deletion/retention policy UI is absent. Profile/settings do not provide general income-source management.
- **Admin:** seven modules exist, but family statistics and verified Stripe invoice/revenue views are incomplete. A normal-user denial page is implemented; API guards provide the actual security boundary.
- **Receipt review:** local component review state is vulnerable to navigation/reload; there is no scan history/reopen endpoint. Users can re-upload the same image to retrieve the deduplicated record, which is not an obvious recovery workflow.
- **Network errors:** messages tell a hosted user to check FastAPI on port 8000. Replace developer instructions with an actionable service-unavailable message for beta participants.
- **Performance:** original production build generated an approximately **852.31 kB JS chunk / 246.15 kB gzip**, 104.90 kB CSS, and three illustrated/logo assets of about 625 kB, 963 kB and 1.07 MB. Vite emitted its >500 kB chunk warning. Optimize image delivery and route splitting before relying on slow mobile networks.

Browser runs used disposable API databases and a separately built `/api` frontend. Original core harness attempts failed at readiness or Vite page load; an independent browser run reached registration, five owner onboarding steps and separate-context invitation acceptance. A later geometry sweep measured the 23 dashboard/household routes listed below at all five required widths, and a corrected focused public-page recheck measured four public pages at those widths. No page-wide horizontal overflow was measured across the resulting **135 unique route/width combinations**. Public-page rechecks found no broken completed images. Screenshots of the 360px shared-wallet page and 1440px open shared-wallet dialog were also visually inspected; the layout fitted those captures. Empty/short synthetic tables do not prove large-table or every-modal responsiveness.

| Width | Dashboard/household route measurements | Corrected public-page measurements | Page-wide overflow observed |
|---|---:|---:|---:|
| 360 px | 23 | 4 | 0 |
| 390 px | 23 | 4 | 0 |
| 768 px | 23 | 4 | 0 |
| 1024 px | 23 | 4 | 0 |
| 1440 px | 23 | 4 | 0 |

The public pages were `/`, `/login`, `/register`, `/forgot-password`. Dashboard routes were overview, accounts, transactions, budgets, goals, reports, reminders, ai-scan, ai-advisor, settings, upgrade, notifications; household overview, members, wallets, income, expenses, budgets, bills, goals, reimbursements, activity, reports. All were navigated by actual browser URLs with the real React application and isolated API. Payment-success and authenticated admin module layouts were not included in this matrix. Full keyboard accessibility, screen-reader behavior, all loading/error/toast states, all buttons and nonempty large tables remain PARTIAL or NOT VERIFIED. The final focused run also verified normal-user admin denial, recorded zero browser page errors/server 5xx/failed same-origin requests for that run, and reproduced Escape failing to close the shared-wallet modal.

## H. MySQL findings

Read-only connection succeeded to MySQL **8.0.46**. Forty tables were present and reported InnoDB. All **30 mapped application tables** and their mapped columns were present. Strict SQL mode includes STRICT_TRANS_TABLES, ONLY_FULL_GROUP_BY and zero-date restrictions. The session timezone reports SYSTEM; the business timezone is not explicitly configured by the app.

Recorded Alembic revision: **`20261117_access`**. Repository heads:

```text
20261104_accounts     (independent legacy accounts repair)
20261117_access       (maxbud_features branch)
```

The access head follows beta → shared goals → request keys → notifications → AI → reminders. The accounts repair is a separate root without an explicit dependency linking it to the feature branch. Existing database state satisfies the currently mapped columns, but this is not proof that both branch histories ran from scratch.

**A fresh empty MySQL database cannot be initialized from this migration set alone.** The legacy accounts root explicitly requires pre-existing users, accounts, financial_accounts, transactions and categories. The features root creates reminder foreign keys to existing users/accounts/transactions; later revisions alter existing goals/subscriptions/families. No complete baseline schema/migration was found in the repository. Do not run `alembic upgrade heads` blindly. A reviewed schema restore/baseline or clean baseline migration is required before Railway can start against a new DB. No migration was run in this audit.

Inspected nullability differences: generated `budgets.family_scope` is reported nullable in MySQL while the model marks it non-null; transactions.category and transactions.description are nullable in the database but non-null in the model. The generated COALESCE expression warrants different treatment from ordinary nullable fields. NUMERIC-versus-DECIMAL spellings in introspection are aliases, **not precision defects**; reviewed monetary precisions match. This was not a complete autogenerate/schema-diff or examination of every legacy trigger/check/index.

Aggregate integrity checks found:

| Check | Count |
|---|---:|
| Users with duplicate active membership rows | 0 |
| Duplicate family/user membership pairs | 0 |
| Transactions with missing referenced account | 0 |
| Transactions with missing referenced user | 0 |
| Active households above six active memberships | 0 |
| Transactions with null category / null description | 0 / 0 |
| Transfer headers without exactly two linked legs | 0 |
| Linked transfer legs whose amount differs from the header | 0 |
| Current goal contributions referencing a missing goal | 0 |

An additional read-only comparison found **no missing mapped foreign keys or mapped unique constraints** in the inspected database. The aggregate transfer checks above passed, but they do not verify every leg's account/kind/date/ownership, every account's accounting policy, or every legacy record. FamilyMembership has no model-level unique family/user pair or global active-membership constraint; locking/application checks bear responsibility for exclusivity. Family owner, subscription user, Stripe customer/subscription mappings and several financial request identifiers do have unique constraints. Additional sanitized evidence is `/tmp/maxbud-full-qa-schema-detail.json`.

Local billing summaries showed four Stripe-sourced paid subscriptions, four trials and one legacy Free subscription; five Stripe account mappings, four mapped subscription IDs and nine received-event rows. No user identifiers or private financial values were copied. Managed TLS, least-privilege grants, scheduled backups and restore reliability remain NOT VERIFIED. The local configuration has no DB TLS CA; beta/production configuration will reject that until explicitly provisioned.

`family_mysql_races.py` was not run: it creates and drops a schema, and it contains obsolete direct-member/three-seat Free-plan assumptions. It is unsuitable as current six-seat invitation-based proof. `FAMILY_TEST_MYSQL=1` rollback fixtures were not run against genuine MySQL; the user required write tests to use isolated data. Never infer race safety from those fixtures or from SQLite passes.

## I. Automated tests and evidence

Commands below ran from the stated subdirectory. Logs are temporary local audit artifacts, not committed deliverables. No unqualified historical report PASS was reused.

| Command / location | Passed | Failed | Skipped | Evidence / execution boundary |
|---|---:|---:|---:|---|
| `npm test` — frontend | 5 | 0 | 0 | Node test runner; five test files/test units, with many internal assertions; API/storage mocks and server-rendered component checks. `/tmp/maxbud-full-qa-frontend-test.log` |
| `npm run lint` — frontend | Successful exit 0 | 0 errors reported | N/A | Full configured ESLint scope; `src_backup*`/dist excluded. `/tmp/maxbud-full-qa-lint.log` |
| `npm run build` — frontend | Successful exit 0 | 0 build errors | N/A | Vite 8.3.5; large-chunk warning; original environment build. `/tmp/maxbud-full-qa-build.log` |
| `VITE_API_URL=/api VITE_BACKEND_URL='' VITE_GOOGLE_CLIENT_ID='' npm run build -- --outDir /tmp/maxbud-full-qa-dist` — frontend | Successful exit 0 | 0 | N/A | Separate browser-test artifact, no application source change. `/tmp/maxbud-full-qa-build-isolated.log` |
| `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 timeout 900 .venv/bin/python -m pytest tests -q -p no:cacheprovider` — backend | **237** | **2** | **0** | SQLite fixtures; mocked Stripe/Groq/SMTP/Google as specified by each test; 21 successful subtests, 2 warnings; 544.90 s. `/tmp/maxbud-full-qa-pytest.log` |
| `FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 timeout 180 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v` — backend | **81 completed** | 0 recorded before interruption | No final suite count | Initial sandbox attempts stalled; this retry has no final summary. A later 600-second attempt was interrupted before producing test output. Do not count either as a complete suite PASS. `/tmp/maxbud-auth-regression.log` |
| `PYTHONDONTWRITEBYTECODE=1 FAMILY_TEST_MYSQL=0 timeout 180 .venv/bin/python /tmp/maxbud_qa_probes.py` — backend | 6 reproduction checks | 0 harness assertion failures | 0 | 4.900 s, in-memory SQLite, foreign keys ON; exact family scenario plus five deliberately observed defect/legacy cases. `/tmp/maxbud-full-qa-probes.log` |
| `node /tmp/maxbud_qa_recovery.mjs` — independent signed-out recovery-client probe | Bug reproduced | Feature FAIL | 0 | `Please sign in to continue.`, fetch count 0. `/tmp/maxbud-full-qa-recovery-client.log` |
| `PYTHONDONTWRITEBYTECODE=1 timeout 300 .venv/bin/python /tmp/maxbud_qa_browser_direct.py` — backend | 4 journey milestones plus fixture checks | Later layout-selector harness timeout | N/A | Registration + owner UI onboarding, direct-route protection, separate-context invite registration/acceptance; member onboarding/API fixtures explicitly distinguished. `/tmp/maxbud-full-qa-browser-direct-final.log` |
| `PYTHONDONTWRITEBYTECODE=1 timeout 300 .venv/bin/python /tmp/maxbud_qa_layouts.py` — backend | 115 dashboard/household geometry measurements | Initial public-page harness issues; later admin-heading harness timeout | N/A | Synthetic records, real browser/API; initial proxy URL-decoding/hidden-heading defects excluded and rechecked. `/tmp/maxbud-full-qa-layouts.log` |
| `PYTHONDONTWRITEBYTECODE=1 timeout 180 .venv/bin/python /tmp/maxbud_qa_layouts.py --public-only` — backend | 20 public geometry measurements; normal-user admin denial | 1 product keyboard defect reproduced | N/A | Final run completed; zero page JS errors, 5xx or failed same-origin requests; Escape leaves dialog open. `/tmp/maxbud-full-qa-layouts-public-final.log` |
| Backend import/OpenAPI generation | Successful | 0 | N/A | Installed Python 3.12.3; actual route/schema generation completed. `/tmp/maxbud-full-qa-route-inventory.json` |
| Read-only MySQL and Stripe inspection script | Successful | 0 inspection errors after network retry | N/A | `/tmp/maxbud-full-qa-inspect.jsonl`; no provider mutations or DB writes |
| `PYTHONDONTWRITEBYTECODE=1 timeout 45 .venv/bin/python /tmp/maxbud_qa_schema_detail.py` — backend | Successful exit 0 | 0 missing mapped FK/unique constraints; aggregate checks zero | N/A | Read-only MySQL; `/tmp/maxbud-full-qa-schema-detail.json` |

### Exact pytest failures

```text
FAILED tests/test_shared_family.py::SharedFamilyTests::test_free_limit
AssertionError: 201 != 403

FAILED tests/test_shared_family.py::SharedFamilyTests::test_registration_overview_and_refresh
('family_pack', 'LKR', 'owner', 6, 5)
!= ('free', 'LKR', 'owner', 0, 0)

2 failed, 237 passed, 2 warnings, 21 subtests passed in 544.90s
```

`SharedFamilyTests` inherits `FamilyTests` and its setup enables Family Pack. Pytest collects inherited Free-plan tests as well. The module's `load_tests` function filters intended methods for unittest, but pytest does not use that filter. Fix fixture/class collection and rerun both supported runners. Do not “fix” permissions to satisfy the contradictory fixtures.

### Browser attempts and limitations

- Existing `tests/core_flow_browser.py`: initial attempt hit sandbox localhost bind EPERM. An approved rerun started Vite but failed health readiness with ECONNREFUSED. Another temporary harness enabled only disposable SQLite performance pragmas/longer readiness; it reached page navigation but timed out after 15 s waiting for Vite `/register` to load. These are **harness/environment failures**, not proof of a broken registration endpoint.
- A temporary runner tried core, auth, Stripe, Family Pack and improvements browser suites against the isolated static build/proxy. Core/auth readiness failed; subsequent execution was interrupted before a complete suite summary. Do not claim those suites passed or that their planned assertions executed.
- An independent single-process disposable API/static-server browser harness verified signed-out direct URL redirection, real React registration, all five owner onboarding steps, separate-browser member registration from an invitation link, and UI invitation acceptance after API-driven member onboarding. The subsequent layout loop incorrectly waited for a `main` element on every page, causing a harness timeout on public auth layouts; it did not invalidate the already completed journey checks. Temporary proxy BrokenPipe errors occurred during navigation and are not attributed to the app without a product reproduction.
- The dedicated layout sweep finished its five-width measurements. Initial mobile auth timeouts came from waiting for a hidden left-panel heading; the initial apparent broken public images came from the temporary proxy failing to URL-decode the asset filename. Only temporary harness code was corrected. The focused recheck passed all 20 public route/width combinations. A final selector correction allowed the admin denial page (an alert without a heading) to be checked; the public recheck, modal Escape check and normal-user admin denial then completed. Full dashboard console cleanliness was not captured by the earlier run's aborted summary; the focused run's diagnostics are recorded separately above. JSON geometry evidence is `/tmp/maxbud-full-qa-responsive.json` and `/tmp/maxbud-full-qa-responsive-public.json`; screenshots are `/tmp/maxbud-full-qa-mobile.png` and `/tmp/maxbud-full-qa-modal.png`.
- Existing browser scripts that operate on the marked pre-existing local family sandbox were intentionally not used for writes. Live-Groq scripts and unreviewed older demo harnesses were not used as evidence of external services.

### Dependency and secret scans

`npm audit --json` first failed sandbox DNS; the read-only approved retry completed with **8 affected dependency entries: 5 high, 3 moderate, 0 critical**. These include inherited dependency nodes, not eight independent exploitable application bugs. Reported chain: picomatch → fdir/tinyglobby → Vite/plugin-react; minimatch → ESLint/config-array. Direct advisories include [picomatch ReDoS](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) and [minimatch glob amplification](https://github.com/advisories/GHSA-g3hv-75wg-m249). These are principally build/dev-tool dependencies in this static deployment. Do not run `npm audit fix --force` blindly: the suggested Vite downgrade can conflict with the current plugin/runtime setup. No dependency was changed.

`pip-audit` was not installed. A read-only audit queried official PyPI release JSON for all **60 installed distributions**; after the approved DNS retry, all 60 queries completed without errors. Four distributions had advisory entries: **dnspython 2.9.0**, **opentelemetry-api 1.45.1**, **Pillow 12.3.0**, and **pip 24.0**. Some PyPI entries duplicate GHSA/PYSEC aliases. The results are advisory metadata, not exploit verification or a substitute for assessing deployed dependencies. PyPI lists fixes including dnspython 2.9.2, opentelemetry-api 1.45.2, Pillow 13.0.0, and pip updates depending on the advisory. [PyPI release API](https://docs.pypi.org/api/json/) explains the release vulnerability metadata. Full local metadata is in `/tmp/maxbud-full-qa-pypi-audit.json`.

Secret scan: no matched common secret patterns in tracked working files, reachable history patches or built assets. Details and limitations are in D; `/tmp/maxbud-full-qa-secrets.jsonl` contains only findings/variable names, not credentials.

## J. Deployment readiness

**Recommended after blockers are fixed: Option A, Vercel frontend + Railway FastAPI + persistent MySQL with verified TLS.** This fits the existing static Vite frontend and long-running FastAPI/storage needs. It is a recommendation based on the architecture, not a deployment approval or verified hosted result. Railway can host MySQL; the actual selected service must satisfy this app's certificate/hostname verification requirements rather than assume default connectivity is enough.

| Concern | Option A: Vercel FE / Railway API + DB | Option B: Railway FE + API + DB |
|---|---|---|
| Fit for existing Vite SPA | Direct static build/output deployment | Needs a configured static web service/container |
| FastAPI/Groq | Railway persistent ASGI process | Same |
| Receipt files | Railway API volume or private object storage required | Same; putting FE on Railway does not persist API files |
| Frontend routing | Explicit SPA fallback/deep-link configuration | Static-server fallback configuration needed |
| API URL/CORS | Two public origins; build-time HTTPS API URL and exact CORS | Also two origins unless reverse proxy is added |
| Operational work for 10 users | Static FE hosting plus API/DB/storage | Additional static service configuration/monitoring |
| Current repository ready as-is? | No | No |

### Concrete configuration and release work required

1. **Repository/service roots:** set frontend root `frontend`, backend root `backend`. No committed Dockerfile, Procfile, Railway configuration, Vercel rewrite file or runtime version pin was found. Git remote hosting/access and cloud project configuration were not changed or verified.
2. **Frontend build:** `npm ci` then `npm run build`, output `dist`. Existing local tools were Node **24.19.0** and Vite **8.3.5**. Pin a supported Node version and preserve a reviewed lockfile. Set `VITE_API_URL=https://<actual-api-host>` and optional matching `VITE_GOOGLE_CLIENT_ID` at build time. Do not set DB, Groq, SMTP, Stripe private or JWT secrets in any VITE variable. Existing local frontend URL values must not be copied into a public build.
3. **SPA routing:** configure fallback to `/index.html` for application paths. With an absolute API origin, the usual Vercel rewrite `{"source":"/(.*)","destination":"/index.html"}` is appropriate for frontend routes. If retaining `/api`, configure its API proxy rewrite **before** the SPA catch-all. Vite's development/preview proxy is not the production hosting configuration. [Vercel's Vite guide](https://vercel.com/docs/frameworks/frontend/vite) explicitly requires SPA deep-link configuration.
4. **Backend runtime/start:** install reviewed backend requirements, pin Python (3.12 was tested), start `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1` from `backend`. Configure `/health` with adequate start timeout. Avoid `--reload` publicly. Railway requires correct public binding/port; see [its FastAPI deployment guide](https://railway.com/guides/fastapi).
5. **Environment:** use `ENVIRONMENT=beta` for this explicitly sandbox-only beta, `DEMO_PAYMENTS_ENABLED=false`, `RATE_LIMIT_ENABLED=true`, a strong private JWT secret, bounded session lifetime, and exact HTTPS `FRONTEND_ORIGIN`. Production intentionally rejects sandbox/demo entitlement, so simply switching to production will remove sandbox paid permissions. This is a current product constraint, not something to bypass.
6. **Database:** supply DB_HOST/PORT/USER/PASSWORD/NAME and a readable DB_SSL_CA file with verified certificate identity. Map provider MYSQL* variables to the app's DB_* names; DATABASE_URL/MYSQL_URL are not automatically consumed. A CA path without a real mounted certificate is insufficient. Rehearse the full schema restore/baseline on isolated MySQL; then apply reviewed additive migrations. Current feature head is **20261117_access**, not the stale 20261115_beta mentioned in deployment docs. Do not run destructive repair/root migrations against user data.
7. **Migration execution:** choose one controlled operator/pre-deploy operation, not every worker on startup. [Railway pre-deploy commands](https://docs.railway.com/deployments/pre-deploy-command) support migrations, but their filesystem changes do not persist and volumes are not mounted there. Keep filesystem initialization separate. A reviewed existing-schema command is `alembic upgrade maxbud_features@head`; this does not initialize an empty database and was not run here.
8. **Private receipt storage:** mount durable storage at an explicit private path and set RECEIPT_STORAGE_DIR accordingly, or implement a private object-store adapter. The current BASE_DIR/private_receipts path is deployment-local and can disappear. Ensure DB and storage backup retention are coordinated, paths fit the 255-character DB field, files retain private permissions, and multi-replica access is designed. [Railway volumes](https://docs.railway.com/volumes) are the relevant persistence mechanism for a single API instance; object storage is preferable when scaling across instances.
9. **Stripe:** keep test keys only. Configure the public HTTPS `/billing/stripe/webhook` endpoint, required supported subscription/checkout/invoice events and the signing secret for that actual endpoint/environment. CLI forwarding secrets and hosted endpoint secrets are not interchangeable. Verify delivery without assuming nine old DB events prove it. Reconciliation is a recovery mechanism, not evidence of webhook health. Verify default/explicit portal configuration, disable unsupported plan switching, ensure period-end cancellation is configured and exercise the permitted lifecycle on dedicated sandbox fixtures only with approval for new purchases. [Stripe webhook management](https://docs.stripe.com/events/manage-webhook-endpoints) covers signature/delivery verification.
10. **Google/SMTP:** set matching actual frontend authorized origins/client IDs; the existing ID-token flow is not a custom backend redirect exchange. Configure authenticated TLS SMTP and test signed-out reset after correcting the client. Verify real email delivery, abuse limits and old-session invalidation without sending to real accounts unnecessarily.
11. **Groq:** confirm current model availability/account quotas, data disclosure and provider spend limits; account/model limits are separate from MaxBud per-user credits. Ten paid users could be entitled to 1,000 scans and 2,000 advisor messages monthly if each has a paid personal plan; this does not prove the provider can sustain concurrent usage. Review [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits); perform a bounded approved staging test later, not speculative live consumption now.
12. **Reliability/security:** one worker initially because of the per-worker limiter; trusted forwarded-header/proxy configuration; ingress body/time limits; HTTPS; appropriate security headers; patched image dependencies; sanitized logs without request bodies/tokens; request IDs and alerts for 5xx, DB/pool pressure, Stripe delivery failures, AI failures, storage capacity and failed backups. No monitoring integration was found or exercised.
13. **Backup/restore:** define scheduled encrypted DB backups and receipt-storage backups, retention, restore owner, RPO/RTO, and verify a complete restore into a separate database/storage path. Code/documentation is not a successful restore. [Railway MySQL documentation](https://docs.railway.com/databases/mysql) describes backup/PITR capabilities; actual enablement and recovery were not verified.
14. **Staging acceptance:** use correct HTTPS origins; test direct refresh of dashboard/family/payment-success routes; cross-origin authorized/denied CORS; mobile devices at all requested widths; real email/OAuth; approved Stripe delivery; provider failure behavior; isolated MySQL races; and ten consenting beta participants. Only then consider exposure outside the developer machine.

Locally working assumptions that break on hosting: localhost API URLs; relying on Vite proxy in a static deployment; backend default loopback/port command; missing SPA rewrites; local MySQL hostname/credentials; missing TLS CA; absent fresh schema; image paths on ephemeral disk; localhost Google origins; CLI-only Stripe forwarding; per-worker rate limits treated as global limits; missing SMTP; and sandbox entitlements rejected under production mode.

## K. Prioritized bug list

The table gives reproduction, expected/actual behavior, affected files and a concrete suggested fix. P0 = financial/security release blocker; P1 = must fix/verify before external beta; P2 = important UX/reliability; P3 = later improvement. NOT VERIFIED release gates are explicitly distinguished from reproduced bugs.

| ID / priority | Exact problem and reproduction | Expected / actual | Files or endpoint | Suggested fix |
|---|---|---|---|---|
| FIN-01 **P0** | Zero account → future income 1,000 → today expense 100 → dashboard/report | Future scheduled income cannot fund today; actual 201/201, balance 900 versus month closing −100 | services/account.py; schemas/transaction.py; routers/transaction.py; dashboard/cash_flow | Reject unsupported future posted dates or separate scheduled transactions; use as-of accounting consistently; add meaningful date-boundary regressions |
| AUTH-01 **P1** | Sign out → Forgot password → submit address | Public recovery request; actual client rejects before fetch | PasswordRecovery.jsx; api/client.js | Use a public JSON client for all three recovery endpoints with safe error handling; browser-test signed-out reset |
| AUTH-02 **P1** | Inspect SMTP config / call recovery on configured app | Deliver eligible user's reset code; currently SMTP absent and endpoint returns configured-unavailable 503 | core/config.py; services/recovery.py | Provision SMTP through secret manager; verify delivery and failure reporting on dedicated account |
| SEC-01 **P1** | Change password then reuse original JWT | Prior sessions invalidated according to explicit policy; actual original JWT remains valid | routers/settings.py:34; core/security.py; access SessionVersion | Increment durable session version on ordinary password change; force safe re-authentication and test copied token |
| SEC-02 **P1** | Suspend Stripe subscription locally then reconcile paid provider state | Administrative restriction remains; actual becomes active | routers/admin.py:94; routers/billing.py:95 | Separate operator suspension from provider billing state; enforce both in entitlement; audit actions |
| DEP-01 **P1** | Inspect installed dependencies and run advisory queries | Reviewed patched dependency set; actual npm 8 affected entries, Python 4 distributions | requirements.txt; package-lock.json | Triage runtime reachability, especially Pillow; upgrade compatible patched releases and review upper bounds; rerun upload/build tests |
| DB-01 **P1** | Provision empty MySQL then inspect planned Alembic roots | Reproducible initialization; actual roots require pre-existing legacy/current tables | migrations/versions; migrations/env.py; deployment docs | Reviewed baseline/schema restore and isolated migration rehearsal; explicit branch strategy |
| DEPLOY-01 **P1** | Build/redeploy API using default receipt path | Existing receipt images remain durable; no volume/object adapter is configured in repo | core/config.py; routers/ai.py | Private durable storage + backup/restore; verify redeploy persistence |
| BILL-01 **P1 verification gate** | GET current sandbox webhook endpoints | Public endpoint/event delivery verified; actual list is empty; historical events exist | Stripe configuration; /billing/stripe/webhook | Register correct hosted test endpoint later, configure its secret/events, verify real delivery with dedicated approved scenario |
| DEPLOY-02 **P1** | Attempt static SPA deep link/production API config as currently documented | Host-ready routing/ASGI/env/TLS; repo lacks deployment config; defaults local | App.jsx; vite.config.js; database.py; config.py | Implement and review J's build/start/rewrite/env/TLS requirements before deployment |
| QA-01 **P1 verification gate** | Run isolated multi-connection MySQL financial/seat/replay cases | Proven conservation/isolation under contention; no safe current test execution | tests/family_mysql_races.py; finance/family writers | Replace obsolete race fixture with dedicated isolated MySQL tests; never point write suites at genuine accounts |
| QA-02 **P1** | Run pytest tests | Green coherent collection; actual 237 pass / 2 inherited-fixture fails | tests/test_shared_family.py; test_family.py | Remove contradictory inherited collection or isolate fixture classes; retain real Free/Family assertions |
| UX-01 **P2** | Read landing FAQ/prices/sponsored AI claims | Accurate trial/scanner/monthly/sponsorship descriptions; actual contradictory stale copy | landingpage/LandingPage.jsx; unused config/subscription.js | Update copy to canonical plan semantics; remove stale yearly/demo offers |
| UX-02 **P2** | Keyboard-open generic dialog, press Escape/tab | Focus enters/stays/returns and Escape closes; handlers absent | components/common/Modal.jsx | Shared accessible modal behavior; test focus/Escape on real forms |
| UX-03 **P2** | Onboarding about-you full_name two spaces; attempt Back/current-step reload | Valid trimmed name and clear navigation; actual empty saved name, no Back, draft lost | schemas/onboarding.py; routers/onboarding.py; Onboarding.jsx | Trim before min-length validation; deliberate step-edit/draft-resume design |
| FIN-02 **P2** | Repeat personal contribution without request ID | Defined retry semantics; actual two allocations | routers/goals.py; schemas/account.py; transaction idempotency contract | Require keys where duplicate protection is promised; document legacy contract otherwise |
| UX-04 **P2** | Enter mistaken shared expense/income/bill or confirmed receipt | Audited correction supported; no general correction endpoints | routers/household.py; routers/ai.py; family UI | Add authorized reversal/amendment flows that retain history and reconcile dependencies |
| UX-05 **P2** | Leave second household browser open while first adds data | Clear refresh/current-state behavior; no push or general automatic synchronization | family components; SubscriptionProvider.jsx | Add explicit refresh/stale indicators or bounded invalidation/polling; test two contexts |
| OPS-01 **P2** | Restart/scale worker or apply traffic through proxy | Consistent rate limits/failure handling; currently worker-local/IP based | core/rate_limit.py; main.py | Trusted proxy configuration, shared/edge limits, explicit health 503 and recovery/load tests |
| ADMIN-01 **P2** | Inspect billing/family metrics | Accurate supported beta metrics; billing is demo-only, family stats absent | routers/admin.py; Admin.jsx | Add useful household and sandbox-invoice metrics with correct labels and privacy controls |
| UX-06 **P2** | Refresh receipt review/history; slow mobile first load | Recoverable review state and reasonable assets; no history API, large bundle/images | AI.jsx; routers/ai.py; assets; App.jsx | Scan recovery/history plus route splitting/image compression without redesign |
| PRIV-01 **P2** | Follow footer for privacy/terms/support/data retention | Clear disclosures/contact/retention policy; no routes found | App.jsx; landing footer; deployment operations | Publish accurate data/provider/storage/retention/support information before collecting sensitive beta data |
| ARCH-01 **P3** | Browse source/docs and compare current catalog/migrations | One current contract; duplicate backups/auth helpers and stale deployment claims | src_backup*; auth clients; README/DEPLOYMENT_GUIDE | Archive unused copies safely later, consolidate clients, update operational docs |

## L. Final Go / No-Go decision

| Intended release | Verdict | Conditions / reasoning |
|---|---|---|
| Local developer demo | **Conditional GO for a supervised demonstration** | Use disposable/manual test data, current/past dates, and disclose mocked/unconfigured recovery, providers and payments. This is not certification that all financial inputs are correct. |
| Ten-user external beta | **NO-GO** | Fix FIN-01, public recovery and session/control defects; patch/triage dependencies; validate isolated MySQL concurrency; complete actual browser/mobile and provider acceptance. |
| Railway/Vercel deployment | **NO-GO as-is** | Missing initialization baseline, durable receipt storage, host routing/start/env/TLS configuration, actual webhook setup and backup/restore evidence. No deployment was performed. |
| Production financial application | **NO-GO** | Accounting blocker, unresolved security/reliability controls and broad external verification gaps. Billing intentionally supports sandbox access only and rejects it in production. |

## M. Recommended fix order

1. **Accounting correctness:** resolve future-versus-posted dates, reconcile dashboard/monthly/account totals, and lock down tests for spending/transfer/bill/receipt behavior around date boundaries. Preserve existing histories and avoid retroactive silent financial rewrites.
2. **Account access and administrative controls:** public recovery client, SMTP, normal password-change session invalidation, durable subscription suspension, and explicit logout/session policy. Re-test signed-out, copied-token, disabled-user and ordinary-member access.
3. **Untrusted input/dependencies:** assess applicable Pillow advisories, adopt patched compatible versions, tighten/pin reproducible dependencies, and enforce ingress upload limits. Keep decoder and quota failure tests; do not use dangerous exploit files against the real service.
4. **Database and financial concurrency:** define a reproducible baseline, rehearse migrations/restore on isolated MySQL, resolve material nullable-field differences without damaging legacy records, then prove simultaneous balance/transfer/reimbursement/contribution/seat behavior on dedicated accounts.
5. **Hosting/storage/billing configuration:** choose Option A, prepare concrete reviewed root/build/start/SPA/env/TLS/volume configuration, backups, health/monitoring and a correct sandbox webhook/portal setup. Keep deployment as a separately authorized future action.
6. **User-facing completeness:** align landing/pricing claims, improve accessible dialogs and onboarding recovery, add clearly audited shared-finance correction flows, scan resumption and accurate administration/notification descriptions. Preserve the existing brand/design.
7. **Release validation:** repair test collection; rerun appropriate backend/frontend/browser suites, five-width checks and complete two-browser invitation/owner/member journeys. Verify real OAuth/SMTP/Groq and approved Stripe delivery separately from mocks. Rehearse restore; then invite ten consenting users with dedicated test data and a clear issue/rollback process.

This audit provides evidence for a fix plan, not deployment authorization. A green mocked test suite alone will not close the external-service, storage, concurrency and real-user acceptance gates.
