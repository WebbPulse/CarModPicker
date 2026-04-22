---
phase: 3
slug: non-breaking-internal-improvements
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source of truth for the Per-Task Verification Map is `03-RESEARCH.md` §"Validation Architecture" — this file carries the frontmatter + sampling-rate contract and is updated with per-task rows as plans land.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-xdist + pytest-cov |
| **Config file** | `backend/pytest.ini` (existing; `--cov-fail-under=51` landed in Phase 1) |
| **Quick run command** | `pytest -n auto backend/tests/crawlers/test_adapter_discovery.py backend/tests/test_pydantic_v1_regression.py backend/tests/test_on_event_regression.py backend/tests/test_logger_migration_regression.py -x` |
| **Full suite command** | `pytest -n auto --cov=app --cov-fail-under=51` |
| **Estimated runtime** | ~5s quick / ~90s full |

All new tests must be worker-safe under `-n auto --dist=loadfile`.

---

## Sampling Rate

- **After every task commit:** Run the quick command above (~5s)
- **After every plan wave:** Run `pytest -n auto backend/tests/crawlers/ backend/tests/ -x`
- **Before `/gsd-verify-work`:** Full suite must be green; `grep -rn "Depends(get_logger)" backend/app/` returns zero; OpenAPI snapshot unchanged
- **Max feedback latency:** 5 seconds (quick command)

---

## Per-Task Verification Map

> Source of truth: `03-RESEARCH.md` §"Validation Architecture" → "Phase Requirements → Test Map" (21 rows: 11 REQ-IDs + 1 characterization regression row).
> This table is updated per-task as plans are written; the planner MUST populate it when creating `*-PLAN.md` files.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| _TBD by planner_ | — | — | CRAWL-01..07, QUAL-01/02/03/07 | — / V5 (Pydantic) | see RESEARCH.md | unit + integration | see RESEARCH.md per-REQ command | ❌ W0 for 11 files | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Test infrastructure (`pytest.ini`, `conftest.py`, fixtures) exists. These test files must be created during Phase 3 execution (Wave 0 per plan):

- [ ] `backend/tests/crawlers/test_adapter_discovery.py` — CRAWL-01, CRAWL-02, CRAWL-03
- [ ] `backend/tests/crawlers/test_circuit_breaker.py` — CRAWL-04 (pybreaker unit)
- [ ] `backend/tests/crawlers/test_runner_breaker.py` — CRAWL-04 (runner integration)
- [ ] `backend/tests/crawlers/test_compute_adapter_workers.py` — CRAWL-05 (formula)
- [ ] `backend/tests/crawlers/test_parallel_session_isolation.py` — CRAWL-05 (SessionLocal per worker)
- [ ] `backend/tests/crawlers/test_health_check.py` — CRAWL-06
- [ ] `backend/tests/crawlers/test_runner_result_dict.py` — CRAWL-07 (result dict keys)
- [ ] `backend/tests/test_email.py` — extend with CRAWL-07 renderer test case (file exists)
- [ ] `backend/tests/test_car_generations_loader.py` — QUAL-01
- [ ] `backend/tests/test_pydantic_v1_regression.py` — QUAL-02
- [ ] `backend/tests/test_on_event_regression.py` — QUAL-03 (may merge with QUAL-02)
- [ ] `backend/tests/test_logger_migration_regression.py` — QUAL-07

No framework install needed — pytest + pytest-xdist + pytest-cov already in dev stack.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `uvicorn --reload` startup latency measurably improves | QUAL-01 (success criterion #4 from ROADMAP) | One-shot measurement; no value in CI gate | `time uvicorn app.main:app --reload` (Ctrl+C at "Application startup complete"), 3 cold runs before change + 3 runs after change. Record median in PR description per CONTEXT D-28. |

All other Phase 3 behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies listed in their plan
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all 12 MISSING test files above
- [ ] No watch-mode flags (pytest runs are one-shot with `-x`)
- [ ] Feedback latency < 5s for quick command
- [ ] `nyquist_compliant: true` set in frontmatter once Per-Task Verification Map is populated by the planner

**Approval:** pending
