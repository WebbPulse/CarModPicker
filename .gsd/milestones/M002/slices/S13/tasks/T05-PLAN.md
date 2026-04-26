---
estimated_steps: 6
estimated_files: 3
skills_used: []
---

# T05: Kick off backfill (started, not complete) and capture cursor + progress evidence

R005 says 'Started by milestone end; can finish post-merge' — T05's bar is `started`, not `complete`. Run the backfill against the live local DB to confirm the CLI is wired correctly and produces the expected runtime signals.

From `backend/`: first a dry-run to confirm shape with no behavior change — `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --dry-run --limit 50`. Confirm CLI exits 0, logs `backfill: batch=...` lines, and writes nothing (no cursor file, no Part.specifications mutations).

Then a real run as the `started` evidence: `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --limit 100 2>&1 | tee /tmp/backfill-run.log`. Expected: per-batch INFO log `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns`, final summary log line, exit 0, `backend/.crawler-state/backfill_cursor.json` lands.

Copy the log + cursor to evidence: `cp /tmp/backfill-run.log .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log` and `cp backend/.crawler-state/backfill_cursor.json .gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json`. The cursor file remains in `backend/.crawler-state/` (gitignored per S04) for an operator to resume — DO NOT delete it.

Then re-hit `GET /api/admin/extraction-health` and confirm whatever delta the run produced shows up in `coverage.per_tier.<tier>.parts_with_specs` (it should increase if any of the 100 sampled parts had archived HTML and successfully re-extracted). Capture a fresh JSON dump to `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json` for diff.

AUTONOMOUS-MODE NOTE: T05 also reuses T01's live stack. If Docker isn't up, T05 cannot proceed. The dry-run portion in particular requires the live DB to query the empty-specs filter against real Part rows.

## Inputs

- ``backend/app/crawlers/backfill.py` — CLI module (S04)`
- ``backend/app/api/endpoints/admin/extraction_health.py` — for post-backfill coverage check`
- ``backend/.crawler-state/` — runtime cache directory (gitignored)`

## Expected Output

- ``.gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log` — committed backfill stdout/stderr with per-batch log lines`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json` — committed snapshot of backend/.crawler-state/backfill_cursor.json`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json` — post-run admin endpoint JSON for coverage delta evidence`

## Verification

test -f .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log && grep -q 'backfill: batch=' .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log && test -f .gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json && test -f .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json

## Observability Impact

backfill-run.log captures the runtime signal contract S04 established (`backfill: batch=N ... processed=N updated=N`). The cursor snapshot is operator-inspectable resume position; the live cursor in backend/.crawler-state/ continues to advance if/when an operator runs the long-tail backfill post-merge. Above-threshold-failure-rate exit code 2 was already covered by S04 unit tests; T05 just confirms the happy path runs.
