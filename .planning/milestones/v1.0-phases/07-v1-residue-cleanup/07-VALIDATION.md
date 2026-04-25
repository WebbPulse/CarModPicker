---
phase: 7
slug: v1-residue-cleanup
status: accepted
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
validated: 2026-04-24
---

# Phase 7 — Validation Strategy

> Retroactive Nyquist validation for the v1.0 residue-cleanup phase. Phase 7 is itself a regression-pinning phase: its primary deliverables ARE the tests that pin Phase 4 code-review fixes (WR-02/03/04, IN-01, IN-02) and Phase 2 observability/infra items (A-01, TODO-02). VALIDATION.md here certifies that every tech-debt item closed by Phase 7 either has an automated regression test, is environment-gated by design, or is inherently a one-shot/doc item with manual verification.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-xdist 3.8.0 (backend); vitest (frontend); terraform validate (infra) |
| **Config file** | `backend/pytest.ini` (`testpaths = tests`); `frontend/vitest.config.ts`; `terraform/` root |
| **Quick run command** | `cd backend && pytest -n auto --no-cov tests/test_init_service_accounts.py tests/crawlers/test_crawler_user_fallback.py tests/test_build_lists_in01_helper.py tests/test_lifespan_bg_log_context.py tests/test_pytest_ini_testpaths.py 'tests/api/endpoints/test_build_lists.py::TestBuildLists::test_copy_free_tier_cap'` |
| **Full suite command** | `cd backend && pytest -n auto` |
| **Estimated runtime** | Quick: ~9s · Full: ~30s |

---

## Sampling Rate

- **After every task commit:** Run the Quick command above (covers 17 Phase-7 regression tests in <10s)
- **After every plan wave:** Run the Full suite command (2380+ tests, ~30s)
- **Before `/gsd-verify-work`:** Full backend suite must be green + `terraform validate` must pass
- **Max feedback latency:** ~10 seconds for Quick, ~30 seconds for Full

---

## Per-Task Verification Map

Phase 7's "requirements" are tech-debt items (WR-*, IN-*, TD-*, A-*, TODO-*, NYQUIST-*, DOC-*) closed by the 6 plans. The table below maps each closed item to its verifying evidence.

| Task ID | Plan | Wave | Tech-Debt Item | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|----------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | WR-04 | `init_crawler_service_account` logs with `%s` formatter; UUID id renders without TypeError | unit | `cd backend && pytest -n auto --no-cov tests/test_init_service_accounts.py` | ✅ | ✅ green (4 pass) |
| 07-01-02 | 01 | 1 | WR-03 | `_get_crawler_user` env-var fallback parses `CRAWLER_USER_ID` as UUID (rejects non-UUID) | unit | `cd backend && pytest -n auto --no-cov tests/crawlers/test_crawler_user_fallback.py` | ✅ | ✅ green (5 pass) |
| 07-01-03 | 01 | 1 | WR-02 | `reelect_canonical` + `link_new_part` + `unlink_part` acquire locks in deterministic sorted order (no deadlock) | integration (postgres) | `cd backend && pytest -n auto --no-cov 'tests/services/test_part_linker_concurrency.py::test_reelect_and_link_and_unlink_concurrency'` | ✅ | ⚠️ partial — postgres-gated (skips without `POSTGRES_TEST_URL`; CI postgres side-car exercises it) |
| 07-01-04 | 01 | 1 | IN-02 | `copy_build_list` enforces free-tier 1-list cap (402) | integration | `cd backend && pytest -n auto --no-cov 'tests/api/endpoints/test_build_lists.py::TestBuildLists::test_copy_free_tier_cap'` | ✅ | ✅ green (1 pass) |
| 07-01-05 | 01 | 1 | WR-01 | `pytest.ini` retains `testpaths = tests` (not `app/tests`) | static | `cd backend && pytest -n auto --no-cov tests/test_pytest_ini_testpaths.py` | ✅ | ✅ green (1 pass) — **filled by this audit** |
| 07-02-01 | 02 | 1 | IN-01 | `_apply_build_list_filters` helper defined once; invoked ≥2 times (count-select + main-select) | static | `cd backend && pytest -n auto --no-cov tests/test_build_lists_in01_helper.py` | ✅ | ✅ green (3 pass) |
| 07-03-01 | 03 | 1 | TD-03-01 | `test_runner_circuit_breaker.py` stub removed; replacement `test_runner_breaker.py` + `test_circuit_breaker.py` still collect | collection | `cd backend && pytest --collect-only --no-cov -q tests/crawlers/test_runner_breaker.py tests/crawlers/test_circuit_breaker.py` | N/A (manual) | ⬛ manual-only (one-shot deletion) |
| 07-03-02 | 03 | 1 | TD-03-02 | 11 dead helpers removed from `common_patterns.py`; full suite still passes | indirect | `cd backend && pytest -n auto` + `grep -rn "\\bget_standard_endpoint_dependencies\\b\\|\\bget_paginated_response\\b" backend/` (no matches) | N/A | ⬛ manual-only (caught indirectly by full-suite green + grep) |
| 07-03-03 | 03 | 1 | TD-04-WR01-conftest | 6 residual `db.query(...)` sites in `backend/tests/conftest.py` migrated to `select()+scalars()`; suite passes | indirect | `cd backend && pytest -n auto` + `grep -cE '^[^#]*\\b(db\\|db_session)\\.query\\(' backend/tests/conftest.py` returns `0` | N/A | ⬛ manual-only (migration correctness caught by full-suite green) |
| 07-04-01 | 04 | 1 | A-01 | Lifespan orphan sweeps wrapped in `bg_log_context("orphan-*-sweep")`; request_id is `bg:orphan-*:-` during sweep | unit | `cd backend && pytest -n auto --no-cov tests/test_lifespan_bg_log_context.py` | ✅ | ✅ green (3 pass) |
| 07-04-02 | 04 | 1 | TODO-02 | Per-adapter `crawler_parse_failure_per_adapter` alarm via `for_each` over 108 adapters; `terraform validate` green | infra | `cd terraform && terraform init -backend=false && terraform validate` | N/A | ⬛ manual-only (infra validation + operator `terraform plan` review per 07-04 Task 3) |
| 07-05-01 | 05 | 2 | NYQUIST-01 | 6 phase VALIDATION.md files (01-06) have `wave_0_complete: true`, `nyquist_compliant: true`, `status: accepted` | meta | `for N in 01 02 03 04 05 06; do grep -q 'wave_0_complete: true' .planning/phases/$N-*/$N-VALIDATION.md; done` | N/A | ⬛ manual-only (documentation frontmatter flip) |
| 07-06-01 | 06 | 2 | DOC-01 | REQUIREMENTS.md traceability: 59 rows `Satisfied`, 1 row `Pending` (SAFE-03 → Phase 8) | meta | `grep -c "\\| Satisfied \\|" .planning/REQUIREMENTS.md` returns `59`; `grep -c "\\| Pending \\|" .planning/REQUIREMENTS.md` returns `1` | N/A | ⬛ manual-only (documentation sync) |
| 07-06-02 | 06 | 2 | DOC-02 | REQUIREMENTS.md v1 requirements: 59 checkboxes `[x]`, 1 `[ ]` (SAFE-03) | meta | `grep -c "^- \\[x\\]" .planning/REQUIREMENTS.md` returns `59`; `grep -c "^- \\[ \\]" .planning/REQUIREMENTS.md` returns `1` | N/A | ⬛ manual-only (documentation sync) |
| 07-06-03 | 06 | 2 | DOC-03 | ROADMAP.md Progress table: Phases 1–6 `Complete` with dates; Phase 7 `In progress`; Phase 8 `Not started` | meta | `grep -cE '^\\| [1-6]\\. .*\\| Complete \\|' .planning/ROADMAP.md` returns `6` | N/A | ⬛ manual-only (documentation sync) |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ partial (environment-gated) · ⬛ manual-only*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.*

Phase 7 did not require new test-framework installs or shared fixtures. It consumed:
- `backend/tests/conftest.py` `db_session` fixture (SQLite in-memory) — used by all 4 WR/IN regression files
- `backend/tests/conftest.py` `postgres_engine` fixture (postgres-gated) — used by the WR-02 concurrency test
- `backend/tests/api/endpoints/test_build_lists.py` existing `test_user`, `get_auth_token`, `create_car_in_db` helpers — reused by IN-02 test
- Existing `pytest-asyncio` 1.3.0 plugin — used by A-01 lifespan regression tests
- Existing `terraform/` with `aws` provider 5.100.0 — used by TODO-02 `terraform validate`

One file was added by this audit to close the only fillable gap:
- [x] `backend/tests/test_pytest_ini_testpaths.py` — static-structure pin for WR-01 (3 assertions, <0.05s runtime)

---

## Manual-Only Verifications

| Behavior | Tech-Debt Item | Why Manual | Test Instructions |
|----------|----------------|------------|-------------------|
| `test_runner_circuit_breaker.py` stub removed | TD-03-01 | One-shot file deletion; reintroduction would require a new commit adding a skipped stub — not a regression class worth guarding | `test ! -f backend/tests/crawlers/test_runner_circuit_breaker.py && echo "OK"` |
| 11 dead helpers removed from `common_patterns.py` | TD-03-02 | Dead-helper reintroduction would be caught during code review; static grep check is cheaper than maintaining 11 "this function must not exist" tests | `grep -rn "\bget_standard_endpoint_dependencies\b\|\bverify_entity_ownership_or_admin\b\|\bget_paginated_response\b\|\bverify_ownership\b\|\bbuild_sorted_query\b\|\bget_common_dependencies\b\|\bget_admin_dependencies\b\|\bhandle_vote_operation\b\|\bremove_vote_operation\b\|\bhandle_report_creation\b\|\bget_standard_pagination_params\b" backend/app/ backend/tests/` — must return no matches (or only the `common_patterns.py` definition file, which was also scrubbed) |
| 6 `db.query` sites in conftest.py migrated | TD-04-WR01-conftest | Migration correctness is proven by the full pytest suite remaining green; a "must not use db.query" test would be a style-rule substitute for the live `test_session_query_regression.py` guard which already scopes `backend/app/` | `grep -cE '^[^#]*\b(db\|db_session)\.query\(' backend/tests/conftest.py` — must return `0` |
| Per-adapter parse-failure alarms via `for_each` | TODO-02 | Terraform infra validation is inherently gated on operator `terraform plan` review (Plan 07-04 Task 3) plus the 24h staging-bake per D-58. Not a pytest-shaped concern | `cd terraform && terraform init -backend=false && terraform validate` → `Success! The configuration is valid.`; operator reviews `terraform plan -var-file=<env>.tfvars` |
| 6 phase VALIDATION.md files Nyquist-compliant | NYQUIST-01 | Meta-process: this very validation is the closure. Each phase VALIDATION.md frontmatter is verified by the per-phase validation-execution-log section (Plan 07-05) | `for N in 01 02 03 04 05 06; do grep -q 'wave_0_complete: true' .planning/phases/$N-*/$N-VALIDATION.md || echo "MISSING $N"; done` — must print nothing |
| REQUIREMENTS.md traceability synced | DOC-01 | Documentation drift; grep-invariants in Plan 07-06 Task 1 acceptance criteria | `grep -c "\| Satisfied \|" .planning/REQUIREMENTS.md` = 59; `grep -c "\| Pending \|"` = 1 |
| REQUIREMENTS.md checkboxes synced | DOC-02 | Documentation drift | `grep -c "^- \[x\]" .planning/REQUIREMENTS.md` = 59; `grep -c "^- \[ \]"` = 1 |
| ROADMAP.md Progress table synced | DOC-03 | Documentation drift | `grep -cE '^\| [1-6]\. .*\| Complete \|' .planning/ROADMAP.md` = 6 |

---

## Validation Audit 2026-04-24

| Metric | Count |
|--------|-------|
| Tech-debt items closed by Phase 7 | 15 |
| COVERED (automated regression tests) | 6 (WR-04, WR-03, IN-02, IN-01, A-01, **WR-01 — filled by this audit**) |
| PARTIAL (environment-gated by design) | 1 (WR-02 postgres-gated) |
| MANUAL-ONLY (one-shot / indirect / docs / infra) | 8 (TD-03-01, TD-03-02, TD-04-WR01-conftest, TODO-02, NYQUIST-01, DOC-01, DOC-02, DOC-03) |
| Gaps found by this audit | 1 (WR-01) |
| Gaps resolved | 1 (WR-01 — `backend/tests/test_pytest_ini_testpaths.py`) |
| Gaps escalated | 0 |

### Commands Run (evidence)

| Command | Exit | Summary |
|---------|------|---------|
| `cd backend && pytest -n auto --no-cov tests/test_init_service_accounts.py tests/crawlers/test_crawler_user_fallback.py tests/test_build_lists_in01_helper.py tests/test_lifespan_bg_log_context.py` | 0 | 15 passed in 8.30s |
| `cd backend && pytest --no-cov tests/test_pytest_ini_testpaths.py -v` | 0 | 1 passed in 0.02s (new) |
| `cd backend && pytest --no-cov 'tests/api/endpoints/test_build_lists.py::TestBuildLists::test_copy_free_tier_cap' -v` | 0 | 1 passed in 0.52s |
| `cd backend && pytest --collect-only --no-cov -q tests/services/test_part_linker_concurrency.py` | 0 | 3 tests collected (1 new, postgres-gated) |
| `ls backend/tests/crawlers/test_runner_circuit_breaker.py` | non-zero | file gone (TD-03-01 confirmed) |
| `grep -c 'def _apply_build_list_filters' backend/app/api/endpoints/build_lists.py` | 0 | 1 (IN-01 helper present) |
| `grep -c 'bg_log_context' backend/app/main.py` | 0 | 5 (A-01 wiring present) |
| `grep -c 'crawler_parse_failure_per_adapter' terraform/monitoring.tf` | 0 | 1 (TODO-02 resource present) |
| `wc -l terraform/adapter_names.txt` | 0 | 108 lines (TODO-02 input present) |

---

## Validation Sign-Off

- [x] All covered tasks have `<automated>` verify commands; WR-02 is postgres-gated by design; 8 items are intrinsically manual-only (docs/infra/one-shot)
- [x] Sampling continuity: every automated-verify task is ≤10s; no batching required
- [x] Wave 0 covers all MISSING references (WR-01 filled by this audit via `test_pytest_ini_testpaths.py`)
- [x] No watch-mode flags in any command
- [x] Feedback latency <30s (Quick ~9s; Full suite ~30s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-24
