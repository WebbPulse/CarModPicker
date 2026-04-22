---
status: partial
phase: 01-safety-nets-ci-hardening
source: [01-VERIFICATION.md]
started: 2026-04-22T09:15:00Z
updated: 2026-04-22T09:15:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Dependabot GitHub-side activation
expected: After pushing `.github/dependabot.yml` to the default branch on GitHub, the repo's **Insights → Dependency graph → Dependabot** tab shows three active ecosystems: `pip` at `/backend`, `npm` at `/frontend` and `/chrome-extension`, and `github-actions` at `/`. First weekly run is the Monday following the merge; earlier than that, the tab should still list the three ecosystems with "Last checked: …" timestamps.
result: [pending]

### 2. OAuth cassette recording (2 tests)
expected: A developer with Google sandbox credentials records cassettes per the command block in `01-06-SUMMARY.md`, commits them under `backend/tests/cassettes/auth/`, and confirms both `test_characterization_oauth_signin` and `test_characterization_oauth_link` move from SKIPPED to PASSED under `pytest -n auto`.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
