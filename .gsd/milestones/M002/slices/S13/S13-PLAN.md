# S13: Final integration + milestone verification

**Goal:** Close M002 by proving the full system end-to-end against a live stack: live scrape → universal-extraction → category-extraction → Pydantic validation → ingest → Part.specifications → /parts sparkline → /parts/:id retailer breakdown → price-drop alert email → unsubscribe; re-run the S05 perf gate at 10× to validate R019; remove the S05 legacy=true price-history shim; run the full backend+frontend+e2e+lint+type-check gauntlet; author M002-VALIDATION.md + M002-SUMMARY.md and promote R002/R003/R005/R006/R008/R009/R010/R016/R017/R018/R019/R020 from active to validated.
**Demo:** Pick a real coilover product URL. Run a live scrape. Observe in logs: universal extraction → category extraction → Pydantic validation → ingest → Part.specifications populated. Visit /parts and find the part — sparkline renders. Click into detail view — retailer breakdowns visible. Subscribe with threshold above current price; trigger observation; email arrives. Confirm backfill job running (admin extraction-health shows progress). Re-run S05 load test — p95 still inside budget.

## Must-Haves

- All 12 active M002 requirements (R002, R003, R005, R006, R008, R009, R010, R016, R017, R018, R019, R020) promoted to status=validated with the evidence path captured. Live UAT evidence dump under .gsd/milestones/M002/slices/S13/uat-evidence/ contains: log excerpts (universal extraction → category extraction → ingest), screenshots (/parts sparkline, /parts/:id retailer breakdown, /account/alerts row + email render), perf-gate PASSED.json, compliance-audit stdout, backfill log + cursor JSON, /admin/extraction-health JSON dump. Legacy `legacy=true` query-param branch + `_legacy_get_part_price_history` helper removed from backend/app/api/endpoints/parts.py; `getPartPriceHistory(partId)` call removed from frontend/src/pages/builder/ViewPart.tsx; PriceHistoryLineChart.tsx deleted. OpenAPI snapshot regenerated. M002-VALIDATION.md verdict=passed; M002-SUMMARY.md written. Final gauntlet green: `pytest backend/tests -n auto`, `cd frontend && npm run type-check && npm test -- --run && npm run test:e2e && npm run lint` (lint at 108-error baseline per MEM062 — no NEW errors in S13-touched files), `cd backend && python -m app.crawlers.compliance_audit` exit 0 reporting 108/108.

## Proof Level

- This slice proves: - This slice proves: final-assembly
- Real runtime required: yes
- Human/UAT required: yes (operator confirms Docker+uvicorn+frontend dev up; reads SES email; clicks unsubscribe link)

## Integration Closure

- Upstream surfaces consumed: ALL prior slices. S01 (SpecRegistry, ingest validation), S02 (universal extraction), S03 (compliance_audit script + 108-adapter contract), S04 (backfill CLI + admin extraction-health endpoint), S05 (price-history aggregation API + perf gate runner), S06 (sparkline + delta + per-retailer breakdown UI), S07 (alert subscribe + evaluator + SES email + unsubscribe), S08-S12 (full design-system reset with components/ui/* + Playwright e2e at 3 viewports). External: docker-compose Postgres 16, AWS SES IAM role, optional live retailer fetch (or archive_rescrape fallback).
- New wiring introduced in this slice: nothing structural. The only code change is removing the S05 legacy=true shim (T03) — pure deletion + OpenAPI regeneration. T01–T02–T04–T05 are operator-driven verification of already-wired surfaces. T06 writes milestone-close artifacts via `gsd_validate_milestone` and `gsd_complete_milestone`.
- What remains before the milestone is truly usable end-to-end: nothing. After S13 closes, M002 is shipped. Carry-forward (NOT blockers): AccountAlerts MEM097 self-cancel useEffect bug (deferred — hidden by vitest sync mocks; surfaces only in production-latency UI), lint baseline 108 errors (pre-existing per MEM062, not regression), backfill *complete* run (R005 says "started, not complete" — long-running completion is post-merge).

## Verification

- Runtime signals: existing structured logs from S01-S07 surface in T01's UAT walkthrough — `universal_extraction_extracted: ...`, `category_extraction_validated: part_id=...`, `ingest_payload: parse_status=...`, `price_alert_evaluated: alert_id=... verdict=fired`, `price_alert_email_sent: alert_id=... success=true`. T02 produces `backend/.perf-runs/price-history-PASSED-<iso8601>.json` (or FAILED.json with R036 remediation string). T05 produces per-batch `backfill: batch=N start_id=<uuid> processed=N updated=N` log lines + `.crawler-state/backfill_cursor.json` checkpoint.
- Inspection surfaces: GET /api/admin/extraction-health (compliance + coverage + 7d failure rates), GET /api/part-price-alerts/me (active alerts), GET /health and /ready (liveness/readiness during operator checkpoint), backend/.perf-runs/ (perf evidence), .crawler-state/backfill_cursor.json (resume position), .gsd/milestones/M002/slices/S13/uat-evidence/ (committed UAT evidence dump).
- Failure visibility: T01 captures pageerror via Playwright already-shipped specs; UAT log-tailing surfaces extraction failures via `extraction_failure_rate` EMF + structured WARN logs; T02 FAILED.json contains canonical "Open R036 (materialized part_price_summary) per D004" remediation string and exit code 1; T05 backfill exits 2 above-threshold-failure-rate and writes summary to log.
- Redaction constraints: NO email addresses, JWT tokens, or unsubscribe-token query strings in any committed evidence file. Screenshots of the inbox redact the recipient address before commit. Live SES sends use a `+`-suffix on a real operator inbox (e.g. tylert2610+m002-uat@gmail.com) so post-UAT cleanup doesn't pollute the operator's primary inbox.

## Tasks

- [x] **T01: Run live full-stack UAT walkthrough — extraction → ingest → /parts sparkline → /parts/:id breakdown → alert email → unsubscribe** `est:90m`
  Execute the slice's demo statement end-to-end against a live local stack. This is the highest-blast-radius task in S13 — if it fails, every later task is wasted. Operator pre-flight: docker-compose up -d (Postgres 16), `cd backend && alembic upgrade head`, `cd backend && python ../scripts/populate_sample_data.py` (seed coilover/brake/turbo parts + observations + retailers + a test user with verified email), `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust uvicorn app.main:app --port 8000` (backend), `cd frontend && npm run dev` (frontend on :4000). Confirm GET http://localhost:8000/health returns 200 and GET http://localhost:8000/ready returns 200 before proceeding.

Branch decision for the live-fetch portion: prefer archive_rescrape against a representative S3-archived HTML body OR `python -m app.crawlers --adapter bcracing --limit 1` if the retailer is healthy at UAT time. Both exercise universal-extraction → category-extraction → Pydantic validation → ingest → Part.specifications populated. Sample-data injection alone is INSUFFICIENT — the slice plan demo statement requires the extraction loop be exercised. Tail the backend log during the run and capture: `universal_extraction_extracted`, `category_extraction_validated: part_id=<uuid>`, `ingest_payload: parse_status=parsed_ok`, and the resulting Part.specifications dict.

Walk the frontend demo: log in as the test user; visit /parts and confirm the chosen part shows a sparkline + delta line; click into /parts/:id and confirm the 'Price summary (90 days)' block renders with the per-retailer breakdown (flat list ≤3 retailers, Tabs >3); confirm the legacy PriceHistoryLineChart STILL RENDERS (T03 deletes it — at this point it must still be intact); subscribe to a price drop with threshold=current_price+$5 (so the next observation will fire); inject one observation below threshold via `python -c 'from app.api.services.part_listing_service import create_or_update_listing_and_price...'` against the live DB OR replay an archive_rescrape with a downward-shifted price; tail the log for `price_alert_evaluated: verdict=fired` and `price_alert_email_sent: success=true`. Operator confirms email arrives in `tylert2610+m002-uat@gmail.com` (or the configured fixture inbox); operator clicks the unsubscribe link → 302 redirect → /account/alerts?status=success → row removed.

Capture all evidence into `.gsd/milestones/M002/slices/S13/uat-evidence/`: backend log excerpt (universal+category+ingest+alert lines, redacted of email addresses), screenshots of /parts (sparkline visible), /parts/:id (retailer breakdown, both ≤3 and >3 cases if sample data permits), /account/alerts (subscribed state + post-unsubscribe state), inbox email render (recipient redacted). Document each artifact in S13-UAT.md with a one-line caption.

AUTONOMOUS-MODE CHECKPOINT: Auto-mode CANNOT bring up Docker. The executor must verify the stack is live (curl /health, curl /ready, curl /api/parts/?limit=1 expecting 200) before proceeding. If any check fails, write a blocker note to T01-SUMMARY.md describing what's down and exit cleanly — do NOT attempt to launch Docker. Operator resumes the task after bringing the stack up.

SES live-send caveat: if `app.core.email.send_price_drop_alert_email` dry-runs by default in dev (verify by reading email.py), set the env vars to force live send. The S07-deferred 'live SES UAT' is the heart of T01 — without an email arriving in the operator's inbox, T01 has not completed.
  - Files: `backend/app/main.py`, `backend/app/crawlers/__main__.py`, `backend/app/api/endpoints/parts.py`, `backend/app/core/email.py`, `backend/app/api/services/part_listing_service.py`, `backend/app/api/services/part_price_alert_service.py`, `frontend/src/pages/parts/PartsCatalog.tsx`, `frontend/src/pages/builder/ViewPart.tsx`, `frontend/src/pages/account/AccountAlerts.tsx`, `.gsd/milestones/M002/slices/S13/uat-evidence/`, `.gsd/milestones/M002/slices/S13/S13-UAT.md`
  - Verify: test -f .gsd/milestones/M002/slices/S13/S13-UAT.md && test -d .gsd/milestones/M002/slices/S13/uat-evidence && test $(ls .gsd/milestones/M002/slices/S13/uat-evidence/ | wc -l) -ge 5 && grep -q 'price_alert_email_sent' .gsd/milestones/M002/slices/S13/uat-evidence/*.log

- [x] **T02: Run S05 perf gate at 10× and promote R019 — or open R036 on FAIL** `est:30m`
  Re-run the S05 perf gate against the same live stack T01 brought up. Command (from project root): `bash backend/scripts/perf/run_price_history_loadtest.sh`. The script's exit-code contract (locked by MEM050/MEM053) is: 0 PASS, 1 FAIL (FAILED.json written → R036 should open per D004), 2 locust crashed, 3 CSV malformed, 4 CSV missing, 5 empty CSV, 6 missing per-endpoint row.

On PASS (exit 0): a fresh `backend/.perf-runs/price-history-PASSED-<iso8601>.json` lands. Copy it to `.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json` (committed). Promote R019 from active to validated via `gsd_requirement_update` with status='validated' and a notes field referencing `.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json`. R036 stays unopened — its precondition (R019 misses) was not met.

On FAIL (exit 1): the FAILED.json contains the canonical remediation string `Open R036 (materialized part_price_summary) per D004`. DO NOT retry-loop — this is an explicit branch into M003 work, not a transient failure. Copy FAILED.json to `.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-FAILED.json`. Surface a milestone blocker: write a clear note to T02-SUMMARY.md, leave R019 status=active, and call `gsd_requirement_save` to file R036 with class=quality-attribute, status=active, source citing the FAILED.json path. T06's milestone validation verdict will then be `needs-remediation` and the milestone summary explicitly lists R036 as the M003 carry-forward.

On exit codes 2–6: the script crashed mechanically before producing a verdict. This is a setup issue (locust missing, uvicorn down, sample data not seeded), not a perf miss. Diagnose, fix the env, re-run.

AUTONOMOUS-MODE NOTE: T02 reuses T01's live stack. If T01 was checkpointed because Docker wasn't up, T02 cannot proceed either. Operator runs T02 after bringing stack up; auto-mode executor only confirms PASSED.json was written and copies it.
  - Files: `backend/scripts/perf/run_price_history_loadtest.sh`, `backend/scripts/perf/locustfile_price_history.py`, `backend/scripts/perf/_parse_locust_csv.py`, `backend/.perf-runs/`, `.gsd/milestones/M002/slices/S13/uat-evidence/`, `.gsd/REQUIREMENTS.md`
  - Verify: test -f .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json || test -f .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-FAILED.json

- [x] **T03: Remove S05 legacy=true price-history shim and regenerate OpenAPI snapshot** `est:60m`
  Pure code change — the only code increment S13 owes. The S05 explicit follow-up was: remove the `legacy=true` query-param branch on GET /parts/{id}/price-history once the new summary endpoint is the canonical consumer. Audit confirmed (verified at slice planning): the only frontend caller is `frontend/src/pages/builder/ViewPart.tsx:82` (`partsApi.getPartPriceHistory(partId)`), which feeds `frontend/src/components/parts/PriceHistoryLineChart.tsx`. The S06 'Price summary (90 days)' block above already covers the user need. Chrome extension has zero hits for `getPartPriceHistory` or `price-history?legacy` (verified via grep).

Backend changes in `backend/app/api/endpoints/parts.py`:
1. Drop the `legacy: bool = False` query parameter on the `get_part_price_history` route.
2. Drop the entire `_legacy_get_part_price_history` private helper (function ends around line 1190 — read first to confirm exact range).
3. Drop the `if legacy: return _legacy_get_part_price_history(db, part_id, retailer_id)` branch.
4. Drop the `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]` return-type union — narrow to just `PriceHistorySinglePartResponse`.

Frontend changes:
5. `frontend/src/api/parts.ts`: remove the `getPartPriceHistory(partId, params?)` function entirely (it forwards `legacy: true`). It is the only caller of the legacy shim.
6. `frontend/src/api/parts.test.ts`: drop the 3 legacy-regression test cases at lines ~223, ~234, ~250 (`getPartPriceHistory GETs /parts/:id/price-history with legacy=true and no other params`, `getPartPriceHistory forwards retailer_id alongside legacy=true`, `getPartPriceHistory still uses legacy=true shim and returns array shape`).
7. `frontend/src/pages/builder/ViewPart.tsx`: remove the `getPartPriceHistory` import (line 38), remove the legacy useApiRequest call (line 82), remove the entire JSX block that renders `<PriceHistoryLineChart data={priceHistoryData} />` (line 816). The S06 'Price summary (90 days)' block above stays as the canonical price-history surface. Update any types/loading-state accordingly.
8. Delete `frontend/src/components/parts/PriceHistoryLineChart.tsx` (no other consumers).
9. `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`: drop the comment line at ~117 referencing the removed legacy fetcher; if any test assertion targeted the legacy chart specifically, drop it.

Backend test changes:
10. `backend/tests/api/endpoints/test_parts_price_history.py`: drop the legacy-shape regression-guard test cases. Existing object-shape tests stay green.

OpenAPI regeneration:
11. From `backend/`: `TESTING=true ENABLE_RATE_LIMITING=false python -c 'import json,sys;from app.main import app;sys.stdout.write(json.dumps(app.openapi(),indent=2,sort_keys=True))' > tests/fixtures/openapi_snapshot.json` (per MEM088).

Verification:
- `cd backend && TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --no-cov` exits 0.
- `cd frontend && npm run type-check` exits 0.
- `cd frontend && npm test -- --run src/api/parts.test.ts src/pages/builder/ViewPart.priceSummary.test.tsx` exits 0.
- `grep -rn 'legacy=true\|legacy: true\|getPartPriceHistory\b\|PriceHistoryLineChart' frontend/src backend/app` returns ONLY matches inside .test files that intentionally remain (or zero matches if all consumers removed).
  - Files: `backend/app/api/endpoints/parts.py`, `backend/tests/api/endpoints/test_parts_price_history.py`, `backend/tests/fixtures/openapi_snapshot.json`, `frontend/src/api/parts.ts`, `frontend/src/api/parts.test.ts`, `frontend/src/pages/builder/ViewPart.tsx`, `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`, `frontend/src/components/parts/PriceHistoryLineChart.tsx`
  - Verify: cd backend && TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --no-cov && cd ../frontend && npm run type-check && npm test -- --run src/api/parts.test.ts src/pages/builder/ViewPart.priceSummary.test.tsx && ! grep -rn 'PriceHistoryLineChart' src/

- [x] **T04: Run compliance-audit + admin extraction-health live verification + fix PROJECT.md adapter-count drift** `est:30m`
  Final adapter-contract proof against the live stack. Three verifications:

1. Compliance audit: `cd backend && python -m app.crawlers.compliance_audit`. Expected output (per MEM037/MEM122 — 108 not 111): exit 0, stdout contains `Total: 108/108 compliant` and per-tier breakdown `T0 (http): 83/83 compliant`, `T1 (tls): 15/15 compliant`, `T2 (browser): 10/10 compliant`. Capture stdout to `.gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt`.

2. Admin extraction-health endpoint live hit: against the running uvicorn from T01, log in as an admin user (use the test admin or promote the test user via `python -c 'from app.api.models.user import User; ... .is_admin=True'`), grab the JWT cookie, then `curl -H 'Cookie: <admin-token>' http://localhost:8000/api/admin/extraction-health | python -m json.tool > .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json`. Assert in the captured JSON: `compliance.compliant == 108`, `compliance.total == 108`, `compliance.per_tier.http == '83/83'`, `compliance.per_tier.tls == '15/15'`, `compliance.per_tier.browser == '10/10'`, `coverage.per_tier` keys present, `failure_rate_7d` is a list, `window.days == 7`. Visual smoke /admin/extraction-health in the browser (operator) — confirm the S11 UI rendering matches the JSON shape; capture a screenshot to `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-ui.png`.

3. Fix PROJECT.md adapter-count drift: per MEM037/MEM122 and S03's deviations, the roadmap text in PROJECT.md still says '111 adapters' in places. The live ADAPTER_REGISTRY has 108. Read PROJECT.md, find every '111' that refers to adapter count (the 3-adapter delta is IS_FALLBACK GenericHtmlParser instances per tier excluded from the registry per D-03), and correct to '108' with a brief inline note. Do NOT modify M002-ROADMAP.md (historical artifact — slice plans/summaries already note the drift).

Verification: `grep -n '111' .gsd/PROJECT.md | grep -i adapter` returns no hits after the correction. The compliance-audit stdout file exists and contains '108/108'. The admin-extraction-health.json file exists and contains valid JSON with `compliance.compliant: 108`.
  - Files: `backend/app/crawlers/compliance_audit.py`, `backend/app/api/endpoints/admin/extraction_health.py`, `.gsd/PROJECT.md`, `.gsd/milestones/M002/slices/S13/uat-evidence/`
  - Verify: test -f .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt && grep -q '108/108' .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt && test -f .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json && python -c 'import json;d=json.load(open(".gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json"));assert d["compliance"]["compliant"]==108'

- [x] **T05: Kick off backfill (started, not complete) and capture cursor + progress evidence** `est:45m`
  R005 says 'Started by milestone end; can finish post-merge' — T05's bar is `started`, not `complete`. Run the backfill against the live local DB to confirm the CLI is wired correctly and produces the expected runtime signals.

From `backend/`: first a dry-run to confirm shape with no behavior change — `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --dry-run --limit 50`. Confirm CLI exits 0, logs `backfill: batch=...` lines, and writes nothing (no cursor file, no Part.specifications mutations).

Then a real run as the `started` evidence: `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --limit 100 2>&1 | tee /tmp/backfill-run.log`. Expected: per-batch INFO log `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns`, final summary log line, exit 0, `backend/.crawler-state/backfill_cursor.json` lands.

Copy the log + cursor to evidence: `cp /tmp/backfill-run.log .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log` and `cp backend/.crawler-state/backfill_cursor.json .gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json`. The cursor file remains in `backend/.crawler-state/` (gitignored per S04) for an operator to resume — DO NOT delete it.

Then re-hit `GET /api/admin/extraction-health` and confirm whatever delta the run produced shows up in `coverage.per_tier.<tier>.parts_with_specs` (it should increase if any of the 100 sampled parts had archived HTML and successfully re-extracted). Capture a fresh JSON dump to `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json` for diff.

AUTONOMOUS-MODE NOTE: T05 also reuses T01's live stack. If Docker isn't up, T05 cannot proceed. The dry-run portion in particular requires the live DB to query the empty-specs filter against real Part rows.
  - Files: `backend/app/crawlers/backfill.py`, `backend/.crawler-state/backfill_cursor.json`, `.gsd/milestones/M002/slices/S13/uat-evidence/`
  - Verify: test -f .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log && grep -q 'backfill: batch=' .gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log && test -f .gsd/milestones/M002/slices/S13/uat-evidence/backfill-cursor-snapshot.json && test -f .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json

- [x] **T06: Final test gauntlet, milestone validation + summary, requirement promotion** `est:60m`
  Close M002. Run the full local gauntlet, then write the milestone-close artifacts and promote requirement statuses.

**Step 1 — Gauntlet:** Run sequentially and capture exit codes. Each MUST exit 0 (lint MUST be at the MEM062 baseline of 108 errors with zero NEW errors in S13-touched files):

- Backend: `TESTING=true pytest -n auto --rootdir=backend -q --no-cov` from project root
- Frontend type-check: `cd frontend && npm run type-check`
- Frontend unit: `cd frontend && npm test -- --run`
- Frontend e2e: `cd frontend && npm run test:e2e` (must pass at all 3 viewports — mobile/tablet/desktop)
- Frontend lint: `cd frontend && npm run lint` — exit code 1 is acceptable IF total errors == 108 (MEM062 baseline) AND grep of the lint output shows zero errors in S13-touched files (only T03 changes ViewPart.tsx + parts.ts + parts.test.ts + ViewPart.priceSummary.test.tsx)
- Crawler audit: `cd backend && python -m app.crawlers.compliance_audit` exits 0 reporting 108/108

Capture each command + exit code + verdict to `.gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json` as a JSON array (command/exitCode/verdict/durationMs).

**Step 2 — Promote requirement statuses via gsd_requirement_update:** For each of the 12 active M002 requirements, set status='validated' with a notes field referencing the evidence path:
- R002 (universal extractor) — evidence: T01 extraction-and-alert.log + T04 compliance-audit-stdout.txt
- R003 (108-adapter compliance) — evidence: T04 compliance-audit-stdout.txt
- R005 (backfill started) — evidence: T05 backfill-run.log + backfill-cursor-snapshot.json
- R006 (admin extraction-health) — evidence: T04 admin-extraction-health.json
- R008 (sparkline + delta line) — evidence: T01 parts-sparkline.png + S06 e2e baselines
- R009 (per-part detail view + retailer breakdowns + 60d caveat) — evidence: T01 parts-detail-breakdown.png + S06 e2e baselines
- R010 (price-drop alerts end-to-end) — evidence: T01 inbox-email-render.png + extraction-and-alert.log
- R016 (admin shell on new design system) — evidence: T01/T04 admin-extraction-health-ui.png + S11 e2e baselines
- R017 (all ~17 pages on new design system) — evidence: S12 vitest grep-guard test + ESLint no-restricted-imports + components/common+buttons deleted
- R018 (crawler test suite) — evidence: gauntlet pytest backend exit 0 + S03/S04 test counts in summaries
- R019 (perf gate at 10×) — evidence: T02 perf-gate-PASSED.json (or carry-forward as needs-remediation if FAIL)
- R020 (keyboard nav + focus + escape on dialogs) — evidence: S09/S10/S11 e2e desktop keyboard tests + Radix focus-trap behavior

**Step 3 — Author M002-VALIDATION.md via gsd_validate_milestone:** Set verdict='passed' (assuming gauntlet greens AND R019 PASSED — otherwise verdict='needs-remediation' with R036 in the remediation plan). Fill all required sections: successCriteriaChecklist (against the 9 M002 success criteria), sliceDeliveryAudit (S01-S13 — each shipped what was promised), crossSliceIntegration (T01 demo proves the full loop), requirementCoverage (the 12 promotions above + acknowledgement that the 12 still-active R001/R004/R007/R011/R012/R013/R014/R015 may have been covered by prior slice closures — confirm against REQUIREMENTS.md). verdictRationale: 'Live UAT exercised the full extraction → ingest → UI → alert email loop; perf gate met R019 budget; all S08-S12 design-system surfaces verified at 3 viewports; 108-adapter compliance held; backfill started.' Also fill verificationClasses if any prior slice's verification was deferred to S13.

**Step 4 — Author M002-SUMMARY.md via gsd_complete_milestone:** Set verificationPassed=true (assuming Step 3's verdict is 'passed'). Cross-link the uat-evidence/ files. Document carry-forward (NOT blockers): AccountAlerts MEM097 self-cancel useEffect bug (deferred to a future slice that touches that file), lint baseline 108 errors per MEM062 (pre-existing, not regression), backfill long-tail completion (R005 says 'started, not complete' — long-running completion is post-merge), light theme R035 (deferred carry-forward).

**Step 5 — Save M002-close decisions/learnings:** Append any S13-surfaced decisions to `.gsd/DECISIONS.md` via `gsd_save_decision` (e.g., D-XX 'M002 close: live UAT verifies SES path with `+`-suffix fixture inbox' if that decision is not yet captured). Surface any new gotchas via `capture_thought` (e.g., the live retailer fetch vs archive_rescrape vs sample-data trade-off if that picked up new sharp edges in T01).

AUTONOMOUS-MODE NOTE: gsd_validate_milestone and gsd_complete_milestone are DB-write tools that regenerate the markdown — do NOT hand-edit M002-VALIDATION.md or M002-SUMMARY.md. The auto-mode executor calls the tools with full payloads.
  - Files: `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/milestones/M002/M002-VALIDATION.md`, `.gsd/milestones/M002/M002-SUMMARY.md`, `.gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json`
  - Verify: test -f .gsd/milestones/M002/M002-VALIDATION.md && test -f .gsd/milestones/M002/M002-SUMMARY.md && test -f .gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json && python -c 'import json;d=json.load(open(".gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json"));assert all(c["exitCode"]==0 or (c["command"].endswith("npm run lint") and c["verdict"]=="baseline") for c in d)'

## Files Likely Touched

- backend/app/main.py
- backend/app/crawlers/__main__.py
- backend/app/api/endpoints/parts.py
- backend/app/core/email.py
- backend/app/api/services/part_listing_service.py
- backend/app/api/services/part_price_alert_service.py
- frontend/src/pages/parts/PartsCatalog.tsx
- frontend/src/pages/builder/ViewPart.tsx
- frontend/src/pages/account/AccountAlerts.tsx
- .gsd/milestones/M002/slices/S13/uat-evidence/
- .gsd/milestones/M002/slices/S13/S13-UAT.md
- backend/scripts/perf/run_price_history_loadtest.sh
- backend/scripts/perf/locustfile_price_history.py
- backend/scripts/perf/_parse_locust_csv.py
- backend/.perf-runs/
- .gsd/REQUIREMENTS.md
- backend/tests/api/endpoints/test_parts_price_history.py
- backend/tests/fixtures/openapi_snapshot.json
- frontend/src/api/parts.ts
- frontend/src/api/parts.test.ts
- frontend/src/pages/builder/ViewPart.priceSummary.test.tsx
- frontend/src/components/parts/PriceHistoryLineChart.tsx
- backend/app/crawlers/compliance_audit.py
- backend/app/api/endpoints/admin/extraction_health.py
- .gsd/PROJECT.md
- backend/app/crawlers/backfill.py
- backend/.crawler-state/backfill_cursor.json
- .gsd/DECISIONS.md
- .gsd/milestones/M002/M002-VALIDATION.md
- .gsd/milestones/M002/M002-SUMMARY.md
- .gsd/milestones/M002/slices/S13/uat-evidence/gauntlet-evidence.json
