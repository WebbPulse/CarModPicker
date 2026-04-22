---
phase: 01-safety-nets-ci-hardening
plan: 07
subsystem: testing
tags: [crawlers, characterization, fixtures, tier0_http, tier1_tls, pytest, s3, minio]

# Dependency graph
requires:
  - phase: 01-safety-nets-ci-hardening
    provides: plan 04 coverage gates (--cov-fail-under=51)

provides:
  - "5 committed product.html fixtures from carmodpicker-local-crawl MinIO bucket"
  - "5 committed expected.json snapshots (deterministic, sort_keys=True)"
  - "5 characterization tests pinning parse_product_page() output for Phase 3 refactor safety"
  - "CONTEXT.md D-21 corrected to reference correct crawl-data bucket names"

affects: [03-crawler-refactor, CRAWL-01, CRAWL-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Characterization test pattern: commit HTML fixture + expected.json, parse in test, assert equality (image_urls as sets)"
    - "Deterministic JSON serialization: json.dumps(asdict(payload), indent=2, sort_keys=True)"
    - "Regeneration one-liner embedded in each test file as comment"

key-files:
  created:
    - backend/tests/crawlers/fixtures/briantooleyracing/product.html
    - backend/tests/crawlers/fixtures/briantooleyracing/expected.json
    - backend/tests/crawlers/fixtures/amsperformance/product.html
    - backend/tests/crawlers/fixtures/amsperformance/expected.json
    - backend/tests/crawlers/fixtures/texasspeed/product.html
    - backend/tests/crawlers/fixtures/texasspeed/expected.json
    - backend/tests/crawlers/fixtures/cobbtuning/product.html
    - backend/tests/crawlers/fixtures/cobbtuning/expected.json
    - backend/tests/crawlers/fixtures/subispeed/product.html
    - backend/tests/crawlers/fixtures/subispeed/expected.json
    - backend/tests/crawlers/test_characterization_briantooleyracing.py
    - backend/tests/crawlers/test_characterization_amsperformance.py
    - backend/tests/crawlers/test_characterization_texasspeed.py
    - backend/tests/crawlers/test_characterization_cobbtuning.py
    - backend/tests/crawlers/test_characterization_subispeed.py
  modified:
    - .planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md (D-21 bucket name correction)

key-decisions:
  - "Swapped tier2_browser adapters (summitracing, ecstuning) for tier0/tier1 alternatives — user confirmed tier2_browser is currently broken/non-functional"
  - "Final 5 picks: briantooleyracing (tier0), amsperformance (tier0), subispeed (tier0), texasspeed (tier1), cobbtuning (tier1) — 3x tier0_http + 2x tier1_tls"
  - "HTML sourced from carmodpicker-local-crawl MinIO bucket (localhost), crawl_html/by_url/<hash>.html key pattern"
  - "CobbTuning price_cents=null is correct adapter behavior — Cobb hydrates price client-side, not in initial HTML"
  - "image_urls compared as sets in tests to tolerate CDN ordering variance"

patterns-established:
  - "Fixture layout: backend/tests/crawlers/fixtures/<adapter_name>/{product.html,expected.json}"
  - "Test naming: test_characterization_<adapter_name>.py (distinguishes from per-field unit tests)"
  - "Class-name import keying (not ADAPTER_NAME) per D-23 — switch to ADAPTER_NAME when Phase 3 CRAWL-02 lands"

requirements-completed: [SAFE-07]

# Metrics
duration: 55min
completed: 2026-04-22
---

# Phase 01 Plan 07: Crawler Adapter Characterization Summary

**5 characterization tests pinning parse_product_page() output across 3×tier0_http + 2×tier1_tls adapters using real archived HTML from MinIO crawl bucket**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-04-22T08:00:00Z (approx)
- **Completed:** 2026-04-22T08:54:36Z
- **Tasks:** 3 (fixtures + expected.json, tests, D-21 amendment)
- **Files modified:** 16

## Accomplishments

- Probed localhost MinIO bucket (`carmodpicker-local-crawl`) and identified 5 adapters with real archived product HTML
- Downloaded and committed 5 HTML fixtures (241KB–2.5MB each) and computed 5 deterministic expected.json files
- Wrote 5 characterization tests; all 5 pass under `pytest -n auto`; pyright and black clean
- Corrected CONTEXT.md D-21: `carmodpicker-prod-user-images` was wrong (user images bucket); correct crawl archives live in `carmodpicker-local-crawl` (local) and `carmodpicker-production-crawl-data` (prod)

## Adapter Picks

| Adapter | Tier | Class | S3 Key (local bucket) | HTML Size | Price | Images |
|---------|------|-------|----------------------|-----------|-------|--------|
| briantooleyracing | tier0_http | BrianTooleyRacingAdapter | crawl_html/by_url/01825a44fd1e0276.html | 464KB | $407.84 | 1 |
| amsperformance | tier0_http | AMSPerformanceAdapter | crawl_html/by_url/0111dee13e33b18c.html | 349KB | $569.95 | 4 |
| subispeed | tier0_http | SubispeedAdapter | crawl_html/by_url/00af33976a14140b.html | 2.5MB | $295.00 | 3 |
| texasspeed | tier1_tls | TexasSpeedAdapter | crawl_html/by_url/003da4fa57ef4dc7.html | 924KB | $31.26 | 5 |
| cobbtuning | tier1_tls | CobbTuningAdapter | crawl_html/by_url/009ea42926620548.html | 241KB | null* | 12 |

*CobbTuning hydrates price client-side — `price_cents: null` is the correct adapter behavior for archived HTML.

**Bucket used:** `carmodpicker-local-crawl` (MinIO localhost, endpoint http://localhost:9000)

**Key pattern:** `crawl_html/by_url/<sha256(url)[:16]>.html`

**Tier2_browser excluded:** summitracing and ecstuning were the original plan picks, but user confirmed tier2_browser adapters are currently non-functional. Replaced with subispeed (tier0_http) for the 5th slot, giving a 3+2 split rather than 2+1+2.

## Task Commits

1. **Task 2: Fixtures + expected.json** - `6880532` (feat)
2. **Task 3: 5 characterization test files** - `62c844c` (test)
3. **D-21 amendment** - `6ac4390` (docs)

## Files Created/Modified

- `backend/tests/crawlers/fixtures/briantooleyracing/product.html` — ARP head stud kit product page (Magento, BTR)
- `backend/tests/crawlers/fixtures/briantooleyracing/expected.json` — Deterministic parse output
- `backend/tests/crawlers/fixtures/amsperformance/product.html` — R8/Huracan sway bar end links (WooCommerce)
- `backend/tests/crawlers/fixtures/amsperformance/expected.json` — Deterministic parse output
- `backend/tests/crawlers/fixtures/subispeed/product.html` — OLM carbon fiber switch panel covers (Shopify)
- `backend/tests/crawlers/fixtures/subispeed/expected.json` — Deterministic parse output
- `backend/tests/crawlers/fixtures/texasspeed/product.html` — Aeromotive 10-micron filter element (Magento/Hyva)
- `backend/tests/crawlers/fixtures/texasspeed/expected.json` — Deterministic parse output
- `backend/tests/crawlers/fixtures/cobbtuning/product.html` — Accessport for Porsche 911 991.2 (Magento SPA)
- `backend/tests/crawlers/fixtures/cobbtuning/expected.json` — Deterministic parse output (price_cents: null)
- `backend/tests/crawlers/test_characterization_briantooleyracing.py` — SAFE-07 characterization test
- `backend/tests/crawlers/test_characterization_amsperformance.py` — SAFE-07 characterization test
- `backend/tests/crawlers/test_characterization_texasspeed.py` — SAFE-07 characterization test
- `backend/tests/crawlers/test_characterization_cobbtuning.py` — SAFE-07 characterization test
- `backend/tests/crawlers/test_characterization_subispeed.py` — SAFE-07 characterization test
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` — D-21 bucket reference corrected

## Decisions Made

- Swapped tier2_browser picks (summitracing, ecstuning) per user instruction — those adapters are non-functional. Selected subispeed (tier0_http) as 5th adapter instead.
- Sourced all HTML from localhost MinIO bucket first (confirmed data available); prod fallback was not needed.
- Accepted cobbtuning with null price — this is the correct documented behavior for the Cobb adapter (client-side price hydration). 12 images verify the fixture is a real product page.
- image_urls compared as sets in tests — CDN URL ordering is not part of the adapter contract; field value drift is still caught.

## Deviations from Plan

### Auto-selected adapter swaps (user-directed, pre-resolved at checkpoint)

**1. [User directive] Swapped summitracing + ecstuning for subispeed**
- **Found during:** Task 1 (decision checkpoint resolved before execution)
- **Issue:** tier2_browser adapters currently non-functional; user directed tier0+tier1 only
- **Fix:** Selected subispeed (tier0_http, 22 archived URLs in local bucket) as 5th adapter
- **Impact:** 3×tier0 + 2×tier1 instead of 2×tier0 + 2×tier2 + 1×tier1. All 5 tests pass.

---

**Total deviations:** 1 (user-directed adapter selection change)
**Impact on plan:** Adapters 1-4 unchanged from plan. 5th adapter changed from one tier2_browser to a tier0_http. No scope creep; characterization coverage maintained.

## Issues Encountered

- **OpenAPI snapshot pre-existing failure:** `tests/test_openapi_snapshot.py` fails with a schema tag ordering drift unrelated to this plan's changes. Pre-existing before any 01-07 commits (snapshot files not touched). Logged as out-of-scope per deviation rules. Investigation: the `car_generation` tag appears to have shifted position in the router registration order. To fix: regenerate `backend/tests/fixtures/openapi_snapshot.json` in a dedicated commit.

## Handoff Note for Phase 3

**These 5 tests are the only CI guardrail against silent parse regression during the Phase 3 crawler refactor (CRAWL-01 auto-discovery, CRAWL-05 ThreadPoolExecutor parallelization).**

Phase 3 PRs MUST:
1. Keep all 5 characterization tests green
2. If a parse change is intentional, regenerate the corresponding `expected.json` using the one-liner comment embedded in each test file
3. The `expected.json` diff in the PR IS the review artifact for parse-contract changes
4. After CRAWL-02 lands `ADAPTER_NAME`, switch test imports from class-name to ADAPTER_NAME per D-23

Re-fetch HTML fixtures if needed via: `aws s3 cp s3://carmodpicker-local-crawl/crawl_html/by_url/<hash>.html <path>` (local) or `aws s3 cp s3://carmodpicker-production-crawl-data/crawl_html/by_url/<hash>.html <path>` (prod).

## Next Phase Readiness

- SAFE-07 complete: 5 characterization tests are CI-green, Phase 3 crawler refactor has its regression guardrail
- Pre-existing OpenAPI snapshot drift needs separate fix (not blocking Phase 3)
- Remaining Phase 1 plans: 01-08 (SAFE-08 migration repair), 01-09 (SAFE-03 frontend threshold)

## Self-Check

Verifying claims before proceeding.

**Files exist:**
- `backend/tests/crawlers/fixtures/briantooleyracing/product.html`: FOUND
- `backend/tests/crawlers/fixtures/briantooleyracing/expected.json`: FOUND
- `backend/tests/crawlers/fixtures/amsperformance/product.html`: FOUND
- `backend/tests/crawlers/fixtures/amsperformance/expected.json`: FOUND
- `backend/tests/crawlers/fixtures/texasspeed/product.html`: FOUND
- `backend/tests/crawlers/fixtures/texasspeed/expected.json`: FOUND
- `backend/tests/crawlers/fixtures/cobbtuning/product.html`: FOUND
- `backend/tests/crawlers/fixtures/cobbtuning/expected.json`: FOUND
- `backend/tests/crawlers/fixtures/subispeed/product.html`: FOUND
- `backend/tests/crawlers/fixtures/subispeed/expected.json`: FOUND
- `backend/tests/crawlers/test_characterization_briantooleyracing.py`: FOUND
- `backend/tests/crawlers/test_characterization_amsperformance.py`: FOUND
- `backend/tests/crawlers/test_characterization_texasspeed.py`: FOUND
- `backend/tests/crawlers/test_characterization_cobbtuning.py`: FOUND
- `backend/tests/crawlers/test_characterization_subispeed.py`: FOUND

**Commits exist:**
- `6880532` feat(01-07): FOUND
- `62c844c` test(01-07): FOUND
- `6ac4390` docs(01-07): FOUND

**All 5 tests pass:** Verified (8.30s run, 5 passed, 0 failed)

## Self-Check: PASSED

---
*Phase: 01-safety-nets-ci-hardening*
*Completed: 2026-04-22*
