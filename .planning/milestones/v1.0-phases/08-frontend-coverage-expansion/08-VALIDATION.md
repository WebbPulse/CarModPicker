---
phase: 8
slug: frontend-coverage-expansion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-24
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. See `08-RESEARCH.md` §7 for the full Validation Architecture; this file is the condensed contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 3.2.4 + @vitest/coverage-v8 3.2.4 + @testing-library/react 16.1.0 + jsdom 25.0.1 |
| **Config file** | `frontend/vitest.config.ts` |
| **Quick run command** | `cd frontend && npm test -- --run` (no coverage, fast iteration) |
| **Full suite command** | `cd frontend && npm run test:coverage` (full suite + coverage report) |
| **Estimated runtime** | ~30–90 seconds (grows with added tests; Vitest per-file parallel) |

---

## Sampling Rate

- **After every task commit:** `cd frontend && npm test -- --run <changed test files>` (scoped to touched files).
- **After every plan wave:** `cd frontend && npm test -- --run` (full suite, no coverage) — proves nothing else regressed.
- **Before `/gsd-verify-work`:** `cd frontend && npm run test:coverage` — full suite must be green AND meet D-06 thresholds.
- **Max feedback latency:** ~90 seconds for full suite; <15 seconds per changed test file.

---

## Per-Task Verification Map

> Populated by the planner during plan generation. Every plan task MUST include an `<automated>` verify line and a row here. The table below is a template — the planner fills actual rows once plans land.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | SAFE-03 | — | N/A (test-only) | infra | `cd frontend && npm test -- --run` | ❌ W0 | ⬜ pending |
| *(planner fills 19+ more rows)* | | | | | | | | | |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/test/setup.ts` — add `vi.mock('../api/client', ...)` per D-18 without removing existing `vi.mock('../services/Api', ...)` (D-19).
- [ ] `frontend/src/test/utils/test-mocks.ts` — add `mockAdminUser`, `mockSuperuserUser` per D-05.
- [ ] `frontend/src/test/utils/test-utils.tsx` — add `testScenarios.adminAuthenticated`, `testScenarios.superuserAuthenticated` per D-05.
- [ ] `frontend/src/test/mocks/admin/` — new directory with per-surface fixture files (`jobs.ts`, `reports.ts`, `bugs.ts`, `users.ts`, `crawlers.ts`, `stats.ts`, `curation.ts`) per D-06.
- [ ] `frontend/src/test/utils/async.ts` — `vi.useFakeTimers()` helpers per D-07 (EventSource stub dropped per research — CrawlerAdmin has no SSE).
- [ ] `frontend/src/test/guards/` — relocate `no-process-env.test.ts`, `no-legacy-gradient.test.ts`, `extension-content-type.test.ts` with short README per D-17.
- [ ] `frontend/vitest.config.ts` `coverage.exclude` — add `src/main.tsx` + `src/types/Api.ts` with inline rationale per D-13.
- [ ] `.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt` — committed per D-24.
- [ ] `cd frontend && npm test -- --run` exits 0 after setup.ts refactor (proves the 9 existing tests still pass — gates the whole wave train).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fail-force proof: threshold block actually enforces | SAFE-03 / D-22 | One-time CI proof, not a repeatable assertion | Wave 5 plan: (1) uncomment thresholds with values ABOVE measured (e.g. `lines: 95`); (2) run `npm run test:coverage`; confirm non-zero exit + "does not meet global threshold" message; (3) restore D-06 values (`lines: 60, functions: 50, branches: 50, statements: 60`); (4) confirm exit 0. Paste both outputs into the Wave 5 SUMMARY.md. |
| `frontend-ci.yml` goes red when thresholds are violated | SAFE-03 | Needs a real PR in the CI environment to verify | Wave 5 verify step: push the threshold-enable commit; confirm `frontend-ci.yml` run is green; optionally, cut a throwaway branch that deletes a test file and confirm the same workflow goes red for threshold drop (do NOT merge). |

---

## Meta-Checks Against Empty / Ceremonial Tests

Three grep-level guards the planner MUST bake into every Wave 1–4 plan's acceptance criteria (from RESEARCH.md §7):

1. **No empty describe blocks** — every `*.test.*` file touched in a task has ≥1 `it(` / `test(` inside a `describe`.
2. **No committed `.skip(`** — `grep -rn "\.skip(" src --include="*.test.*" | grep -v "^\s*\*\|^\s*//" | wc -l` returns 0 (or matches an allowlist).
3. **Every `.test.*` file has ≥1 `expect(`** — `for f in $(find src -name '*.test.*' -type f); do grep -q "expect(" "$f" || echo "No assertions in $f"; done` emits no output.

---

## Per-Wave Quick Reference

| Wave | Surface | Quick Validate | Meta-Check |
|------|---------|----------------|-----------|
| 0 | Baseline + shared infra | `cd frontend && npm test -- --run` | 9 existing tests all pass; `08-COVERAGE-BASELINE.txt` exists with per-file numbers |
| 1 | API modules | `cd frontend && npm test -- --run src/api/` | assertion-count > it-block-count per file |
| 2 | Hooks + Contexts | `cd frontend && npm test -- --run src/hooks/ src/contexts/` | every non-trivial hook test uses `renderHook`; every context test has ≥1 `act(`/`fireEvent` |
| 3 | Customer pages | `cd frontend && npm test -- --run src/pages/` | every page test has ≥1 `render(` and ≥3 assertions |
| 4 | Admin pages | `cd frontend && npm test -- --run src/pages/admin/` | `CrawlerAdmin.test.tsx` uses `vi.useFakeTimers()` |
| 5 | Gap-fill + threshold enable | `cd frontend && npm run test:coverage` | summary meets 60/50/50/60; fail-force proof recorded |

---

## Phase Gate (Before `/gsd-verify-work`)

1. `cd frontend && npm run test:coverage` → exit 0 with Lines ≥ 60, Functions ≥ 50, Branches ≥ 50, Statements ≥ 60.
2. `cd frontend && npm test -- --run` → exit 0, all tests passing.
3. `cd frontend && npm run lint` → exit 0.
4. `cd frontend && npm run type-check` → exit 0.
5. The commented `coverage.thresholds` block in `vitest.config.ts` is gone; uncommented block matches D-06 values exactly.
6. `frontend-ci.yml` green on the PR.
7. Fail-force proof pasted in Wave 5 SUMMARY.md per the Manual-Only Verifications row above.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (Vitest defaults are non-watching with `--run`; verify no plan calls `vitest` without `--run`)
- [ ] Feedback latency < 90s full suite / 15s per-file
- [ ] `nyquist_compliant: true` set in frontmatter (after planner populates per-task rows and checker confirms)

**Approval:** pending
