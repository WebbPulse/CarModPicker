---
phase: 01-safety-nets-ci-hardening
plan: "06"
subsystem: auth-characterization
tags:
  - auth
  - characterization
  - vcr
  - pytest-recording
  - security
  - safe-06
dependency_graph:
  requires:
    - 01-04  # coverage gate must exist before adding tests that count toward it
  provides:
    - SAFE-06  # 7 auth happy-path characterization tests + cassette audit
  affects:
    - Phase 5 AUTH-01…AUTH-06 (auth refactor guardrail — these tests are the safety net)
tech_stack:
  added:
    - pytest-recording==0.13.4  # VCR cassette record/replay for pytest
  patterns:
    - Library-boundary stubs via unittest.mock.patch (WebAuthn crypto)
    - VCR cassette replay for Google OAuth JWKS HTTP traffic
    - pytest.mark.skipif cassette-existence guard (tests skip cleanly, never fail, when cassettes absent)
    - D-19 assertion depth: HTTP status + response key presence + DB state change
key_files:
  created:
    - backend/requirements.txt  # pytest-recording==0.13.4 added to Testing block
    - backend/tests/conftest.py  # vcr_config fixture appended (SAFE-06 block)
    - backend/tests/auth/__init__.py  # empty package marker
    - backend/tests/cassettes/auth/.gitkeep  # shared cassette directory placeholder
    - backend/tests/auth/test_characterization_signup_verify.py  # flow 1
    - backend/tests/auth/test_characterization_login.py  # flow 2
    - backend/tests/auth/test_characterization_2fa_totp.py  # flow 3
    - backend/tests/auth/test_characterization_webauthn.py  # flow 4
    - backend/tests/auth/test_characterization_oauth_signin.py  # flow 5
    - backend/tests/auth/test_characterization_oauth_link.py  # flow 6
    - backend/tests/auth/test_characterization_password_reset.py  # flow 7
    - backend/tests/test_cassette_secret_audit.py  # T-06-01 guardrail
  modified:
    - backend/requirements.txt
    - backend/tests/conftest.py
decisions:
  - "Token-based verify-email test: generates JWT directly using create_access_token (same as auth.py) rather than capturing SES email — follows existing test_auth.py pattern (test_verify_email_confirm_success)"
  - "Password reset test: skips POST /auth/reset-password (SES fails in test env with 500) and generates reset token directly — identical to test_reset_password_confirm_success pattern"
  - "WebAuthn: patches all 4 library functions at app.api.endpoints.auth.* even though generate_* don't hit external HTTP — pins import path for Phase 5 refactor safety (T-06-06)"
  - "generate_registration_options / generate_authentication_options: mock returns real webauthn options objects (not SimpleNamespace) because auth.py calls options_to_json() on the return value which requires proper webauthn types"
  - "OAuth tests: cassette layout is <test-dir>/cassettes/<module-basename>/<test-func>.yaml (pytest-recording's vcr_cassette_dir default), NOT backend/tests/cassettes/ — skipif guard uses this exact path"
  - "Secret audit covers both cassette roots: backend/tests/cassettes/ AND backend/tests/auth/cassettes/ (actual pytest-recording default for auth/ subdirectory tests)"
metrics:
  duration: "~25 min"
  completed_date: "2026-04-22"
  tasks_completed: 5
  files_created: 12
  files_modified: 2
---

# Phase 01 Plan 06: Auth Characterization Tests Summary

SAFE-06 implemented: 7 auth happy-path characterization tests + cassette secret-audit guardrail, using pytest-recording==0.13.4 with full secret scrubbing.

## Test Files Created

1. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_signup_verify.py` — Flow 1: unverified user created in DB → verify-email/confirm JWT → email_verified flipped True
2. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_login.py` — Flow 2: email/password login → access_token + user returned
3. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_2fa_totp.py` — Flow 3: TOTP setup → verify → totp_enabled in DB → 2FA login challenge → token/2fa completion
4. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_webauthn.py` — Flow 4: WebAuthn register/options + register/verify + login/options + login/verify
5. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_oauth_signin.py` — Flow 5: Google OAuth sign-in (VCR, skips without cassette)
6. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_oauth_link.py` — Flow 6: Google OAuth account link (VCR, skips without cassette)
7. `/home/tyler-webb/Documents/Github/CarModPicker/backend/tests/auth/test_characterization_password_reset.py` — Flow 7: password reset token confirm → password changed → old pw rejected

## WebAuthn Patch Targets (D-18, T-06-06)

All 4 webauthn library functions are patched at the `app.api.endpoints.auth` import boundary:

```python
@patch("app.api.endpoints.auth.verify_authentication_response")
@patch("app.api.endpoints.auth.generate_authentication_options")
@patch("app.api.endpoints.auth.verify_registration_response")
@patch("app.api.endpoints.auth.generate_registration_options")
```

The `generate_*` functions return real `webauthn` options objects (not `SimpleNamespace`) because `auth.py` pipes the return value through `options_to_json()` which requires proper typed structs.

## OAuth Cassette Guard Snippet

Both OAuth tests use the pytest-recording default cassette layout and skip when cassettes are absent:

```python
_CASSETTE = (
    pathlib.Path(__file__).parent
    / "cassettes"
    / pathlib.Path(__file__).stem
    / "test_google_oauth_signin.yaml"  # or test_google_oauth_link_existing_user.yaml
)

pytestmark = pytest.mark.skipif(
    not _CASSETTE.exists(),
    reason="Cassette missing — run `cd backend && pytest -n 0 --record-mode=once ...` to generate.",
)
```

## Cassette Recording Command (Post-Merge Required Step)

After merging, a developer with Google sandbox credentials must record cassettes:

```bash
cd backend

# Ensure GOOGLE_CLIENT_ID is set in .env for the test Google account
export GOOGLE_CLIENT_ID=<sandbox-client-id>

# Record flow 5 (Google OAuth sign-in)
rm -rf tests/auth/cassettes/test_characterization_oauth_signin
pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_signin.py::test_google_oauth_signin

# Record flow 6 (Google OAuth account link)
rm -rf tests/auth/cassettes/test_characterization_oauth_link
pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_link.py::test_google_oauth_link_existing_user

# Commit the cassette YAML files
git add tests/auth/cassettes/
git commit -m "test(01-06): add Google OAuth VCR cassettes for flows 5+6"
```

MUST use `-n 0` (serial) to avoid pytest-xdist write races during recording.

## Post-Merge OAuth Cassette Validation (REQUIRED)

After cassettes are committed, run:

```bash
cd backend && pytest -n auto tests/auth/test_characterization_oauth_signin.py tests/auth/test_characterization_oauth_link.py -v
```

Confirm tests report **PASSED**, not SKIPPED. A SKIPPED result after cassette YAMLs exist means the `_CASSETTE` path formula doesn't match pytest-recording's actual layout. Fix the path computation so `_CASSETTE.exists()` returns `True`, then re-run.

## Handoff Note for Phase 5 (AUTH-01…AUTH-06)

These 7 tests are the guardrail for the auth.py decomposition into `auth/` package. Phase 5's AUTH-01 PR must:
- Keep all 7 characterization tests green
- Keep the cassette audit green (no new scraped secrets)
- If WebAuthn imports move (e.g. into a `utils/webauthn.py`), update the `@patch` targets from `app.api.endpoints.auth.*` to the new import location — the test will fail loudly if patch targets become wrong (T-06-06 natural detection)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] signup_verify test: email_verified=True in TESTING mode**
- **Found during:** Task 2 execution
- **Issue:** The `POST /api/users/` endpoint auto-sets `email_verified=True` when `TESTING=true`, so the planned "signup via API then verify" couldn't test the unverified→verified transition
- **Fix:** Create user directly in DB with `email_verified=False`, then drive the confirm endpoint — identical to existing `test_verify_email_confirm_success` pattern in test_auth.py
- **Files modified:** `tests/auth/test_characterization_signup_verify.py`

**2. [Rule 1 - Bug] password_reset test: SES returns 500 in test env**
- **Found during:** Task 2 execution
- **Issue:** `POST /api/auth/reset-password` calls `send_reset_password_email()` which returns `False` in the test environment (no SES credentials), causing auth.py to raise a 500
- **Fix:** Skip the email-send step; generate reset token directly via `create_access_token` — identical to existing `test_reset_password_confirm_success` pattern
- **Files modified:** `tests/auth/test_characterization_password_reset.py`

**3. [Rule 2 - Missing Critical] WebAuthn mocks: generate_* return real objects not SimpleNamespace**
- **Found during:** Task 3 implementation analysis
- **Issue:** The plan's `SimpleNamespace(challenge=b"...")` pattern would fail because `auth.py` calls `options_to_json(options)` on the generate_* return value — `options_to_json` requires a proper `webauthn` typed object, not a SimpleNamespace
- **Fix:** Mock returns real webauthn options objects constructed via the real library with a controlled challenge value
- **Files modified:** `tests/auth/test_characterization_webauthn.py`

**4. [Rule 2 - Missing] Secret audit: second cassette root added**
- **Found during:** Task 5 implementation
- **Issue:** pytest-recording's default cassette layout for `backend/tests/auth/*.py` tests puts cassettes at `backend/tests/auth/cassettes/` NOT `backend/tests/cassettes/auth/`. The audit needed to cover both locations.
- **Fix:** `CASSETTE_ROOTS` array covers both `tests/cassettes/` and `tests/auth/cassettes/`
- **Files modified:** `tests/test_cassette_secret_audit.py`

**5. [Rule 2 - Missing] Secret audit: 2 meta-guard tests added beyond plan spec**
- **Found during:** Task 5 — success criteria requires "FAILS when fed a cassette with leaked tokens (use an in-memory or tmp-path leak fixture to prove the detection)"
- **Fix:** Added `test_cassette_audit_detection_works_with_leaked_token` (proves detection catches ya29. token) and `test_cassette_audit_passes_for_redacted_cassette` (proves no false-positives on REDACTED cassettes)
- **Files modified:** `tests/test_cassette_secret_audit.py`

## Threat Surface Scan

No new network endpoints introduced. No new auth paths. No new schema changes. All new files are test-only and do not affect production code paths.

## Known Stubs

- `test_characterization_oauth_signin.py` lines 73-75: `id_token_from_cassette`, `nonce_from_cassette`, `email_from_cassette` are `"<..._FROM_CASSETTE>"` placeholders that must be replaced when cassettes are recorded. These are intentional — the values come from the cassette recording session and cannot be known at plan-time. The `skipif` guard prevents these from causing test failures.
- `test_characterization_oauth_link.py` lines 66-68: same cassette placeholder pattern.

These stubs are **intentional** and documented above under "Post-Merge OAuth Cassette Validation".

## Self-Check: PASSED

Files created:
- backend/tests/auth/test_characterization_signup_verify.py: EXISTS
- backend/tests/auth/test_characterization_login.py: EXISTS
- backend/tests/auth/test_characterization_2fa_totp.py: EXISTS
- backend/tests/auth/test_characterization_webauthn.py: EXISTS
- backend/tests/auth/test_characterization_oauth_signin.py: EXISTS
- backend/tests/auth/test_characterization_oauth_link.py: EXISTS
- backend/tests/auth/test_characterization_password_reset.py: EXISTS
- backend/tests/test_cassette_secret_audit.py: EXISTS

Commits:
- 739096f: chore(01-06): install pytest-recording + vcr_config fixture + auth test package
- 5a736b3: feat(01-06): add 4 non-VCR characterization tests (flows 1, 2, 3, 7)
- a0558a8: feat(01-06): add WebAuthn characterization test (flow 4) with library-boundary stubs
- f38d9ec: feat(01-06): add Google OAuth characterization tests (flows 5+6) with VCR skip guards
- ec2e061: feat(01-06): add cassette secret-audit test (T-06-01 guardrail)

Full suite: 2154 passed, 5 skipped — coverage floor from Plan 04 maintained.
