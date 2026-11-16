# Subscription implementation — November 15, 2026

## Policy and state

New password and Google registrations create one persisted `subscriptions` row with `source=trial`, `status=trialing`, `trial_started_at`, `trial_ends_at`, and `expires_at`. Calendar arithmetic clamps month-end days: January 31 + three months = April 30. Login never resets the dates. Trial includes personal finances and per-user monthly AI limits; it cannot create a household.

Premium Individual covers one user; Family Pack covers its billing owner and one household. `FAMILY_PACK_MEMBER_LIMIT=6` includes the owner. Family members receive Individual access and individual monthly AI allowances while sponsorship is valid. Their existing paid subscriptions remain untouched. The UI explains sponsorship; there is no automatic billing or renewal, so MaxBud cannot accidentally charge twice. Existing `source=NULL` Free/Premium rows remain grandfathered; no migration rewrites their plan, expiry, role or data.

Expiration is evaluated at request time. New expired/canceled-after-period/past-due/suspended access becomes read-only unless another valid household sponsorship grants personal access. Viewing/exporting history and managing account security remain allowed. Household editing separately requires a valid Family Pack sponsor (or preserved legacy eligibility). Member removals and permission revocations remain possible after expiry. Downgrading does not erase household records.

`active`, `trialing`, `expired`, `canceled`, `past_due`, `suspended` are supported. Cancellation sets `cancel_at_period_end` and retains the existing period. No background billing worker is required: scheduled plan changes are preferences, explicitly requiring a new demo checkout at renewal. They do not silently activate or charge. Immediate successful plan changes start a new period; same-plan renewal extends the current unexpired period.

## Trusted demo checkout

`GET /subscriptions/plans` returns the public catalog; `GET /subscriptions` returns personal entitlement plus catalog. `POST /subscriptions/checkout` accepts only plan, billing_cycle and request_id. Server-owned UUID checkout, configured price, currency, 15-minute expiry and user association are persisted. `POST /subscriptions/checkout/{id}/simulate` accepts only success/failure. Ownership, expiry, terminal status, idempotency and row locks are checked; the server generates plan/period/status. Unknown fields such as amount and expiry are rejected. Failure never grants new entitlement. A replay never extends the period twice or reactivates a canceled plan.

`POST /subscriptions/cancel` schedules period-end cancellation. `POST /subscriptions/schedule` stores next-plan preference. Both operate only on the caller's demo subscription. A future real gateway should verify events before invoking entitlement changes; no gateway is connected now.

Every checkout operation requires `DEMO_PAYMENTS_ENABLED=true` and a non-production environment. Production startup also rejects demo=true. UI says **Demo Payment — No real money will be charged.** `demo_checkouts` stores simulation history; admin reports label it **SIMULATED / DEMO REVENUE** and verified real revenue remains zero.

`PLAN_PRICES_JSON` keys: `premium_individual` / `family_pack`, each with `monthly` / `yearly` nonnegative decimal-string or null values. Defaults are null, clearly shown as unconfigured; null checkout amounts are explicitly simulation-only and excluded from monetary totals. No final production prices were invented.

## Viva explanation

Billing ownership, household membership and effective access are separate concepts. One member can retain an independently purchased subscription while receiving household access. Central entitlement checks protect API writes independently of frontend state. Trial persistence and trusted checkout dates prevent client-controlled entitlement escalation.
