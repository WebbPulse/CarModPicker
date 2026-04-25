# S04: Re-extraction backfill + admin extraction-health API — UAT

**Milestone:** M002
**Written:** 2026-04-25T05:42:40.686Z

## UAT Script — S04 Re-extraction backfill + admin extraction-health API

### Preconditions

- Backend dev server running (`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`) against local Postgres (docker-compose up -d).
- Local DB populated via `python ../scripts/populate_sample_data.py` (or the existing ~25k real scraped parts dataset).
- Admin user credentials available (use `create_and_login_admin_user` test helper or an existing admin account).
- `CRAWLER_USER_ID` and `CRAWLER_DEFAULT_CATEGORY_NAME` env vars exported (CLI relies on operator's environment per MEM008 — does not set `TESTING=true` itself, so EMF metric fires).
- `chrome-extension/API_CONTRACT.md` parity not affected (admin surface only).

### Test Cases

**TC-1 — Backfill CLI dry-run prints summary, performs no writes**

1. From `backend/`, run `python -m app.crawlers.backfill --dry-run --limit 0`.
2. **Expected:** Exit code 0; stdout includes a summary line `backfill: batch=N ... processed=N updated=N skipped=N elapsed=...s` and final summary; **no `Part.specifications` rows mutated**, **no `crawled_pages.last_parsed_at` updated**, **no `.crawler-state/backfill_cursor.json` written**.
3. **Verification query:** `SELECT count(*) FROM parts WHERE specifications IS NOT NULL AND specifications != 'null' AND specifications != '{}'` — count is unchanged from before the dry-run.

**TC-2 — Backfill CLI populates empty specifications and is idempotent**

1. From `backend/`, run `python -m app.crawlers.backfill --batch-size 100 --limit 200`. Expected: log lines per batch, exit code 0, summary reports `processed=N, updated=M`.
2. Re-run the **same command immediately**.
3. **Expected:** Second run reports `processed=0, updated=0` — the `_empty_specs_filter` no longer matches parts that were populated on run 1 (exercises MEM041 three-shape match: SQL NULL, JSON `'null'`, JSON `'{}'`).
4. **Verification query:** `SELECT count(*) FROM parts WHERE specifications IS NULL OR specifications::text = 'null' OR specifications::text = '{}'` — count strictly decreases between run 1 start and run 2 start, then is stable across run 2.

**TC-3 — Backfill CLI is resumable across Ctrl-C**

1. Start `python -m app.crawlers.backfill --batch-size 50 --limit 500`.
2. After the first batch's "backfill: batch=1 ..." log line appears, send Ctrl-C (SIGINT).
3. **Expected:** Process exits with code 1 (KeyboardInterrupt logged), `.crawler-state/backfill_cursor.json` exists with `{"last_processed_part_id": "<uuid>", "updated_at": "<iso8601>"}`.
4. Re-run **with `--resume`**: `python -m app.crawlers.backfill --batch-size 50 --limit 500 --resume`.
5. **Expected:** First batch's `start_id` is the cursor's `last_processed_part_id`; only parts with `id > <cursor>` are processed; CLI does not re-touch parts handled before the Ctrl-C.

**TC-4 — Backfill CLI rejects malformed CLI args**

1. `python -m app.crawlers.backfill --batch-size 0` → exit code 2, argparse error.
2. `python -m app.crawlers.backfill --batch-size -1` → exit code 2, argparse error.
3. `python -m app.crawlers.backfill --max-failure-rate 1.5` → exit code 2, argparse error (must be in `[0.0, 1.0]`).

**TC-5 — Backfill CLI exits 2 above failure-rate threshold**

1. Seed local DB with parts whose `crawled_pages` has corrupted/missing S3 archive (or temporarily disable S3 access).
2. Run `python -m app.crawlers.backfill --batch-size 10 --limit 20 --max-failure-rate 0.5`.
3. **Expected:** All parts fail rescrape (counted as `ingest_failed`); CLI exits with code 2; final summary log line includes `failed=N total=N rate=1.0` (or similar).

**TC-6 — Backfill CLI `--source` filter restricts to one adapter**

1. From `backend/`, run `python -m app.crawlers.backfill --source a90shop --batch-size 50 --limit 100` (substitute any registered adapter slug from `ADAPTER_REGISTRY`).
2. **Expected:** Only parts whose linked `crawled_pages.source = 'a90shop'` are processed. Parts from other adapters are untouched. Verify with `SELECT count(*) FROM crawled_pages WHERE source = 'a90shop' AND last_parsed_at >= now() - interval '5 minutes'` — count matches the CLI's `processed` value.

**TC-7 — Admin extraction-health endpoint returns compliance block**

1. POST `/api/auth/login` with admin credentials, capture JWT.
2. GET `/api/admin/extraction-health` with `Authorization: Bearer <token>`.
3. **Expected:** 200 OK with JSON body matching:
   ```json
   {
     "compliance": {
       "compliant": 108,
       "total": 108,
       "per_tier": {"http": "83/83", "tls": "15/15", "browser": "10/10"}
     },
     "coverage": {"per_tier": {"http": {...}, "tls": {...}, "browser": {...}}},
     "failure_rate_7d": [...],
     "window": {"days": 7, "since": "<ISO8601>"}
   }
   ```
4. **Assertions:** `compliance.compliant == compliance.total`; each `per_tier` string is `"<n>/<n>"`-shaped; `window.days == 7`; `window.since` parseable via `datetime.fromisoformat()`.

**TC-8 — Admin endpoint coverage counts populated specifications**

1. After running TC-2, GET `/api/admin/extraction-health`.
2. **Expected:** For at least one tier where backfill touched parts, `coverage.per_tier.<tier>.parts_with_specs >= 1` and at least one `per_field.<field>` ratio is `> 0.0` (e.g. `weight_grams: 0.42` if 42% of T0 parts have a `weight_grams` value).
3. **Assertion:** `per_field` includes all 5 universal fields: `weight_grams`, `material`, `finish`, `warranty_days`, `fitment_notes` (matches `UNIVERSAL_FIELD_NAMES` frozenset).

**TC-9 — Admin endpoint failure-rate windows correctly**

1. Insert a `crawled_pages` row with `parse_status='failed'`, `last_parsed_at=now()`, `source='a90shop'`. Insert another with `parse_status='parsed'`, `last_parsed_at=now()`, `source='a90shop'`.
2. Insert a third with `parse_status='failed'`, `last_parsed_at=now() - interval '30 days'`, `source='a90shop'` (outside window).
3. GET `/api/admin/extraction-health`.
4. **Expected:** `failure_rate_7d` includes an entry `{"adapter": "a90shop", "failed": 1, "parsed": 1, "rate": 0.5, "tier": "http"}`. The 30-day-old failure does NOT inflate the count.

**TC-10 — Admin endpoint skips unknown sources defensively**

1. Insert a `crawled_pages` row with `source='retired_adapter_xyz'` (a slug not in `ADAPTER_REGISTRY`).
2. GET `/api/admin/extraction-health`.
3. **Expected:** No entry for `retired_adapter_xyz` in `failure_rate_7d` — the response omits unknown sources rather than crashing or surfacing a phantom adapter.

**TC-11 — Admin endpoint auth gating**

1. GET `/api/admin/extraction-health` with **no Authorization header** → **401 Unauthorized**.
2. GET `/api/admin/extraction-health` with a **regular (non-admin) user's JWT** → **403 Forbidden**.
3. GET with an admin JWT → **200 OK** with the body shape from TC-7.

### Edge Cases

- **Empty `crawled_pages` table:** `failure_rate_7d=[]`, `coverage` all-zero, `compliance` still 108/108. Endpoint does not 500.
- **All `last_parsed_at IS NULL`:** `failure_rate_7d=[]`. No false positives.
- **`--limit` smaller than `--batch-size`:** CLI processes up to `--limit` parts and exits 0 — does not over-fetch.
- **Empty result set on first run:** CLI exits 0 immediately with summary log line `processed=0`.
- **`--resume` with no cursor file:** CLI silently starts from the beginning (no error).
- **Cursor file write fails (e.g. read-only state-dir):** CLI logs WARN, continues — resume becomes manual the next run.

### Operator Notes

- The CLI is opt-in / operator-driven. It is NOT scheduled; running it against production requires explicit operator action with `CRAWLER_USER_ID` and `CRAWLER_DEFAULT_CATEGORY_NAME` env vars set.
- `WINDOW_DAYS = 7` is a hard-coded constant in `extraction_health.py`. If an admin UI needs configurable windows, add a query param in S11 — endpoint currently exposes `window.days` so the consumer can render the actual window without assuming.
- The 7d failure-rate signal is authoritative DB state (`crawled_pages.parse_status`). The CloudWatch EMF `ExtractionFailureRate` metric continues to fire from `ingest_payload` for monitoring/alarms but is intentionally NOT consumed by this endpoint (D009).
