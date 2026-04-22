---
phase: 1
slug: safety-nets-ci-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-21
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 7.x + pytest-xdist + pytest-cov (already installed) + pytest-recording (Wave 0 installs) |
| **Framework (frontend)** | vitest 3.x + @vitest/coverage-v8 (already installed) |
| **Config file (backend)** | `backend/pytest.ini` |
| **Config file (frontend)** | `frontend/vitest.config.ts` |
| **Quick run command (backend)** | `cd backend && pytest -n auto -x --no-cov` (no coverage, fail-fast) |
| **Full suite command (backend)** | `cd backend && pytest -n auto --cov=app --cov-report=term-missing --cov-fail-under=<measured_baseline>` |
| **Quick run command (frontend)** | `cd frontend && npm test -- --run` |
| **Full suite command (frontend)** | `cd frontend && npm test -- --run --coverage` |
| **Migration DROP-guard command** | `cd backend && python scripts/check_migrations.py` |
| **OpenAPI snapshot command** | `cd backend && pytest -n auto tests/test_openapi_snapshot.py` |
| **Estimated runtime** | Backend quick: ~30s · Backend full: ~60s · Frontend full: ~20s · DROP guard: ~1s · Total CI time: < 3 min |

---

## Sampling Rate

- **After every task commit:** Run quick command for the subsystem touched (backend → backend quick; frontend → frontend quick). Never defer feedback beyond one commit.
- **After every plan wave:** Run full suite for every subsystem touched in the wave. All CI gates (coverage floor, DROP guard, OpenAPI snapshot, Dependabot YAML lint) must pass locally before the wave is marked complete.
- **Before `/gsd-verify-work`:** Full backend suite + full frontend suite + DROP-guard script must all be green. CI on the push branch must also be green.
- **Max feedback latency:** 60 seconds (backend quick is bounded by `-n auto` parallelism; frontend quick is bounded by vitest run mode).

---

## Per-Task Verification Map

> Tasks are not yet authored — the planner fills this in. The map below is the CONTRACT: every future plan task must map to at least one row, and no three consecutive tasks may lack an automated verification step.

| Requirement | Subsystem | Test Type | Automated Command | Verification Artifact |
|-------------|-----------|-----------|-------------------|----------------------|
| SAFE-01 | backend | config / CI gate | `cd backend && pytest -n auto --cov=app --cov-fail-under=<baseline>` | `pytest.ini` contains `--cov-fail-under` in `addopts`; CI fails on coverage drop |
| SAFE-02 | frontend CI | workflow | `gh workflow view frontend-ci.yml` + CI run on PR | `.github/workflows/frontend-ci.yml` has `Run tests` step before `Build application` |
| SAFE-03 | frontend | config / CI gate | `cd frontend && npm test -- --run --coverage` | `vitest.config.ts` has `coverage.thresholds: { lines: 60, functions: 50, branches: 50, statements: 60 }` |
| SAFE-04 | backend / CI | script + workflow step | `cd backend && python scripts/check_migrations.py` (fails on unannotated `drop_*`) | `backend/scripts/check_migrations.py` exists; `.github/workflows/backend-ci.yml` invokes it |
| SAFE-05 | backend | snapshot test | `cd backend && pytest -n auto tests/test_openapi_snapshot.py` | `backend/tests/fixtures/openapi_snapshot.json` committed; test asserts `app.openapi()` equals snapshot |
| SAFE-06 | backend | characterization (vcrpy) | `cd backend && pytest -n auto tests/auth/test_characterization_*.py` | 7 tests green; cassettes committed under `backend/tests/cassettes/auth/` |
| SAFE-07 | backend | characterization (fixture replay) | `cd backend && pytest -n auto tests/crawlers/test_characterization_*.py` | 5 tests green; 5 HTML fixtures committed under `backend/tests/crawlers/fixtures/<adapter>/product.html`; 5 expected-output JSONs committed |
| SAFE-08 | backend / DB | repair migrations + test upgrade | `cd backend && alembic upgrade head` on a Postgres container primed with broken state | 3 repair migration files exist; each carries `# SAFE: repair invalid drop_constraint(None) — see SAFE-08` annotation |
| SAFE-09 | backend | unit assertion | `cd backend && pytest -n auto -k test_metadata_naming_convention` | `backend/app/db/base_class.py` applies `MetaData(naming_convention=...)`; test asserts convention keys present |
| SAFE-10 | repo | config lint | `cd . && yamllint .github/dependabot.yml && gh api repos/:owner/:repo/dependabot/alerts` | `.github/dependabot.yml` committed with `pip`, `npm` (both `frontend/` + `chrome-extension/`), `github-actions` ecosystems on weekly Monday schedule with minor+patch grouping |

---

## Wave 0 Requirements

- [ ] `backend/requirements.txt` — add `pytest-recording` (SAFE-06 dependency; fails characterization tests without it)
- [ ] `backend/tests/cassettes/auth/` — empty directory placeholder with `.gitkeep` (SAFE-06 cassette home)
- [ ] `backend/tests/crawlers/fixtures/<adapter_name>/` — 5 subdirectory placeholders with `.gitkeep` (SAFE-07 fixture home)
- [ ] `backend/scripts/` — directory exists (SAFE-04 script home)
- [ ] `backend/tests/fixtures/` — directory exists (SAFE-05 snapshot home)
- [ ] Measure backend coverage baseline ONCE on a clean `main` — capture the number into PR description (SAFE-01, D-01)
- [ ] Measure frontend coverage baseline ONCE on a clean `main` — if < 60, write tests to reach 60 BEFORE enabling threshold (SAFE-03, D-05)
- [ ] Confirm prod RDS alembic_version — `SELECT version_num FROM alembic_version` to determine SAFE-08 repair strategy (research Open Question 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DROP-guard fails CI on an unannotated `drop_column` | SAFE-04 | Requires a PR-level regression test — CI run, not a local unit test | Create throwaway branch with an unannotated `drop_column` in a migration; push; verify CI job `migration-drop-guard` turns red |
| DROP-guard passes CI on a `# SAFE:`-annotated `drop_column` | SAFE-04 | Same as above — CI-level proof | Same as above but with `# SAFE: <reason>` annotation; verify CI turns green |
| Coverage floor ratchet fails a real regression PR | SAFE-01 | Requires a PR that actually reduces coverage | Throwaway branch deletes one test; verify CI fails with `cov-fail-under` message |
| Vitest threshold fails a real regression PR | SAFE-03 | Same | Throwaway branch deletes one test; verify frontend CI fails on threshold |
| Dependabot actually opens a grouped minor+patch PR on Monday | SAFE-10 | Cannot trigger Dependabot in CI; live behavior proof | After merge, wait until Monday or manually trigger via `gh api /repos/:owner/:repo/dependabot/updates`; verify a grouped PR appears |
| Auth cassette regeneration works end-to-end | SAFE-06 | Requires live Google OAuth / live SES / live network — explicitly excluded from CI | Delete one cassette locally, re-run the test against a real Google OAuth sandbox; verify the new cassette records correctly AND that secrets are scrubbed per VCR filter config |

---

## Validation Sign-Off

- [ ] All phase requirements (SAFE-01 through SAFE-10) have an automated verification row in the Per-Task Verification Map
- [ ] Sampling continuity: no 3 consecutive tasks in any PLAN.md without an automated verify (enforced by planner)
- [ ] Wave 0 covers all MISSING references (pytest-recording install, cassette/fixture directories, baseline measurements, prod alembic_version probe)
- [ ] No watch-mode flags anywhere (`npm test -- --run`, not `npm test`; `pytest`, not `pytest --watch`)
- [ ] Feedback latency < 60s for quick commands
- [ ] `nyquist_compliant: true` set in frontmatter once all above boxes are checked

**Approval:** pending
