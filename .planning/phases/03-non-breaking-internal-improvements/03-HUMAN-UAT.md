---
status: partial
phase: 03-non-breaking-internal-improvements
source: [03-VERIFICATION.md]
started: 2026-04-22T22:10:00Z
updated: 2026-04-22T22:50:00Z
---

## Current Test

[AFTER timings captured; BEFORE baseline still pending for PR body]

## Tests

### 1. uvicorn --reload cold-boot startup latency (SC4 / QUAL-01 / D-28)
expected: AFTER median uvicorn cold-boot time is measurably lower than BEFORE median, after replacing the 8,412-line `car_generations_data.py` literal with JSON + `@lru_cache` loader. PR description must contain the literal strings `Startup latency (before):` and `Startup latency (after):`, each followed by 3 timing values.

Steps:
1. Check out main (pre-QUAL-01 commit) and run three cold `uvicorn app.main:app --host 0.0.0.0 --port 8000` invocations against a real PostgreSQL + SES environment; time each from process start to the "Application startup complete" log line. Record as `Startup latency (before): Xs, Ys, Zs`.
2. Check out the Phase 3 head and repeat three cold `uvicorn` invocations; record as `Startup latency (after): Xs, Ys, Zs`.
3. Paste both entries into the PR description under a "QUAL-01 startup latency" section.

Automated proxy already captured by Plan 03-04 (AST-parse of car_generations_data module: 12.3ms → 0.2ms, 98% reduction). This manual step confirms the end-to-end uvicorn cold-boot delta that ROADMAP SC4 binds to.

result: partial — AFTER measurements captured on 2026-04-22 against Phase 3 head:
  - Run 1 (pid 62198): started 15:49:27.516 → startup complete 15:49:30.713 = **3.197s**
  - Run 2 (pid 62839): started 15:49:36.996 → startup complete 15:49:39.859 = **2.863s**
  - Run 3: not yet captured

  `Startup latency (after): 3.197s, 2.863s, <pending>`

Observations:
- Cold-boot wall time is dominated by `init_cars` (1002 car-generation row sync ~1s) and the orphan-sweep AWS-credential timeout (~2s), not the car_generations module parse. That matches the AST-parse proxy showing the module-parse slice is only ~0.2ms post-refactor.
- BEFORE baseline (pre-Phase-3 commit `aabcdee`) still needs a matching 3-run capture against the same local PG + env; the AFTER-vs-BEFORE delta is expected to sit within the noise floor of the dominating init steps (single-digit-ms on the parse, not seconds).

Remaining for PR body:
- 1 more AFTER run.
- 3 BEFORE runs on `git checkout aabcdee` (or any commit prior to e8e9179 `feat(03-04): lazy JSON loader for car-generations`).
- `Startup latency (before):` + `Startup latency (after):` lines added to PR description per D-28.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
