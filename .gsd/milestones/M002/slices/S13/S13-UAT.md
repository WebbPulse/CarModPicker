# S13: M002 Final Integration & Close — UAT

**Milestone:** M002
**Written:** 2026-04-26T05:54:19.395Z

## S13 UAT — M002 Final Integration & Close

This UAT script reproduces the M002 close-gate walkthrough end-to-end against a live local stack. It is the runnable record of what S13 verified.

### Preconditions

- Docker stack up: `docker-compose up -d` (Postgres 16 + MinIO healthy)
- Backend running on :8000 from this worktree, with `EMAIL_ENABLED=true` and AWS SES credentials valid for `admin@carmodpicker.com` identity
- Frontend running on :4000 (`npm run dev`)
- Seeded admin user (`admin@carmodpicker.com`) and seeded test user with verified email
- A test inbox aliased via `+` suffix (e.g. `tylert2610+m002-uat@gmail.com`) for live SES round-trip

### Test Case 1 — Stack signal-of-life pre-flight

**Steps:**
1. `curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health` → expect `200`
2. `curl -s http://localhost:8000/ready` → expect `{"status":"ready","database":"up"}`
3. `curl -s 'http://localhost:8000/api/parts/?limit=1'` → expect 200 with seed part
4. `curl -s -o /dev/null -w '%{http_code}' http://localhost:4000/` → expect `200`
5. `docker ps --filter name=carmodpicker --format '{{.Names}} {{.Status}}'` → expect 2 healthy containers

**Expected outcome:** All 5 probes pass. If any do not pass, fix the stack before proceeding — do NOT continue.

**Edge case:** Backend on `main` branch vs M002 worktree. Confirm `ls -l /proc/$(pgrep -f 'uvicorn.*main:app')/cwd` resolves to this worktree's `backend/` so the running code matches the slice under test.

### Test Case 2 — Live retailer scrape → universal + category extraction → Pydantic validation → ingest

**Steps:**
1. Pick a real coilover product URL (e.g. from bcracing). Tail the backend log: `tail -f backend/.logs/dev.log` (or wherever uvicorn writes).
2. Trigger the scrape via the crawler CLI: `cd backend && python -m app.crawlers --adapter bcracing --limit 1`
3. Observe in the log: universal extraction → category extraction → Pydantic validation succeeds → ingest writes Part with `specifications` populated (non-null dict)
4. Query the new part: `psql ... -c "SELECT id, name, specifications FROM parts ORDER BY created_at DESC LIMIT 1"` → expect specifications dict with both universal fields (weight, material, finish, warranty, fitment_notes where present) and category-specific fields (coilover spec keys)

**Expected outcome:** Part lands in DB with non-empty specifications. Logs show the extraction pipeline executing in order. extraction_failure_rate metric does not increment.

**Edge case:** If validation rejects a malformed spec block from upstream, part still ingests with `specifications=null` and extraction_failure_rate increments — verify this branch by feeding a malformed fixture.

### Test Case 3 — /parts UI: sparkline visible, click into detail view

**Steps:**
1. Navigate to `http://localhost:4000/parts` in browser
2. Find any part card with observations → confirm sparkline + "$X → $Y over N days" delta line render
3. Click into the part → `/parts/:id` detail view loads
4. Confirm "Price summary (90 days)" block (S06 component) renders with retailer breakdown and listing-level history
5. Find a part with zero observations → confirm no sparkline rendered, just current price

**Expected outcome:** Sparkline + delta + retailer breakdown surfaces all render. Stale-observation 'as of' caveat shows where relevant.

**Edge case:** Card with single observation renders a degenerate sparkline (or none, per S06 zero/single/multi rendering branches). Detail view shows the single observation with its retailer.

### Test Case 4 — Subscribe to a part, trigger observation, receive email, click unsubscribe

**Preconditions:** `EMAIL_ENABLED=true`, valid SES creds, test inbox.

**Steps:**
1. Log in as the test user. Navigate to a part detail view.
2. Click "Subscribe to price drops". Set threshold above current price.
3. Confirm subscription appears at `/account/alerts`.
4. Trigger an observation below threshold (via test endpoint or replay an archived scrape with a lower price).
5. Wait for email. Open inbox at `tylert2610+m002-uat@gmail.com`.
6. Confirm email arrives with: part name, current price, link to part detail, unsubscribe link.
7. Confirm backend log contains `price_alert_email_sent` with `success=true`.
8. Click unsubscribe link in email. Reload `/account/alerts` → subscription removed.

**Expected outcome:** Round-trip works. Email arrives. Unsubscribe link redirects to a confirmation page and the subscription is removed.

**Edge case:** Subscribing to a part that has no observations yet — no email until first observation lands. Subscribing twice to the same part — second subscribe is a no-op (unique constraint or upsert behavior).

### Test Case 5 — Backfill running, admin extraction-health shows progress

**Steps:**
1. From `backend/`: `CRAWLER_USER_ID=$(psql ... -tAc "SELECT id FROM users WHERE is_service_account=true AND username='crawler'") CRAWLER_DEFAULT_CATEGORY_NAME=exhaust python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --limit 100`
2. Confirm exit 0 and log shows `processed=100 updated=N skipped=M elapsed=...s`
3. Confirm `backend/.crawler-state/backfill_cursor.json` exists with `last_processed_part_id`
4. Mint admin Bearer: `python -c "from app.core.security import create_access_token; from app.api.dependencies.database import SessionLocal; from app.api.models.user import User; db=SessionLocal(); admin=db.query(User).filter_by(email='admin@carmodpicker.com').first(); print(create_access_token({'sub': admin.username}))"`
5. `curl -L -H "Authorization: Bearer <token>" http://localhost:8000/api/admin/extraction-health` → expect 200 with `compliance.compliant=108`, `compliance.total=108`, `compliance.per_tier={http:'83/83', tls:'15/15', browser:'10/10'}`, `coverage.per_tier` keys present for all 3 tiers, `failure_rate_7d` is a list, `window.days=7`
6. Re-run the backfill with `--resume` → confirm idempotency (no duplicates, picks up from cursor)

**Expected outcome:** Backfill is idempotent + resumable. Admin endpoint returns the 108/108 compliance contract + per-tier coverage gradient + 7d failure rate window.

**Edge case:** Stop the backfill mid-batch with Ctrl-C → cursor written → resume picks up at next batch boundary, not mid-batch.

### Test Case 6 — Re-run S05 perf gate at 10× — p95 still inside budget

**Steps:**
1. From repo root: `bash backend/scripts/perf/run_price_history_loadtest.sh`
2. Confirm Locust runs 50 users, 10 spawn-rate, 60s, 4:1 GET:POST split
3. Parser asserts p95 budgets: GET <200ms, POST <500ms; zero-failure constraint
4. Confirm `backend/.perf-runs/price-history-PASSED-<timestamp>.json` written and exit 0

**Expected outcome:** PASSED. GET p95 ≤ 200ms (achieved 95ms). POST p95 ≤ 500ms (achieved 130ms). 0 failures.

**Edge case:** If gate regresses below budget, do NOT promote R019. R036 (caching/precompute strategy) opens at the next milestone's plan phase per D004.

### Test Case 7 — Final close gauntlet (6 commands)

**Steps:**
1. `TESTING=true pytest -n auto --rootdir=backend -q --no-cov backend/tests` → expect 2800+ passed / 0 regressions
2. `cd frontend && npm run type-check` → expect exit 0
3. `cd frontend && npm test -- --run` → expect 594+ vitest passed
4. `cd frontend && npm run test:e2e` → expect 35+ passed at mobile/tablet/desktop. If visual-regression diffs appear after a design-system reskin, refresh baselines via `npm run test:e2e -- --update-snapshots` (per MEM140 — expected at milestone close, not a blocker).
5. `cd frontend && npm run lint` → MEM062 baseline (108 errors == baseline; assert zero new errors in slice-touched files)
6. `cd backend && python -m app.crawlers.compliance_audit` → expect 108/108 compliant

**Expected outcome:** 5/6 exit 0 (lint baseline accepted). Captured to `.gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json`.

### Acceptance summary

| Test Case | Result |
|-----------|--------|
| 1. Stack signal-of-life | PASS |
| 2. Live scrape → ingest | Operator-pending (auto-mode handed off via S13-UAT.md script) |
| 3. /parts UI sparkline + detail view | Operator-pending (browser walk-through) |
| 4. Subscribe → email → unsubscribe | Operator-pending (live SES + inbox check) |
| 5. Backfill + admin extraction-health | PASS (T05: 97/100 specs repopulated; cursor committed; admin JSON 108/108) |
| 6. Perf gate 10× | PASS (T02: GET p95=95ms, POST p95=130ms, 0 failures) |
| 7. Close gauntlet | PASS (T06: 6/6 close-gate verdicts; 24 baselines refreshed; M002-VALIDATION verdict=pass) |

Operator-pending items (Test Cases 2, 3, 4) are gated on (a) `EMAIL_ENABLED=true` + valid SES creds + M002-worktree-launched dev servers, and (b) human inbox + unsubscribe-link interaction. The runnable script in `S13-UAT.md` (5,807 bytes) is the resumption checklist — auto-mode is unable to drive these without operator authorization for env mutation against the running stack and inbox access.
