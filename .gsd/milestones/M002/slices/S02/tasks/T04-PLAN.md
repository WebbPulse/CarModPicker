---
estimated_steps: 37
estimated_files: 8
skills_used: []
---

# T04: Wire apply_universal_extraction into runner / archive_rescrape / crawled_pages call sites + refresh fixture snapshots

Insert the universal-extraction hook between `parse_product_page` and `ingest_payload` at the three call sites. Single-line insertion per file plus a sanity check that the existing flow is unchanged for None-payload returns.

**Call site 1: `backend/app/crawlers/runner.py` (around line 574).**
Current shape:
```python
payload = adapter.parse_product_page(html, url)
if payload is None:
    skipped_not_product += 1
    ...
    continue
# ... archive HTML ...
part = ingest_payload(db, payload, ...)
```
New shape:
```python
payload = adapter.parse_product_page(html, url)
if payload is None:
    skipped_not_product += 1
    ...
    continue
payload = adapter.apply_universal_extraction(html, payload)
# ... archive HTML ...
part = ingest_payload(db, payload, ...)
```
The hook is called *after* the None check (no point extracting against junk pages) and *before* archive + ingest (so the merged specifications land in the same DB write).

**Call site 2: `backend/app/crawlers/archive_rescrape.py` (around line 143).**
Current shape:
```python
payload = adapter.parse_product_page(html, page.url)
if payload is None:
    page.parse_status = 'failed'
    ...
```
Insert `payload = adapter.apply_universal_extraction(html, payload)` after the None check, before the existing `try: ingest_payload(...)`.

**Call site 3: `backend/app/api/endpoints/crawled_pages.py` (around line 267).**
This is the extension `/scrape` endpoint where the Chrome extension uploads HTML. Locate the existing `payload = adapter.parse_product_page(sanitized_html, url)` line; insert the hook on the next line after the None-skip branch. Same shape as the other two sites.

Then refresh the 5 stale characterization-test snapshots if T03's bridge change causes any of them to populate `specifications` with universal fields where today they're `null`. Files to check: `backend/tests/crawlers/fixtures/{amsperformance,briantooleyracing,cobbtuning,subispeed,texasspeed}/expected.json`. Run `pytest backend/tests/crawlers/test_characterization_*.py -n auto --rootdir=backend` to surface any drift; refresh the JSON if needed by setting the actual extracted dict (or keep `null` if extraction returns nothing). Do NOT introduce new fixtures; just refresh existing ones if the merged universal-field output requires it.

No new files. Three call-site edits + up to five fixture-snapshot refreshes.

## Inputs

- ``backend/app/crawlers/adapters/base.py` — uses apply_universal_extraction from T03`
- ``backend/app/crawlers/runner.py` — call site 1 (line 574 area)`
- ``backend/app/crawlers/archive_rescrape.py` — call site 2 (line 143 area)`
- ``backend/app/api/endpoints/crawled_pages.py` — call site 3 (line 267 area)`
- ``backend/tests/crawlers/fixtures/amsperformance/expected.json` — characterization snapshot, may need refresh`
- ``backend/tests/crawlers/fixtures/briantooleyracing/expected.json` — characterization snapshot, may need refresh`
- ``backend/tests/crawlers/fixtures/cobbtuning/expected.json` — characterization snapshot, may need refresh`
- ``backend/tests/crawlers/fixtures/subispeed/expected.json` — characterization snapshot, may need refresh`
- ``backend/tests/crawlers/fixtures/texasspeed/expected.json` — characterization snapshot, may need refresh`

## Expected Output

- ``backend/app/crawlers/runner.py` — apply_universal_extraction inserted between parse + ingest`
- ``backend/app/crawlers/archive_rescrape.py` — apply_universal_extraction inserted between parse + ingest`
- ``backend/app/api/endpoints/crawled_pages.py` — apply_universal_extraction inserted between parse + ingest`
- ``backend/tests/crawlers/fixtures/amsperformance/expected.json` — refreshed if extraction populates specifications`
- ``backend/tests/crawlers/fixtures/briantooleyracing/expected.json` — refreshed if extraction populates specifications`
- ``backend/tests/crawlers/fixtures/cobbtuning/expected.json` — refreshed if extraction populates specifications`
- ``backend/tests/crawlers/fixtures/subispeed/expected.json` — refreshed if extraction populates specifications`
- ``backend/tests/crawlers/fixtures/texasspeed/expected.json` — refreshed if extraction populates specifications`

## Verification

pytest backend/tests/crawlers/ -n auto --rootdir=backend

## Observability Impact

No new signals — wiring change only. The DEBUG log lines from T03 now fire on every real crawl + every archive rescrape + every extension upload.
