# Phase 1: Safety Nets & CI Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-21
**Phase:** 01-safety-nets-ci-hardening
**Mode:** auto (recommended defaults selected for every gray area)
**Areas discussed:** Coverage floors, Migration DROP guard, Auth characterization, Crawler adapter characterization, MetaData naming_convention, OpenAPI snapshot, Dependabot

---

## Backend coverage floor (SAFE-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Set AT measured baseline (no buffer) | Strongest ratchet; any drop fails CI | ✓ |
| Set slightly below baseline (-2%) | Absorbs flake-related swings | |
| Set aspirational (e.g., 80%) | Forces tests but breaks CI until reached | |

**User's choice:** AT measured baseline (auto — recommended default).
**Notes:** STATE.md flags "baseline not yet measured" — measurement is the first execution step.

---

## Frontend CI tests + coverage (SAFE-02, SAFE-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Add tests step before build step | Fail fast on regressions; saves CI minutes | ✓ |
| Add tests step after build step | Builds are a smoke test first | |
| Separate tests workflow job | Parallel, but YAML overhead | |

**User's choice:** Tests before build (auto — recommended default).
**Notes:** `lines: 60` threshold is locked by SAFE-03. If baseline < 60, write tests in-phase to reach 60 before enabling the threshold.

---

## Migration DROP guard (SAFE-04)

| Option | Description | Selected |
|--------|-------------|----------|
| CI step running a grep/AST Python script | Enforced at merge gate; dev machines unaffected | ✓ |
| Pre-commit hook | Catches earlier but trivially bypassed | |
| Alembic `env.py` hook | Runs at migration generation, not at PR | |

**User's choice:** CI step (auto — recommended default).
**Notes:** Annotation format locked as `# SAFE: <reason>` for greppable audit.

---

## Repair broken migrations + naming_convention (SAFE-08, SAFE-09)

| Option | Description | Selected |
|--------|-------------|----------|
| Forward-only naming_convention + targeted repair migrations | Safe on live RDS; no retroactive renames | ✓ |
| Sweep migration renaming all historic constraints | Consistent but dangerous against prod | |
| Skip repair, just gate via DROP guard | SAFE-08 explicitly requires repair | |

**User's choice:** Forward-only + targeted repair (auto — recommended default).
**Notes:** Constraint names discovered via live-DB introspection; repair migrations carry `# SAFE:` annotation.

---

## Auth characterization tests (SAFE-06)

| Option | Description | Selected |
|--------|-------------|----------|
| `pytest-recording` (vcrpy) | REQUIREMENTS.md locks this tool | ✓ |
| Hand-crafted mocks | More explicit but higher maintenance | |
| Integration test w/ live SES stub | Flaky, slow | |

**User's choice:** `pytest-recording` (LOCKED by SAFE-06).
**Notes:** 7 flows locked: signup→verify-email, login, 2FA-TOTP, WebAuthn, Google OAuth sign-in, OAuth account link, password-reset. Assertion depth: status + key presence + DB-state change.

---

## Crawler adapter characterization tests (SAFE-07)

| Option | Description | Selected |
|--------|-------------|----------|
| Pick 5 spanning fetcher tiers (tier0/1/2) | Representativeness across crawler infra | ✓ |
| Pick the 5 most-recently-failing | Pins current recovery state | |
| Pick the 5 most-crawled | Highest production impact | |

**User's choice:** Spanning fetcher tiers (auto — recommended default).
**Notes:** 2× tier0_http (including the recently-fixed ones from 7831fda), 2× tier1_flaresolverr, 1× tier2_tls. Test only `parse_product_page()` against archived HTML; `discover_product_urls()` deferred to Phase 3.

---

## OpenAPI schema snapshot (SAFE-05)

| Option | Description | Selected |
|--------|-------------|----------|
| Commit formatted JSON, diff on PR | Reviewers see actual drift in PR | ✓ |
| Commit SHA-256 hash | Compact but opaque | |
| Auto-regenerate, assert no uncommitted diff | Same as option 1 functionally | |

**User's choice:** Committed formatted JSON (auto — recommended default).

---

## Dependabot / dependency upgrades (SAFE-10)

| Option | Description | Selected |
|--------|-------------|----------|
| Dependabot (GitHub-native) | Zero extra infra, weekly schedule | ✓ |
| Renovate | More configurable, more overhead | |
| Manual quarterly upgrades | Already falling behind | |

**User's choice:** Dependabot (auto — recommended default).
**Notes:** Three ecosystems (`pip`, `npm`, `github-actions`). Group minor+patch, individual PRs for majors.

---

## Claude's Discretion

- Exact names of the `check_migrations.py` variables and functions
- Format details of committed expected-output JSON for adapter fixtures
- Whether to additionally enforce `branches`/`functions`/`statements` floors beyond `lines`
- Minor Dependabot groupings

## Deferred Ideas

- E2E Chrome extension auth flow test via Playwright → Phase 5 (AUTH-05)
- Crawler `discover_product_urls()` characterization → Phase 3
- Retroactive rename of historic constraints → future tech-debt task
- Sentry for CI failures → Phase 2 scope
- Postgres-backed migration testing in CI → Phase 4 (DATA-09)
- `lazy="raise"` on SQLAlchemy relationships → Phase 4 (DATA-10)
- Renovate migration → revisit if Dependabot becomes noisy
