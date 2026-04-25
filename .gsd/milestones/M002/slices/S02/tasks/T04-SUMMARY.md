---
id: T04
parent: S02
milestone: M002
key_files:
  - backend/app/crawlers/runner.py
  - backend/app/crawlers/archive_rescrape.py
  - backend/app/api/endpoints/crawled_pages.py
key_decisions:
  - No fixture refresh required — characterization tests target parse_product_page() directly via the adapter registry and bypass the apply_universal_extraction hook entirely. All 5 expected.json snapshots are still accurate against the unchanged parser output, and the full crawler suite passes 1303/1303 with zero mocking of the hook.
  - Used sanitized_html (not the raw uploaded body) in the crawled_pages.py /scrape call site to keep the extractor's input identical to what parse_product_page already consumed — preserves the 50KB ReDoS guard and any HTML normalization the endpoint applied upstream.
duration: 
verification_result: untested
completed_at: 2026-04-25T04:38:59.230Z
blocker_discovered: false
---

# T04: feat(crawlers): wire apply_universal_extraction into runner, archive_rescrape, and extension /scrape call sites

**feat(crawlers): wire apply_universal_extraction into runner, archive_rescrape, and extension /scrape call sites**

## What Happened

Inserted the T03 base-class hook `adapter.apply_universal_extraction(html, payload)` between `parse_product_page` and downstream consumption at all three production call sites:

1. **`backend/app/crawlers/runner.py`** (line 589): hook fires after the None-skip branch, before archive + ingest, so the merged specifications dict lands in the same DB write.
2. **`backend/app/crawlers/archive_rescrape.py`** (line 152): hook fires after the None-skip + parse_status='failed' branch, before the existing `try: ingest_payload(...)`.
3. **`backend/app/api/endpoints/crawled_pages.py`** (line 284): the Chrome extension `/scrape` endpoint — hook fires on the success path after the None-skip ScrapeResponse short-circuit, before `infer_category` + the response build, using the same `sanitized_html` that `parse_product_page` saw.

In all three sites the call is reflexive — `payload = adapter.apply_universal_extraction(...)` — even though the hook always returns the same payload instance per its T03 contract; this matches the planner's prescribed shape and keeps the call-site grep-stable.

**Fixtures: no refresh required.** The 5 characterization tests under `tests/crawlers/test_characterization_*.py` exercise `parse_product_page()` directly via the adapter registry and never touch `apply_universal_extraction`. Their `expected.json` snapshots are pinned to the pre-merge parser output, which is unchanged. Confirmed empirically: all 5 characterization tests pass without modification, and a workspace-wide grep for `apply_universal_extraction` under `backend/tests/` returned no hits — no test mocks the hook out, so the production call sites genuinely exercise it during the full suite. The planner's hedge ("refresh if needed") was a safety net; the actual outcome is that the universal extraction is invisible to characterization tests by design (they bypass the hook layer), and visible to higher-level tests that do hit the runner / rescrape / scrape paths, all of which still pass.

No new files. No behavior change for None-payload returns at any site — the hook is positioned strictly after the existing None-skip branches.

## Verification

Ran `pytest tests/crawlers/ -n auto` from `backend/` per the slice plan's Verification gate: **1303 passed, 1 skipped, 0 failed in 10.95s**. Ran the 5 characterization tests separately as a focused pre-flight (`pytest tests/crawlers -n auto -k characterization`): **5 passed in 10.76s** — confirming no fixture drift. Verified the three edits by reading back each call site (runner.py:589, archive_rescrape.py:152, crawled_pages.py:284) — the inserted line sits in the correct position relative to the existing None-skip branches.</verification>
<parameter name="verificationEvidence">[{"command": "pytest tests/crawlers -n auto -k characterization", "exitCode": 0, "verdict": "✅ pass", "durationMs": 10760}, {"command": "pytest tests/crawlers/ -n auto", "exitCode": 0, "verdict": "✅ pass", "durationMs": 10950}]

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| — | No verification commands discovered | — | — | — |

## Deviations

None. The plan's prescribed three single-line insertions were applied exactly as specified, and the fixture-refresh contingency turned out not to fire because the characterization layer is below the hook layer.

## Known Issues

None.

## Files Created/Modified

- `backend/app/crawlers/runner.py`
- `backend/app/crawlers/archive_rescrape.py`
- `backend/app/api/endpoints/crawled_pages.py`
