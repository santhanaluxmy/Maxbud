# Registration and login verification

16 November 2026. Checks use synthetic accounts and disposable SQLite data. Genuine MySQL accounts, passwords, financial records and private environment files were not changed. This follows the previously completed frontend/API connection work.

## Bug found and fixed

`verify_password()` caught ValueError/TypeError but not pwdlib's `UnknownHashError`. The configured Argon2 verifier raises that exception for a bcrypt hash before `password_matches()` can reach its intended legacy bcrypt fallback. Unsupported/corrupt stored hashes could therefore produce a server error rather than a controlled login failure.

The verifier now returns false for UnknownHashError so the existing bcrypt fallback can run. Valid legacy bcrypt passwords authenticate; incorrect passwords and corrupt hashes produce 401. Existing password hashes are preserved. `bcrypt>=4,<6` is explicitly declared because the fallback depends on it; installed bcrypt 5.0.0 was reused, without installation or upgrades.

Application files changed: `backend/app/core/security.py` and `backend/requirements.txt`. No authentication schema, migration, UI design or stored credentials changed.

## API checks

New `backend/tests/test_auth_flow.py` contains nine passing cases:

1. Registration normalizes email/name, stores a password hash rather than plaintext, starts a personal trial, issues a usable token, does not create an automatic household, and ignores a forged admin role.
2. Invalid email/name/password/confirmation inputs return 422 without leaving partial users.
3. Duplicate email detection is case insensitive and does not replace the original password.
4. Wrong password and unknown email return the same 401 response.
5. Login returns current onboarding completion and role for frontend redirect decisions.
6. Disabled accounts cannot log in or reuse an existing token.
7. Missing, expired and tampered tokens cannot access `/auth/me`.
8. Legacy bcrypt credentials authenticate without modifying their stored hash; wrong passwords are rejected.
9. Unsupported/corrupt password hashes return 401 rather than raising an unhandled exception.

Fresh run: **9 tests passed in 2.915s**. The full backend regression suite also passed: **74 tests in 31.638s**. The test fixture overrides get_db and explicitly selects disposable SQLite mode; it does not write to genuine MySQL.

```bash
cd backend
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_auth_flow.py' -v
FAMILY_TEST_MYSQL=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

## Frontend checks

`frontend/tests/auth.test.mjs` covers request bodies/normalization, bearer profile access, duplicate-email messages, unreachable server messages and logout. Added cases verify exactly one storage location for Remember me, expired-session cleanup and clearing a previous session on a failed password login. `npm test` passed all four frontend test files; this is not four total assertions.

```bash
cd frontend
npm test
```

## Browser checks

`backend/tests/auth_flow_browser.py` exercises real React pages through `/api`, FastAPI and a temporary SQL database. It reuses the safe core-flow server, with configurable test ports/log level. It tests signed-out route protection; empty/invalid form errors; successful registration; duplicate-email and wrong-password errors; session-only versus Remember me storage; new-tab behavior; network failure/retry; incomplete/completed/admin destinations; logout; suspended-account denial; expired-session cleanup; and browser JavaScript errors.

Only synthetic fixture state is changed to choose completed/admin/disabled accounts. The full five-step onboarding forms were already exercised by `core_flow_browser.py`; this focused test avoids repeating that entire workflow.

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/auth_flow_browser.py
```

Browser result: **PASS (exit 0)**. Observed API statuses: registration 201, duplicate registration 409, wrong password 401, valid login 200 and disabled-account login 403. Every browser check listed above passed, including storage/redirect/expiry behavior; no browser JavaScript errors occurred. Initial attempts encountered test-service readiness and a registration response timeout; they are not counted as passes. The successful final attempt used separate test ports 8791/5181, recorded HTTP statuses and synthetic diagnostics, and allowed 45 seconds for responses.

## Remaining limitations

- These mutation checks use SQLite; real MySQL connectivity was verified read-only in the previous core-flow phase. No full MySQL authentication write test or real-user password reset was performed here.
- Google OAuth verification has existing mocked API coverage. Interactive Google login is not freshly verified without an authorized provider session/setup.
- Forgotten-password recovery is still absent. Password changes still do not revoke already issued JWTs; that separately identified audit issue remains open.
- Frontend expiry checks support navigation convenience; backend JWT signature/expiry and active-user validation remain authoritative.
