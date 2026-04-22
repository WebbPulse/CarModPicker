---
phase: 03-non-breaking-internal-improvements
plan: 03
subsystem: crawler/result-dict-and-email-renderer
tags: [crawler, reporting, email, ses, observability, CRAWL-07]
requires:
  - Phase 03 Plan 02 (runner result dict with parse_miss_urls, health_skipped keys; pybreaker wired)
provides:
  - runner.py result-dict delta: parse_failures, sample_failure_urls, elapsed_seconds (on success + health-skip paths; breaker-bail inherits via `break` → success return)
  - _render_crawler_result_html ParseFailures block (per-adapter colspan=5 row under main row, silent for healthy adapters)
  - URL-truncation rule: first-120 + ellipsis + last-40 for samples >160 chars (Pitfall PR-01)
affects:
  - Phase 2 OBS-02 (CloudWatch EMF): reads parse_failures + elapsed_seconds directly (D-24 / D-38) — zero schema negotiation cost
tech-stack:
  added: []
  patterns:
    - Additive result-dict key extension (no removals — Phase 2 OBS-02 schema-stable consumer)
    - Colspan-row render pattern for per-adapter annotations under main row (distinct from collapsed <details> used by failure samples)
    - URL truncation via first-N + ellipsis + last-M preserves host + path-head + file-extension tail
    - Encounter-order (not sorted, not evenly sampled) first-N slice from an accumulator list (D-23)
key-files:
  created:
    - backend/tests/crawlers/test_runner_result_dict.py
  modified:
    - backend/app/crawlers/runner.py
    - backend/app/core/email.py
    - backend/tests/test_email.py
decisions:
  - parse_failures is an alias for skipped_not_product — intent is distinct from transport/HTTP "errors" (D-22)
  - sample_failure_urls slice is list[str] (URL-only per D-23), not the full list[dict] shape preserved in parse_miss_urls
  - elapsed_seconds captured AFTER check_health so it measures URL-loop cost exclusively; health-skip path returns 0.0
  - Breaker-bail inherits new keys automatically via `break` → common success-return (no separate return-dict site to extend)
  - URL truncation rule: first-120 + ellipsis + last-40 (bounds email body at ~800 chars/adapter for 5 samples)
metrics:
  duration_minutes: ~7
  completed_date: 2026-04-22
  tasks_completed: 2
  files_created: 1
  files_modified: 3
  tests_added: 7
  full_crawler_email_suite: 1264 passed, 1 skipped
---

# Phase 03 Plan 03: Crawler Result-Dict + Email ParseFailures Summary

Extended the per-adapter crawler result dict with three new keys (`parse_failures`, `sample_failure_urls`, `elapsed_seconds`) and added a per-adapter "ParseFailures: N / total — samples: <urls>" block to the SES job-report email so operators can distinguish "site returned 500" from "our parser returned None from a valid HTML page." All 7 new tests GREEN; 1264/1265 crawler + email tests GREEN (same skip baseline as Plan 03-02); OpenAPI snapshot unchanged.

## One-liner

Added `parse_failures` + `sample_failure_urls[:5]` + `elapsed_seconds` keys to the runner's result dict and rendered a per-adapter ParseFailures row in the SES email so parser drift is visible without grepping logs — and Phase 2 OBS-02 can read both new metric keys directly with zero schema negotiation.

## What Landed

### Task 1 — 7 new tests encoding CRAWL-07 behavior (commit `a6e9b80`, RED)

`backend/tests/crawlers/test_runner_result_dict.py` (new, 4 tests + autouse `_clear_breakers` fixture matching `test_runner_breaker.py` pattern):

| Test | Asserts |
|------|---------|
| `test_result_dict_includes_parse_failures` | After a stubbed run with 7 parse-miss URLs, `result["skipped_not_product"] == 7` AND `result["parse_failures"] == 7` |
| `test_sample_failure_urls_first_five_urls_only` | `len(result["sample_failure_urls"]) == 5` AND every entry is a `str` (not a dict — the "url" key was extracted per D-23) |
| `test_sample_failure_urls_preserves_order` | `result["sample_failure_urls"] == urls[:5]` — encounter order, not evenly sampled, not sorted |
| `test_elapsed_seconds_non_negative` | `"elapsed_seconds" in result`, `isinstance(result["elapsed_seconds"], float)`, `result["elapsed_seconds"] >= 0.0` |

`backend/tests/test_email.py` (appended 3 module-level tests after existing `TestJobReportRendering` class):

| Test | Asserts |
|------|---------|
| `test_crawler_parse_failures_block_renders` | With `parse_failures=3, total=10, sample_failure_urls=[3 urls]`, rendered HTML contains `ParseFailures:`, `3 / 10`, AND all three sample URLs verbatim |
| `test_crawler_parse_failures_block_omitted_when_empty` | With `parse_failures=0`, rendered HTML does NOT contain `ParseFailures:` (silent for healthy adapters) |
| `test_crawler_parse_failures_url_truncation` | With a 300-char URL in samples, rendered HTML contains `…` (ellipsis) AND the full 300-char URL is NOT present verbatim |

RED state at commit: 6 of 7 tests fail as expected (KeyError on missing result-dict keys; `ParseFailures:` literal absent from renderer). The `omitted_when_empty` test trivially passes RED because "ParseFailures:" never appears without the Task 2 renderer block — a falsifiable absence-assertion is strengthened post-GREEN because the same string never leaks from the healthy-adapter path in full regression.

### Task 2 — Runner + email renderer extensions (commit `c5a6bac`, GREEN)

`backend/app/crawlers/runner.py`:

**ADD zone A (line ~520, immediately before the URL loop):**
```python
t0 = time.monotonic()
```
Captured AFTER the `check_health()` gate (Plan 02) so `elapsed_seconds` measures URL-loop cost exclusively and is never polluted by probe timeouts.

**ADD zone B (success-path return, 3 new keys at end of dict, line ~710):**
```python
"parse_failures": skipped_not_product,
"sample_failure_urls": [p["url"] for p in parse_miss_urls[:5]],
"elapsed_seconds": round(time.monotonic() - t0, 3),
```

**ADD zone C (health-skipped early-return, line ~428):**
```python
"parse_failures": 0,
"sample_failure_urls": [],
"elapsed_seconds": 0.0,
```
Health-skip occurs before `t0` is captured → elapsed 0.0. No URLs processed → parse_failures 0, samples [].

**Breaker-bail path (line ~559):** uses `break` to fall through to the common success-path return, so it automatically inherits the three new keys. No separate return-dict site needed.

`backend/app/core/email.py` — `_render_crawler_result_html`:

Inserted a colspan=5 row-append directly after the per-adapter main row-append (line ~327), guarded on `parse_failures > 0 AND samples`. Local `_trunc()` closure implements Pitfall PR-01 (first-120 + ellipsis + last-40 for URLs >160 chars). Samples are passed through the existing `_escape_html` helper (already in the file — no need for the `_html_std.escape` fallback the plan mentioned as a contingency).

```python
if parse_failures > 0 and samples:
    def _trunc(u: str) -> str:
        return u if len(u) <= 160 else f"{u[:120]}…{u[-40:]}"
    sample_html = "<br/>".join(_escape_html(_trunc(u)) for u in samples)
    rows_html.append(
        '<tr><td colspan="5" ...>'
        f'<strong>ParseFailures:</strong> {parse_failures} / {r.get("total", 0)} — '
        f'samples: {sample_html}'
        '</td></tr>'
    )
```

## Baseline Committed

| Metric | Value |
|--------|-------|
| `"parse_failures"` occurrences in runner.py | 2 (success + health-skip return sites) |
| `"sample_failure_urls"` occurrences in runner.py | 2 |
| `"elapsed_seconds"` occurrences in runner.py | 2 |
| `time.monotonic()` occurrences in runner.py | 2 (`t0 = ...` + `round(... - t0, 3)`) |
| `parse_miss_urls[:5]` occurrences in runner.py | 1 |
| `ParseFailures:` occurrences in email.py | 1 |
| `sample_failure_urls` occurrences in email.py | 1 |
| New test file | `backend/tests/crawlers/test_runner_result_dict.py` (4 tests) |
| New tests in `backend/tests/test_email.py` | 3 (`test_crawler_parse_failures_*`) |
| Full crawler + email suite | 1264 passed, 1 skipped (+18 vs Plan 02 baseline of 1246, no regression) |
| OpenAPI snapshot | unchanged |

## Deviations from Plan

None — plan executed exactly as written. Two small notes:

1. **No `_html_std` contingency needed.** The plan offered `import html as _html_std` as a fallback if `_escape_html` wasn't already defined in `email.py`. It IS defined (line 159), so the block uses `_escape_html(_trunc(u))` directly — one fewer import, no behavioral difference.

2. **`test_crawler_parse_failures_block_omitted_when_empty` passed RED trivially** — the literal `ParseFailures:` cannot appear in the rendered HTML before Task 2 adds the emitting code. This is intrinsic to negative assertions; the post-GREEN full-suite regression (1264 / 1265 passing) proves the same absence claim holds once the block CAN emit, which is the stronger invariant.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `parse_failures` as an ALIAS for `skipped_not_product` (not a rename) | D-22 / RESEARCH "Result-dict schema preserved". Downstream consumers (email renderer, Phase 2 OBS-02) can read either key; existing tests/consumers that read `skipped_not_product` are unaffected. |
| `sample_failure_urls` is `list[str]` (URL-only), not `list[dict]` | D-23. Email renderer + CloudWatch EMF don't need the wrapper dict; slimming the shape at the runner boundary avoids forcing every consumer to unwrap `{"url": "..."}`. The full `parse_miss_urls` dict list remains unchanged for the `_render_crawler_failure_samples` <details> block. |
| `elapsed_seconds` captured AFTER `check_health()` | Probe has its own 5s timeout (Plan 02). Including it in the URL-loop metric would pollute the signal used for "is this adapter slow or the upstream slow?". Health-skip path returns 0.0 which is unambiguous. |
| First-5, encounter order (not evenly sampled, not sorted) | D-23. Operators debugging parser drift want the first miss because it's usually representative of the template change. Sampling would introduce noise. |
| URL truncation rule: first-120 + ellipsis + last-40 | Pitfall PR-01. Preserves host + path-head (diagnosis cue) AND file-extension tail (product-id cue), bounding body growth to ≤800 chars per adapter (5 × 160). |
| Breaker-bail inherits new keys via `break` → success return (no separate return-dict site) | The breaker-bail path in `run_crawler()` uses `break` to exit the URL loop and falls through to the common success return at the bottom. Adding a separate return dict in the `except CircuitBreakerError` handler would be dead code (the current flow already flows through the success-return). The plan called out a "breaker-bail return dict" but that's a phantom site in the current structure — both paths converge. |
| Append email block AFTER the main adapter row (not at the row-end) | The `_render_crawler_failure_samples(results)` function already renders a per-adapter `<details>` block AFTER the per-adapter table with richer info. The ParseFailures block's purpose is different — it's a tight, always-visible counter row UNDER each main row when `parse_failures > 0`, giving operators a glanceable metric without expanding the details. Both blocks can coexist. |

## Threat Flags

None — all 5 threats in the plan's `<threat_model>` (T-03-03-01 through T-03-03-05) are handled by the shipped code:

- **T-03-03-01** (credential leak in sample URLs): accepted — retailer product URLs are sitemap-public; no NEW data exposure vs existing `error_urls`/`parse_miss_urls` keys.
- **T-03-03-02** (`<script>`-tag injection): mitigated — `_escape_html` wrapper escapes `<`, `>`, `&`, `"` before emission. Existing helper, test coverage via `test_crawler_parse_failures_block_renders` implicitly asserts the exact-URL survives (round-trip through escape must produce the same URL since retailer URLs don't contain `<` / `>` / `&`).
- **T-03-03-03** (long URL DoS): mitigated — `_trunc()` caps at 160 chars; verified by `test_crawler_parse_failures_url_truncation`.
- **T-03-03-04** (SES send-frequency change): mitigated — CRAWL-07 changes content only, not the send trigger (end of crawler run) or recipients.
- **T-03-03-05** (malicious adapter returning fake samples): accepted — adapter code reviewed at PR time; out-of-scope threat model.

No new security-relevant surface introduced.

## Unblocks

- **Phase 2 OBS-02 (CloudWatch EMF metrics):** `parse_failures` and `elapsed_seconds` are now first-class keys on every result dict (success, breaker-bail, health-skip). A downstream EMF emitter can do `metric("ParseFailures", r["parse_failures"])` and `metric("AdapterDurationSeconds", r["elapsed_seconds"])` with zero schema-change ceremony (D-24 / D-38).
- **All Phase 3 CRAWL-0x requirements (CRAWL-01 through CRAWL-07) complete.**

## Self-Check: PASSED

Verified all claimed artifacts exist on disk and all claimed commits exist in the worktree branch history.

**Files on disk:**
- FOUND: `backend/tests/crawlers/test_runner_result_dict.py` — 4 `def test_`, 7 occurrences of `parse_failures`, 9 of `sample_failure_urls`, 7 of `elapsed_seconds`
- FOUND: `backend/tests/test_email.py` — 3 `def test_crawler_parse_failures_*`
- FOUND: `backend/app/crawlers/runner.py` — `"parse_failures"` (2), `"sample_failure_urls"` (2), `"elapsed_seconds"` (2), `time.monotonic()` (2), `parse_miss_urls[:5]` (1)
- FOUND: `backend/app/core/email.py` — `ParseFailures:` (1), `sample_failure_urls` (1)

**Commits in worktree branch:**
- FOUND: `a6e9b80` — test(03-03): add failing tests for result-dict + email ParseFailures block (RED)
- FOUND: `c5a6bac` — feat(03-03): extend runner result dict + email renderer with ParseFailures (GREEN)

**Test suites:**
- PASSED: `python -m pytest -n auto tests/crawlers/test_runner_result_dict.py tests/test_email.py` → 18 passed
- PASSED: `python -m pytest -n auto tests/crawlers/ tests/test_email.py` → 1264 passed, 1 skipped (no regression)
- PASSED: `python -m pytest -n auto tests/test_openapi_snapshot.py` → 1 passed (OpenAPI unchanged)

## TDD Gate Compliance

Plan 03 follows the RED → GREEN cycle:
- **RED gate:** commit `a6e9b80` (`test(03-03): ...`) — 7 new tests, 6 fail as expected; 1 passes trivially (absence assertion before emitter exists).
- **GREEN gate:** commit `c5a6bac` (`feat(03-03): ...`) — runner + email extensions wired; 18 / 18 targeted tests green; full crawler + email suite 1264 passed + 1 skipped.

REFACTOR gate: not required (no cleanup-only changes needed).
