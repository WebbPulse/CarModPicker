---
status: partial
phase: 01-safety-nets-ci-hardening
source: [01-VERIFICATION.md]
started: 2026-04-22T09:15:00Z
updated: 2026-04-22T09:30:00Z
---

## Current Test

[1 of 2 complete — OAuth cassettes deferred]

## Tests

### 1. Dependabot GitHub-side activation
expected: After pushing `.github/dependabot.yml` to the default branch on GitHub, the repo's **Insights → Dependency graph → Dependabot** tab shows three active ecosystems: `pip` at `/backend`, `npm` at `/frontend` and `/chrome-extension`, and `github-actions` at `/`. First weekly run is the Monday following the merge; earlier than that, the tab should still list the three ecosystems with "Last checked: …" timestamps.
result: passed (user confirmed 2026-04-22)

### 2. OAuth cassette recording (2 tests)
expected: A developer with Google sandbox credentials records cassettes per the 7-step recipe (see below), commits them under `backend/tests/auth/cassettes/` (pytest-recording default layout), and confirms both `test_characterization_oauth_signin` and `test_characterization_oauth_link` move from SKIPPED to PASSED under `pytest -n auto`.
result: pending (user deferred 2026-04-22 — will record later when Google sandbox is set up)

Recording recipe summary:
1. Obtain a real Google `id_token` via the browser OAuth consent flow (Client ID must be set as `GOOGLE_CLIENT_ID`).
2. Paste the real `id_token`, a nonce, and the matching email into the test-file placeholders `<ID_TOKEN_FROM_CASSETTE>`, `<NONCE_FROM_CASSETTE>`, `<EMAIL_FROM_CASSETTE>` in `test_characterization_oauth_signin.py`.
3. `rm -rf tests/auth/cassettes/test_characterization_oauth_signin` and run `pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_signin.py::test_google_oauth_signin`.
4. Repeat steps 2–3 for `test_characterization_oauth_link.py` (same id_token works, or a second account for a cleaner test).
5. Confirm `pytest -n auto` shows both PASSED (not SKIPPED).
6. Confirm `pytest -n auto tests/test_cassette_secret_audit.py` still passes (scrub config already covers Authorization/Cookie/client_secret/code/refresh_token/access_token).
7. Commit both updated test files AND the new `tests/auth/cassettes/` YAML tree.

## Summary

total: 2
passed: 1
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
