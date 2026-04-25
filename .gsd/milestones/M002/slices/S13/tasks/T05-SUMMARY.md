---
id: T05
parent: S13
milestone: M002
key_files:
  - .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log
  - .gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json
  - .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json
  - backend/.crawler-state/backfill_cursor.json
key_decisions:
  - Minted the admin Bearer token via create_access_token({'sub': admin.username}) (NOT admin.id) — get_current_user looks up by username, so a UUID in sub 401s. Captured as MEM138 so the next auto-mode session doesn't repeat the 30-second investigation. T04's working pattern already used username; this just reproduced and documented it.
  - Did NOT delete backend/.crawler-state/backfill_cursor.json after copying to evidence — the task plan explicitly says 'DO NOT delete it' so an operator can post-merge --resume from where the 100-part run stopped (last_processed_part_id=019daecf-5841-7b5f-80d1-4308c375acbd). The cursor stays gitignored in backend/, the snapshot in evidence/ is the auditable copy.
  - Used CRAWLER_DEFAULT_CATEGORY_NAME=exhaust per the task plan's verbatim invocation even though the candidate query does NOT filter by category (the join is parts→crawled_pages on part_id with empty-specs predicate, no category constraint). The env var is consumed by resolve_default_category_id() at bootstrap as a fallback for parts that need category assignment during ingest — it doesn't narrow the SELECT. Followed the plan's invocation rather than dropping the var; it's load-bearing for the rescrape→ingest path, not for candidate selection.
duration: 
verification_result: passed
completed_at: 2026-04-26T05:29:59.353Z
blocker_discovered: false
---

# T05: Kicked off the S04 backfill against the live local stack — dry-run + 100-part real run both passed (97/100 specs repopulated, 0 failures), cursor + log + post-run admin extraction-health JSON committed as `started` evidence for R005.

**Kicked off the S04 backfill against the live local stack — dry-run + 100-part real run both passed (97/100 specs repopulated, 0 failures), cursor + log + post-run admin extraction-health JSON committed as `started` evidence for R005.**

## What Happened

Re-extraction backfill is the final piece of M002/S13: R005 only requires it be `started` by milestone close, with the long tail draining post-merge.

**Pre-flight.** Confirmed Docker DB + MinIO healthy (8h uptime), backend liveness=200 ready=200, the running uvicorn (PID 936488) is rooted in this M002 worktree's `backend/`. Resolved the crawler service account UUID directly from the live DB (`019d94ae-e5c3-7804-b8e1-7b7f91bd284c`, username=crawler, is_service_account=true) and confirmed an `exhaust` category exists. Counted 28,085 candidate parts (NULL/json-null/empty-dict specifications) — plenty of long-tail work for a future operator drain. The S04 backfill CLI's `_empty_specs_filter` already handles all three on-disk shapes per MEM044/MEM041.

**Dry-run.** From `backend/`: `CRAWLER_USER_ID=… CRAWLER_DEFAULT_CATEGORY_NAME=exhaust python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --dry-run --limit 50`. Exit 0. Logged `backfill[dry-run]: batch=1 start_id=019daecf-0bae-… processed=50 updated=0 skipped=0 elapsed=0.00s` plus the `done … (dry-run)` summary. No `.crawler-state/` directory created (read-only path verified).

**Real run.** Same env, `--limit 100` (no --dry-run), tee'd to `/tmp/backfill-run.log`. Exit 0. One batch logged `backfill: batch=1 start_id=019daecf-0bae-765f-827e-1b5751ceacd1 processed=100 updated=97 skipped=0 elapsed=18.18s`, then the summary line `backfill: done batches=1 processed=100 updated=97 skipped=0 parse_failed=0 ingest_failed=0 failure_rate=0.000 elapsed=18.19s`. 97 of 100 sampled parts had archived HTML and successfully re-extracted via `rescrape_crawled_page_from_archive` → universal extraction → ingest_payload → Part.specifications. Cursor file landed at `backend/.crawler-state/backfill_cursor.json` with `last_processed_part_id=019daecf-5841-7b5f-80d1-4308c375acbd`. Cursor file remains in `backend/.crawler-state/` (gitignored per S04) so a post-merge operator can `--resume`.

**Post-run admin endpoint check.** Minted an admin Bearer token directly via `create_access_token({'sub': admin.username})` against the seeded admin (matching T04's auto-mode pattern that bypasses TOTP). Hit `GET /api/admin/extraction-health/` (HTTP 200, 4891 bytes). Coverage delta confirms the run took effect: `coverage.per_tier.http.parts_with_specs`: 0 → 97 (TLS and browser tiers stayed at 0 since the 100 sampled exhaust parts were all HTTP-tier). `compliance.compliant: 108` unchanged. `failure_rate_7d` shows healthy adapter rates (max 2.7% for vividracing, well within budget).

**Evidence committed.** `backfill-run.log` (per-batch + done log lines), `backfill-cursor-snapshot.json` (resume position), `admin-extraction-health-post-backfill.json` (4891-byte coverage proof). Verification gate (`test -f … && grep -q 'backfill: batch=' … && test -f … && test -f …`) passes.

**One auth gotcha worth documenting.** First admin-endpoint attempt 401'd because I minted the token with `sub=str(admin.id)` — but `get_current_user` does `select(DBUser).where(DBUser.username == sub)`, so the UUID returned no user. Re-minted with `sub=admin.username` and got 200. Captured as MEM138 so future auto-mode token-minting in this codebase doesn't repeat the investigation. T04 had used the username already; this was reproducing the pattern, not inventing it.

## Verification

Slice-level verification gate executed and passed: `test -f .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log && grep -q 'backfill: batch=' .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log && test -f .gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json && test -f .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json` → exit 0. Dry-run exited 0 with `backfill[dry-run]: batch=…` lines and zero writes (no .crawler-state/ created). Real run exited 0 with `backfill: batch=1 … processed=100 updated=97 skipped=0` per-batch + `failure_rate=0.000` final summary. Post-run admin endpoint returned HTTP 200 with `coverage.per_tier.http.parts_with_specs: 97` (was 0 in T04's pre-backfill snapshot). Cursor file landed at `backend/.crawler-state/backfill_cursor.json` with `last_processed_part_id=019daecf-5841-7b5f-80d1-4308c375acbd`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --dry-run --limit 50` | 0 | ✅ pass | 1500ms |
| 2 | `python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --limit 100 (real run)` | 0 | ✅ pass | 18190ms |
| 3 | `curl -H 'Authorization: Bearer <admin>' http://localhost:8000/api/admin/extraction-health/` | 0 | ✅ pass (HTTP 200, coverage delta http: 0→97) | 400ms |
| 4 | `test -f backfill-run.log && grep -q 'backfill: batch=' backfill-run.log && test -f backfill-cursor-snapshot.json && test -f admin-extraction-health-post-backfill.json` | 0 | ✅ pass | 5ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log`
- `.gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json`
- `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json`
- `backend/.crawler-state/backfill_cursor.json`
