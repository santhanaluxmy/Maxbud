# Local Family Pack testing without payment

## 1. Grant temporary access

Use a private terminal, from the project root. The backend configuration must already be valid and use `development` or `test`; beta and production are rejected. Do not change production configuration to run this tool.

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/local_family_test.py init --apply
PYTHONPATH=. .venv/bin/python scripts/local_family_test.py grant --email family-owner@maxbud.example.com --hours 24 --apply
PYTHONPATH=. .venv/bin/python scripts/local_family_test.py status
```

Initialization requires typing `CREATE LOCAL TEST DATABASE` and choosing a NEW test-only password. Six synthetic accounts share this initial password. Grant requires typing the exact owner email and privately entering its password. Without `--apply`, init/grant/revoke only preview. Expiry is mandatory, from 1 to 168 hours; grant again explicitly to renew.

The tool creates only `backend/.local-family-test/`, a private, ignored SQLite database and separate signing key. It refuses an existing directory during init, has no reset command, accepts no external database URL, and never opens MySQL. Only the fixed synthetic owner can be granted access. Test grants have source `test_access`, an expiry, and a TEST ACCESS / payment=false audit event. No checkout or payment record is created. There is no public grant endpoint.

## 2. Log in with six users

Keep the sandbox API running in the backend terminal:

```bash
PYTHONPATH=. .venv/bin/python scripts/local_family_test.py serve
```

In a second terminal, from the project root:

```bash
cd frontend
VITE_API_URL= VITE_BACKEND_URL= VITE_GOOGLE_CLIENT_ID= API_PROXY_TARGET=http://127.0.0.1:8011 npm run dev -- --host 127.0.0.1 --port 5184 --strictPort
```

Open **http://127.0.0.1:5184**. Use six separate browser profiles or isolated browser contexts. Some incognito windows share storage; verify the displayed signed-in email in each. Use the password chosen at initialization:

| Role | Email |
|---|---|
| Owner | family-owner@maxbud.example.com |
| Member 1 | roommate1@maxbud.example.com |
| Member 2 | roommate2@maxbud.example.com |
| Member 3 | roommate3@maxbud.example.com |
| Member 4 | roommate4@maxbud.example.com |
| Member 5 | roommate5@maxbud.example.com |

Complete onboarding separately for each person. These accounts start Free, with no financial records. Granting changes only the owner; accepted members receive configured shared permissions; personal entitlements remain independent. Demo checkout is disabled. Google login and paid AI providers are disabled in this sandbox process. Normal backend authorization still applies. Keep all test data synthetic.

## 3. Screen checklist

| Screen/area | Check |
|---|---|
| Subscription | Owner sees Family Pack, TEST ACCESS, expiry and no real payment. Accepted members see sponsored permissions; their billing subscription stays Free. |
| Family Management | Owner creates a household, then invites the five member emails. Copy each link privately to the matching signed-in profile. Accept, confirm six active members and zero remaining seats; a seventh invitation must fail. |
| Invitations | Wrong account must fail. Revoking a pending invitation blocks acceptance. **No automatic email delivery exists**; this tests email-bound invitation links. After onboarding, return to Family Management/the link to accept. |
| Personal accounts/income/expenses | Add distinct private records for each user. Owner and other members must not see another person's balances, account names, income or expenses. |
| Shared wallets/contributions | Create a shared wallet. Fund 20,000 and 30,000 from two personal accounts, then spend 8,000: shared balance 42,000. Funding must reduce personal cash and must not become genuine household income. |
| Shared income/expenses | Add genuine shared income separately. Confirm actor, amount, category and balance updates for every permitted member. Private salaries must not appear here. |
| Expense splitting | Record 50,000 paid by one person and split across five selected people: 10,000 each, including the payer. Confirm only the other four owe the payer. |
| Reimbursements | Settle one 10,000 debt partially by 2,000, then fully by 8,000. Outstanding debt should fall to 8,000 then zero, without creating another household expense. |
| Shared budgets | Set 20,000 category budget and spend 12,000 in the same month/category: 8,000 remaining, consistent for all permitted members. |
| Shared goals | Owner creates a goal; two members allocate 300 and 200. Progress/history should show 500 with correct actors. Goal allocation does not transfer wallet cash or create income. |
| Personal Reports | Confirm only the signed-in user's transactions, month totals and running balance; shared transactions must stay separate. |
| Family financial report / Shared overview | Confirm household income, expenses, wallet balance and funding totals; no private account details. Detailed dated shared monthly cash-flow report is currently missing. |
| Permissions/removal | Disable one member's shared editing/reports, then remove that member. Reuse the existing session to confirm access is denied; personal records and historical shared records remain. Restore/join only through the existing invitation flow. |
| Expiry/revocation | Refresh all profiles: shared editing locks while household/history remain. Personal entitlements stay unchanged; sponsored shared editing ends. Check Premium limits again; ordinary Free personal editing remains available within its limits. |

## 4. Revoke safely

From `backend`, while the sandbox server may remain running:

```bash
PYTHONPATH=. .venv/bin/python scripts/local_family_test.py revoke --email family-owner@maxbud.example.com --apply
PYTHONPATH=. .venv/bin/python scripts/local_family_test.py status
```

Confirm the owner's email and test password again. This restores only the known sandbox Free baseline, records a test revocation event and preserves users, households, memberships and financial history. Existing tokens lose shared write authorization immediately on the next request; refresh the UI. Expiry also locks access automatically. Stop both local servers with Ctrl+C when finished; the sandbox persists for later inspection.

## 5. Verification scope and gaps

Automated local-access tests cover private fresh initialization, intended-account confirmation/password, expiry bounds, environment guards, refusal to overwrite other subscription sources, five sponsored members, sixth additional member rejection, disabled demo checkout, immediate revocation using existing tokens, retained history and absence of a public grant endpoint. The browser harness is `backend/tests/local_family_browser.py`; it uses disposable SQLite and six isolated browser contexts.

Remaining product gaps: Stripe/real billing; actual invitation email delivery; smooth invitation return after signup/onboarding; shared dated monthly cash-flow report; wallet funding and reimbursement history screens; auditable shared transaction corrections. Shared overview totals and personal reports already exist. Do not treat the missing features as passing manual checks. No production/MySQL concurrency validation is implied by these SQLite tests. Existing MySQL data, real accounts, production settings and payment controls are not changed.
