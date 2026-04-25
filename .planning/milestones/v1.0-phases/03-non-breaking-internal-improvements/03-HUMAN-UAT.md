---
status: complete
phase: 03-non-breaking-internal-improvements
source: [03-VERIFICATION.md]
started: 2026-04-22T22:10:00Z
updated: 2026-04-22T23:10:00Z
completed: 2026-04-22
result: measured (QUAL-01 cold-boot gain within measurement noise — finding accepted, refactor value retained as maintainability per 03-VERIFICATION.md)
---

## Current Test

[All 6 runs captured; finding: QUAL-01 cold-boot gain is within measurement noise, AST-parse proxy overstates end-to-end benefit]

## Tests

### 1. uvicorn --reload cold-boot startup latency (SC4 / QUAL-01 / D-28)
expected: AFTER median uvicorn cold-boot time is measurably lower than BEFORE median, after replacing the 8,412-line `car_generations_data.py` literal with JSON + `@lru_cache` loader. PR description must contain the literal strings `Startup latency (before):` and `Startup latency (after):`, each followed by 3 timing values.

Steps:
1. Check out main (pre-QUAL-01 commit) and run three cold `uvicorn app.main:app --host 0.0.0.0 --port 8000` invocations against a real PostgreSQL + SES environment; time each from process start to the "Application startup complete" log line. Record as `Startup latency (before): Xs, Ys, Zs`.
2. Check out the Phase 3 head and repeat three cold `uvicorn` invocations; record as `Startup latency (after): Xs, Ys, Zs`.
3. Paste both entries into the PR description under a "QUAL-01 startup latency" section.

#### Raw cold-boot (process-start → "Application startup complete"):

**AFTER** (main @ `d167c9c`, Phase 3 merged):
- Run 1 (pid 62198): 15:49:27.516 → 15:49:30.713 = **3.197s**
- Run 2 (pid 62839): 15:49:36.996 → 15:49:39.859 = **2.863s**
- Run 3 (pid 66426): 15:52:01.385 → 15:52:04.314 = **2.929s**
- Median: **2.929s**

**BEFORE** (`git checkout aabcdee`, pre-Phase-3):
- Run 1 (pid 76891): 15:59:39.392 → 15:59:42.223 = **2.831s**
- Run 2 (pid 77185): 15:59:49.218 → 15:59:50.027 = **0.809s**
- Run 3 (pid 77462): 15:59:56.657 → 15:59:57.486 = **0.829s**
- Median: **0.829s**

`Startup latency (before): 2.831s, 0.809s, 0.829s`
`Startup latency (after): 3.197s, 2.863s, 2.929s`

#### Finding: raw numbers are dominated by AWS credential-lookup noise, not QUAL-01

The orphan-sweep line "Unable to locate credentials" takes ~2s on every AFTER run and on BEFORE run 1, but returns **instantly** on BEFORE runs 2 and 3 (likely a boto3 credential-resolver cache kicking in after the first miss). That ±2s swing dwarfs any QUAL-01 effect.

| Run | init_cars end | Orphan sweep end | Sweep cost |
|-----|---------------|------------------|-----------:|
| AFTER R1 | 28.693 | 30.707 | 2.014s |
| AFTER R2 | 37.838 | 39.854 | 2.016s |
| AFTER R3 | 02.288 | 04.308 | 2.020s |
| BEFORE R1 | 40.199 | 42.216 | 2.017s |
| BEFORE R2 | 50.017 | 50.025 | 0.008s |
| BEFORE R3 | 57.477 | 57.484 | 0.007s |

#### Normalized comparison (process-start → `init_cars` complete, before the sweep noise):

| Run | AFTER | BEFORE |
|-----|------:|-------:|
| 1 | 1.177s | 0.807s |
| 2 | 0.842s | 0.799s |
| 3 | 0.903s | 0.820s |
| **Median** | **0.903s** | **0.807s** |

Normalized, **AFTER is ~96ms SLOWER than BEFORE at cold boot**. The JSON load via `importlib.resources` + first `@lru_cache` miss costs a bit more than Python loading the pre-compiled `.pyc` of the literal. The AST-parse proxy (12.3ms → 0.2ms) measures only one slice (module re-parse) and does not capture the JSON load + resource-resolution cost incurred once per process.

#### Honest assessment for PR body

The ROADMAP SC4 phrasing "uvicorn --reload startup latency is measurably reduced" is **not supported** by this end-to-end measurement. What QUAL-01 actually delivers:

1. **Maintainability win (real, substantial):** 8,412 lines of Python → 108-line shim + external JSON asset. The data is now editable without re-flowing a massive Python literal.
2. **Hot-reload savings (small, niche):** During `uvicorn --reload` dev loops where the `car_generations_data` module re-parses on code change, each reload saves ~12ms. Meaningful only for developers iterating rapidly on code that imports the module — not a cold-boot win.
3. **Cold-boot impact (slightly negative):** JSON load + `importlib.resources` first-call cost adds ~100ms at process start vs. the pre-compiled `.pyc` of the literal.

#### Recommendation

When drafting the PR body, include the raw numbers verbatim AND an honest note that the cold-boot delta is within noise and the real win is maintainability, not startup latency. Do not frame this as a performance improvement.

result: measured

## Summary

total: 1
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- **SC4 phrasing mismatch:** ROADMAP Phase 3 success criterion 4 ("uvicorn --reload startup latency is measurably reduced") is contradicted by end-to-end measurement. The refactor's value is maintainability, not latency. Consider amending SC4 language to "car_generations_data.py reduced from 8,412 → 108 lines via JSON extraction with `@lru_cache` loader" for future milestones' clarity. Non-blocking for phase completion — phase goal (crawler hardening + Pydantic v1 elimination) is met independently of this nuance.



user manually fully signs off
