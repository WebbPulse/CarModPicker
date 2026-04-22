---
phase: 4
slug: db-parts-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-xdist (SQLite default; opt-in Postgres 16 for marked tests) |
| **Config file** | `backend/pytest.ini` (existing) + new `postgres` marker registration |
| **Quick run command** | `cd backend && pytest -n auto -m "not postgres"` |
| **Full suite command** | `cd backend && pytest -n auto` (SQLite) + CI job `POSTGRES_TEST_URL=... pytest -n 4 -m postgres` |
| **Estimated runtime** | ~90s SQLite default / +~30s Postgres-marked job on CI |

---

## Sampling Rate

- **After every task commit:** Run `pytest -n auto -m "not postgres"` (SQLite-default — fast feedback)
- **After every plan wave:** Run the wave's targeted tests + the full SQLite suite
- **Before `/gsd-verify-work`:** Full SQLite suite must be green AND the Postgres-marked concurrency test must be green in CI
- **Max feedback latency:** ~90s for SQLite default; ~120s for a Postgres-marked subset in CI

---

## Per-Task Verification Map

> Task IDs below are illustrative; the planner owns exact IDs. This map enumerates every validation class that MUST exist by end-of-phase. Each row maps one ROADMAP success criterion or locked decision to its verifying test + CI gating.

| Validation Class | Plan (approx.) | Wave | Requirement(s) | Test Type | Automated Command | Fidelity | CI Gating | Status |
|------------------|----------------|------|----------------|-----------|-------------------|----------|-----------|--------|
| N+1 query-count regression | build_logs N+1 fix | 3 | DATA-01, DATA-02 | regression (SQLAlchemy `event.listen("before_cursor_execute")` counter) | `pytest -n auto backend/tests/test_build_log_n_plus_one.py` | SQLite | always-on | ⬜ pending |
| `query_counter` fixture | build_logs N+1 fix | 3 | DATA-02 | fixture + self-test | `pytest -n auto backend/tests/test_query_counter_fixture.py` | SQLite | always-on | ⬜ pending |
| Part-linker concurrency (10-thread) | part-linker hardening | 4 | DATA-03, DATA-04, PARTS-01 | concurrency (Postgres + `with_for_update`) | `POSTGRES_TEST_URL=... pytest -n 4 -m postgres backend/tests/services/test_part_linker_concurrency.py` | Postgres 16 | opt-in locally; required in CI job | ⬜ pending |
| Canonical-flow integration | part-linker integration | 5 | PARTS-03 | integration (SQLite, 5 scenarios) | `pytest -n auto backend/tests/services/test_part_linker_integration.py` | SQLite | always-on | ⬜ pending |
| FK index presence | FK audit migration | 1 | DATA-05 | model introspection + `SHOW INDEXES` query | `pytest -n auto backend/tests/test_fk_indexes.py` | SQLite (autogenerate-name assertions) | always-on | ⬜ pending |
| Add-index migration round-trip | FK audit migration | 1 | DATA-05 | Alembic upgrade → downgrade → upgrade | `cd backend && ./scripts/test_migration_round_trip.sh <revision>` | Local Postgres (Docker) | documentation (reviewer gate) | ⬜ pending |
| Build-log eager create + backfill | build_log backfill | 2 | DATA-08 | migration data-check + startup assertion | `pytest -n auto backend/tests/test_build_log_backfill.py` | SQLite (idempotent backfill shape) | always-on | ⬜ pending |
| Build-log orphan assertion | build_log cleanup | 2 | DATA-08 | post-migration `SELECT COUNT(*)` guard | `pytest -n auto backend/tests/test_build_log_orphan_guard.py` | SQLite | always-on | ⬜ pending |
| `session.query` grep regression | session.query sweep | 3 | DATA-06 | grep-based (mirrors Phase 3 QUAL-02/07 pattern) | `pytest -n auto backend/tests/test_session_query_regression.py` | No DB | always-on | ⬜ pending |
| Pool config regression | pool_recycle tweak | 1 | DATA-07 | assert `engine.pool._recycle == 1800` + pool_size/max_overflow unchanged | `pytest -n auto backend/tests/test_db_pool_config.py` | SQLite (config-only) | always-on | ⬜ pending |
| `lazy="raise"` caller coverage | lazy=raise scope | 5 | DATA-10 | each callers-path test hits the loader-paired path without raising | `pytest -n auto backend/tests/test_lazy_raise_callers.py` | SQLite | always-on | ⬜ pending |
| car_inference ambiguity pin | car_inference docs | 5 | PARTS-02 | fixed-input regression (~20 vectors) | `pytest -n auto backend/tests/test_car_inference_ambiguity.py` | SQLite (pure Python, no DB) | always-on | ⬜ pending |
| OpenAPI snapshot (Phase 1 SAFE-05) | session.query sweep | 3 | — (inherited) | snapshot diff must be empty | `pytest -n auto backend/tests/test_openapi_snapshot.py` | SQLite | always-on | ⬜ pending |
| Auth + crawler characterization (Phase 1) | all waves | 1–5 | — (inherited) | smoke — MUST stay green across every plan merge | `pytest -n auto backend/tests/test_auth_characterization.py backend/tests/test_crawler_characterization.py` | SQLite | always-on | ⬜ pending |
| Coverage floor | all waves | 1–5 | — (inherited SAFE-01) | `--cov-fail-under=51` must NOT regress | `pytest -n auto --cov=app --cov-report=term-missing` | SQLite | always-on | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**ROADMAP Success-Criterion → Test Map (1:1 coverage):**

| ROADMAP Criterion | Primary Test | Supporting Test |
|-------------------|--------------|-----------------|
| 1. `GET /build-logs/build-list/{id}` issues exactly 2 SQL queries | `test_build_log_n_plus_one.py` | `test_query_counter_fixture.py` |
| 2. 10-thread link/unlink produces zero orphaned/circular refs | `test_part_linker_concurrency.py` (Postgres) | `test_part_linker_integration.py` (SQLite algorithmic coverage) |
| 3. All FK join keys have `Index()` declarations | `test_fk_indexes.py` | Alembic autogenerated migration file review |
| 4. Zero `session.query()` calls remain | `test_session_query_regression.py` | — |
| 5. Build log creation is eager; lazy branch eliminated | `test_build_log_orphan_guard.py` | `test_build_log_backfill.py` |

---

## Wave 0 Requirements

- [ ] `backend/pytest.ini` — register `postgres` marker (`markers = postgres: opt-in Postgres-backed tests; serial: force single-worker`)
- [ ] `backend/tests/conftest.py` — add `query_counter` fixture (SQLAlchemy `event.listen("before_cursor_execute", ...)`); add `postgres_engine` + `postgres_session` fixtures gated on `POSTGRES_TEST_URL`; add per-worker Postgres DB creation using `PYTEST_XDIST_WORKER` env var
- [ ] `.github/workflows/backend-ci.yml` — add Postgres `services` block + a dedicated job step running `pytest -n 4 -m postgres`
- [ ] `docker-compose.test.yml` — add `postgres-test` service (Postgres 16, tmpfs data dir) for local `-m postgres` runs
- [ ] `backend/scripts/test_migration_round_trip.sh` — helper script documented in CONVENTIONS.md for reviewer-gated downgrade testing
- [ ] New test-file stubs at creation time so per-task verification commands exist from task-1 onward:
  - [ ] `backend/tests/test_build_log_n_plus_one.py`
  - [ ] `backend/tests/test_query_counter_fixture.py`
  - [ ] `backend/tests/services/test_part_linker_concurrency.py`
  - [ ] `backend/tests/services/test_part_linker_integration.py`
  - [ ] `backend/tests/test_fk_indexes.py`
  - [ ] `backend/tests/test_build_log_backfill.py`
  - [ ] `backend/tests/test_build_log_orphan_guard.py`
  - [ ] `backend/tests/test_session_query_regression.py`
  - [ ] `backend/tests/test_db_pool_config.py`
  - [ ] `backend/tests/test_lazy_raise_callers.py`
  - [ ] `backend/tests/test_car_inference_ambiguity.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Alembic migration downgrade round-trip (FK index + build_log backfill migrations) | DATA-09 | Per D-31: CI automation deferred; reviewer-gated convention in CONVENTIONS.md. Postgres side-car currently exists only for the concurrency test job. | Before merge, reviewer runs `backend/scripts/test_migration_round_trip.sh <revision>` against local Docker Postgres; pastes the green output into the PR conversation. |
| `pool_recycle=1800` behavior in prod | DATA-07 | Production RDS idle-disconnect and App Runner cold-start rates cannot be measured in unit tests. | Post-deploy, operator watches CloudWatch RDS metrics (`DatabaseConnections`, `DisconnectCount`) for ~48h; if reconnect rate spikes, revisit the value (per CONTEXT.md Deferred Ideas). |
| RDS Performance Insights — zero FK full-table-scan warnings | DATA-05, ROADMAP criterion 3 | Requires live prod traffic; unit tests verify index presence, not query planner behavior. | Post-deploy, operator samples RDS Performance Insights "Top SQL" view for 48h; confirms no full-table-scan on FK columns listed in the FK audit. |
| `gen_random_uuid()` availability on prod RDS (Research Assumption A2) | DATA-08 | Prod RDS 16 ships with or without `pgcrypto` depending on parameter-group history; cannot assert from unit tests. | Before Wave 2 migration ships: operator runs `SELECT gen_random_uuid();` against prod RDS via the bastion. If it fails, CREATE EXTENSION pgcrypto is added to the migration's upgrade body. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s (SQLite fast path) / <180s (Postgres-marked CI job)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
