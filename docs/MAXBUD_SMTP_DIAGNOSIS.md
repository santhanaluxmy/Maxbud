# Family Invitation SMTP diagnosis and fix

## Result

Real Gmail SMTP authentication and real invitation submission succeeded. Credentials were neither printed nor replaced. Inbox receipt and recipient acceptance are separate, and were not confirmed at the time of this report.

The latest authorized recipient is `santhanaluxmy20@gmail.com`. Gmail accepted the actual MaxBud invitation for that address using the real configured account. This was not a mocked email test.

## Root-cause findings and confidence

A confirmed implementation defect was that invitation mail read `get_settings()`, which is globally cached with `lru_cache`. Looking up that object again does not reload an edited `.env`; a running worker could therefore keep obsolete SMTP credentials or a previous public URL after an operator updated the file. The fix removes that stale-settings path for invitation email. A regression test now changes a synthetic credential file between reads and verifies that the email settings update while the application's shared settings cache remains untouched.

The historical 535 response cannot be uniquely attributed to a particular old credential or account state because those secret values were deliberately not logged. It would be incorrect to conclude that the current App Password is wrong. With the current file, both an independent Python standard-library SMTP client and the application's actual invitation sender authenticated successfully. No credential reset was required during this task.

Separate runtime finding: neither FastAPI nor Vite was listening when diagnosis began. They were started using the existing application configuration. The frontend was started using its actual installed Node executable. No application designs or financial behavior were changed.

## Configuration and protocol verification

| Check | Result |
| --- | --- |
| Canonical settings file | PASS — absolute `backend/.env` path |
| Parsed settings versus dotenv values | PASS — SMTP host, port, security, username, password, sender and public URL matched |
| Running FastAPI worker | PASS — worker started after the dotenv update; correct backend directory |
| Exported SMTP environment overrides | PASS — none in the live worker |
| Username and sender | PASS — valid address format and matching configured sender/account |
| Password parsing | PASS — formatting spaces normalize to a valid-length ASCII app-password string; no literal quote edges, hidden formatting characters or non-ASCII characters |
| Port/security | PASS — `smtp.gmail.com:587`, STARTTLS |
| Protocol sequence | PASS — EHLO `250` → STARTTLS `220` → EHLO `250` → authentication `235` |
| TLS | PASS — certificate-verified TLS 1.3 |
| Actual Google account/App Password pair | PASS — verified by Gmail authentication, rather than inferred from the sender field |

The supported Gmail configuration agrees with [Google's SMTP settings](https://support.google.com/mail/answer/7104828?hl=en). Google documents the account-specific nature of app passwords and their revocation after an account password change in [App Password help](https://support.google.com/accounts/answer/185833?hl=en).

## Exact fixes

1. Invitation email now reads the canonical settings sources when it is used. It does not clear or alter the global configuration cache used by authentication, the database engine or billing. SMTP environment-variable precedence is preserved.
2. Settings validation failures become a safe 503 error; validation input containing credentials is not returned or logged through the invitation endpoint.
3. A failed resend restores the previous invitation token hash and expiry when the same pending attempt still owns them. The existing invitation link remains valid after an authentication failure. No invitation row is deleted or duplicated.
4. Email audit events record only bounded error types and SMTP status codes, rather than provider responses or credentials. Authentication error guidance refers to the Google account/credential pair instead of asserting that the App Password alone is incorrect.
5. `PUBLIC_FRONTEND_URL` was updated to the newly generated and verified temporary HTTPS tunnel address. No SMTP credential field was changed.

## Real email results

### First recipient, previously authorized

- Recipient: `shayan@gmail.com`.
- Reused existing pending invitation **44**; zero invitation rows added.
- Authentication: **PASS**, `235`, response `2.7.0 Accepted`.
- Message submission: **PASS**, `250`, response `2.0.0 OK 1795062048 d2e1a72fcca58-8c5ca7aaaccsm2079794b3a.11 - gsmtp`.
- Public HTTPS invitation preview: **PASS** for the correct recipient and pending invitation.
- Record count, invitation identity, permissions and creation date: **PASS**, preserved.

### Replacement recipient explicitly requested by the user

- Recipient: `santhanaluxmy20@gmail.com`.
- No pending invitation existed for this address. The normal invitation handler created exactly one unique invitation, **45**, under the authorized household. The Shayan invitation remained intact.
- Authentication: **PASS**, `235`, response `2.7.0 Accepted`.
- Message submission: **PASS**, `250`, response `2.0.0 OK 1795062793 5a478bee46e88-382a6304ff2sm12879190eec.6 - gsmtp`.
- Public HTTPS invitation preview: **PASS** for the correct recipient and pending invitation.
- Duplicate pending invitations: **PASS**, none created.
- Inbox delivery: **NOT YET CONFIRMED BY THE RECIPIENT**. SMTP acceptance is not an inbox-delivery or read receipt.
- Recipient acceptance: **NOT YET CONFIRMED**. No membership was fabricated or automatically accepted for verification.

Real SMTP verification observed the actual transport methods and their returned status codes without replacing network communication, printing AUTH data or exposing invitation tokens. The send used the application's invitation handler/service and its existing owner, capacity and permission checks. This was a backend maintenance invocation; no owner/member JWT was forged to simulate a browser login.

## Public HTTPS address

**https://securities-hope-responding-road.trycloudflare.com**

The frontend, `/invite`, and `/api/openapi.json` all returned HTTP 200 over HTTPS. FastAPI is reached through the existing same-origin `/api` proxy. No outgoing invitation contains localhost. Invitation secrets stay in the email URL fragment and preview POST body, not in this report or access-log paths.

This URL is temporary. The local frontend, backend and Cloudflare tunnel must remain running while the recipient opens the invitation. No hosting deployment was performed.

## Tests

- **PASS:** 15 invitation/SMTP regression tests using isolated SQLite and transport mocks. These verify configuration reload, secret-safe failures, rejected authentication, preservation of existing links after failed resend, URL restrictions, permission checks, reservations, no duplicate invitation rows, replay protection and acceptance behavior.
- **PASS:** real SMTP authentication, actual Gmail message acceptance and public invitation preview, as separately recorded above.
- **PASS:** Python compilation and `git diff --check`.
- Unrelated frontend designs, Stripe code, database schema and financial data were not changed.

The mocked tests are regression coverage, not the evidence for real email submission.

## Files affected in this task

- `backend/app/services/invitations.py` — fresh email settings, safe settings-validation handling and account-pair error guidance.
- `backend/app/routers/household.py` — preserve existing invitation links/expiry on failed resend; record bounded SMTP status codes.
- `backend/tests/test_family_invitations.py` — reload, secret-safety and failed-resend regression coverage.
- `backend/tests/test_family.py` — email settings dependency injection for isolated fixtures.
- `backend/.env` — public HTTPS URL only; credentials unchanged. This private file must not be committed.
- `docs/MAXBUD_SMTP_DIAGNOSIS.md` — this report.

## Remaining manual action

Open Gmail while signed in as `santhanaluxmy20@gmail.com`, check Inbox and Spam for MaxBud, and open **Accept your invitation** inside the email. Sign in or register with that same address and accept. The recipient email address itself is a `mailto:` link and opens a compose-app chooser; it is not the invitation acceptance link.

No push or deployment was performed.
