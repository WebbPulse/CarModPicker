---
slice: S13
parent: M002
title: Final integration + milestone verification
depth: targeted
---

# S13: Final integration + milestone verification — Research

## Summary

S13 closes M002. By design it ships almost no new code — every functional surface (S01–S12) is already tested at the contract layer, and the priority pages (build-list, parts catalog, admin) plus the kitchen-sink primitive page already have multi-viewport Playwright coverage. What S13 owes is the **live, full-stack proof** that those surfaces compose end-to-end against a real backend + real DB + real SES path, plus three explicit milestone-close artifacts the slice plan and milestone-context call out:

1. **Live integration UAT** — pick a real coilover/brake/turbo product URL, run a live scrape (or archive rescrape), watch logs flow universal-extraction → category-extraction → Pydantic validation → ingest → `Part.specifications` populated → aggregation API returns history → `/parts` shows sparkline → detail page shows retailer breakdowns. Then subscribe with threshold > current, trigger an observation, confirm the SES email lands in a fixture inbox, click the unsubscribe link, confirm the alert deactivates.
2. **Live perf-gate run** — `bash backend/scripts/perf/run_price_history_loadtest.sh` against a uvicorn server with sample-data seed; `backend/.perf-runs/price-history-PASSED-<iso8601>.json` lands; R019 promotes from active to validated; R036 stays unopened. If it FAILs, the canonical remediation string in FAILED.json says "Open R036 (materialized `part_price_summary`) per D004" — that's the prescribed branch; do not retry-loop.
3. **Cleanup + milestone validation artifacts** — remove the `legacy=true` shim on `GET /parts/{id}/price-history` per S05's explicit follow-up, plus generate the M002-VALIDATION.md / M002-SUMMARY.md per the verdict.

The slice has the lowest residual risk in M002 (`risk:low` per ROADMAP) but the highest "system goes live for real" coverage. Everything depends on docker-compose Postgres, populate_sample_data.py, AWS SES creds for the alert email, and (for the live scrape branch) an outbound request to a real retailer or a representative archived `crawl_html/by_url/` HTML body. Auto-mode does NOT bring up Docker; the live UAT pieces are operator-driven and the slice plan explicitly anticipates this — many task summaries (S04, S05, S07) defer "live SES / live perf / live scrape" specifically to S13.

A second responsibility S13 owes — implicitly from S12's follow-ups, S05's follow-ups, and the lint baseline drift captured in MEM062 → 108 — is **deciding what's out of scope and what is not**. Scope guardrail: nothing that doesn't directly contribute to milestone-close gate-passing. Lint debt cleanup, AccountAlerts MEM097 useEffect bug, the legacy PriceHistoryLineChart sibling on /parts/:id, vitest e2e collection noise (MEM128/MEM129) — all flagged as future work, none required for M002 close.

## Recommendation

**Approach (sequence-of-tasks shape):**

1. **T01 — Live full-stack walkthrough script + execution** (the demo gate).
   - Docker up → migrations → populate_sample_data → uvicorn + frontend dev → walk the slice-plan demo statement end-to-end.
   - Branch on environment: if outbound retailer fetch is unsafe/flaky, use `archive_rescrape` against a representative S3-archived HTML body OR exercise `populate_sample_data`'s seeded coilover/brake/turbo with a fresh observation injected via the test endpoint (preferred — repeatable, no flakiness).
   - SES live email send hits a fixture inbox (`tylert2610+m002-uat@gmail.com` or similar `+`-suffix); operator confirms receipt and clicks unsubscribe.
   - Capture: log excerpts (universal extraction → category extraction → ingest), screenshots of /parts (sparkline), /parts/:id (retailer breakdown), /account/alerts, the inbox email render. Land artifacts under `.gsd/milestones/M002/slices/S13/uat-evidence/`.

2. **T02 — Live perf-gate run + R019 validation** (R019 promotion).
   - Same uvicorn + sample-data setup. `bash backend/scripts/perf/run_price_history_loadtest.sh`.
   - On PASS: PASSED.json drops in `backend/.perf-runs/`; copy to `.gsd/milestones/M002/slices/S13/uat-evidence/`; promote R019 status from active to validated via `gsd_requirement_update` with the latest evidence path.
   - On FAIL: FAILED.json drops the R036/D004 remediation string; do NOT retry-loop. The slice's exit path is to file R036 and surface a milestone blocker; auto-mode escalates to checkpoint.

3. **T03 — Legacy shim removal** (S05 explicit follow-up).
   - Audit callers of `getPartPriceHistory` (`legacy=true` shape). Today: only `frontend/src/pages/builder/ViewPart.tsx:82` consumes it (feeds `PriceHistoryLineChart`). The Chrome extension is checked in at `chrome-extension/src/` — verify whether its part-detail prefetch hits this path.
   - Migrate ViewPart's legacy call to consume `getPartPriceHistorySummary` (S06 already added the parallel summary fetch) and refactor PriceHistoryLineChart to read the new shape, OR retire PriceHistoryLineChart in favor of the existing S06 stat-strip + retailer breakdown. Prefer the second — the S06 block already covers the user need; the legacy chart is duplicative.
   - Backend: drop the `legacy=true` query param branch + private `_legacy_get_part_price_history` helper in `backend/app/api/endpoints/parts.py`; regenerate the OpenAPI snapshot per MEM088.

4. **T04 — Compliance audit re-run + admin-endpoint live hit** (final adapter contract proof).
   - `cd backend && python -m app.crawlers.compliance_audit` → expect "Total: 108/108 compliant" exit 0 (108 not 111 per MEM037/MEM122; fix the milestone roadmap text drift in PROJECT.md).
   - `curl http://localhost:8000/api/admin/extraction-health` (admin auth via `Cookie: <admin-token>`) → assert response shape matches `ExtractionHealthResponse` and compliance.compliant == 108. Visual smoke /admin/extraction-health in browser to confirm the S11 UI rendering matches.

5. **T05 — Backfill kickoff + visibility** (R005 operability proof).
   - `cd backend && python -m app.crawlers.backfill --batch-size 100 --max-failure-rate 0.5 --dry-run --limit 50` first to confirm the CLI is wired against the live DB (no behavior change; just confirms shape); then a real `--limit 100` run as the "started" gate per R005 (started, not complete).
   - Confirm `backend/.crawler-state/backfill_cursor.json` lands; confirm /admin/extraction-health coverage block reflects whatever delta the run produced.

6. **T06 — Final test gauntlet + milestone-validation artifacts** (write-the-paper).
   - Backend: `TESTING=true pytest -n auto --rootdir=backend -q --no-cov` from project root.
   - Frontend: `npm run type-check && npm test -- --run && npm run test:e2e && npm run lint`.
   - Crawler: `python -m app.crawlers.compliance_audit` exit 0.
   - Author M002-VALIDATION.md (per `gsd_validate_milestone` shape — verdict + checklists for success criteria + slice delivery audit + cross-slice integration + requirement coverage).
   - Author M002-SUMMARY.md if `gsd_complete_milestone` requires it; cross-link evidence files; capture remaining follow-ups (legacy shim removal complete, lint baseline cleanup deferred, AccountAlerts MEM097 deferred, etc.).
   - Save decisions/learnings: D-XX for "live UAT verifies SES path with fixture inbox" if not already captured; capture-thought new gotchas surfaced.
   - Promote requirement statuses: R002, R003, R005, R006, R008, R009, R010, R016, R017, R018, R019, R020 — most still `active`; S13 is the validation gate.

**Why this shape:** Tasks are ordered by dependency on a live stack (T01 needs DB + uvicorn; T02 reuses that stack; T03 is pure code change; T04 reuses T01's stack; T05 reuses T01's stack; T06 is the wrap-up). T01 runs first because it's the highest-value demo — if it fails, every later task is wasted. T02 runs next because if it fails, R036 opens and the milestone slips. T03 (legacy shim removal) is the only code change S13 owes; it must land before the final test gauntlet so test+lint+type-check exercise the cleaned shape. T04/T05 are operational confirmations the slice plan demands. T06 closes.

**Risks to budget:**
- **Auto-mode can't bring up Docker.** Operator must confirm Postgres + uvicorn + frontend dev server are running; T01–T02–T04–T05 stall otherwise. The slice plan should explicitly checkpoint at T01-start with operator confirmation.
- **SES live send.** Requires a working IAM role / SES credential and an inbox the operator can read. If `app.core.email.send_price_drop_alert_email` is configured to dry-run by default in dev (verify), enable live send via env vars. The S07-deferred "live SES UAT" is the heart of T01.
- **Live retailer fetch.** Real outbound HTTP to `bcracing.com` etc. is rate-limit-sensitive and can flake. Prefer `archive_rescrape` against a known-good S3-archived HTML body OR sample-data injection — both deterministic, neither flaky.
- **Perf-gate FAIL.** R019's branch is "open R036." That's a slice-fork into M003. The slice plan should encode this branch explicitly; auto-mode should checkpoint, not retry.
- **Lint baseline drift.** MEM062 baseline = 108. S12's wrap-up confirmed it's still 108. T06's `npm run lint` will report 108. That's not a regression; that's the agreed baseline. Document it explicitly in M002-VALIDATION.md so the milestone-close audit doesn't trip on it.

## Implementation Landscape

### Files that exist today and need to change

| File | Why | What changes |
|---|---|---|
| `backend/app/api/endpoints/parts.py` | T03 — drop the `legacy=true` shim per S05 follow-up | Remove `legacy: bool = False` query param; remove `_legacy_get_part_price_history` private helper; drop `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]` typing → return only the new shape. Regenerate OpenAPI snapshot. |
| `backend/tests/api/endpoints/test_parts_price_history.py` | T03 — remove the `legacy=true` regression-guard test | Drop the legacy-shape test cases; existing object-shape tests stay green. |
| `backend/tests/fixtures/openapi_snapshot.json` | T03 — drift after removing legacy param | Regenerate per MEM088: `TESTING=true ENABLE_RATE_LIMITING=false python -c '...openapi(),sort_keys=True...' > tests/fixtures/openapi_snapshot.json`. |
| `frontend/src/api/parts.ts` | T03 — drop the `legacy=true` forwarding | `getPartPriceHistory` no longer needs to forward `legacy: true`; either delete the function entirely (preferred — only one caller) or migrate it to call the summary endpoint. |
| `frontend/src/api/parts.test.ts` | T03 — drop the 3 legacy-regression test cases | Tests at lines 223/234/250 will fail when the shim is removed; delete them. |
| `frontend/src/pages/builder/ViewPart.tsx` | T03 — migrate the `getPartPriceHistory` consumer | Either (a) delete the legacy `PriceHistoryLineChart` block entirely (the S06 "Price summary (90 days)" block above already covers the user need), or (b) migrate `PriceHistoryLineChart` to consume `PriceHistorySinglePartResponse.history`. Prefer (a) — duplicative UI. |
| `frontend/src/components/parts/PriceHistoryLineChart.tsx` | T03 — likely delete entirely | If chosen path (a) above, delete. If (b), refactor input shape. |
| `chrome-extension/src/**` | T03 — verify | Grep for `getPartPriceHistory` / `price-history?legacy`. If chrome-extension hits the legacy path it's an out-of-band consumer — keep the shim or migrate the extension. Likely no hit. |
| `.gsd/REQUIREMENTS.md` (via tool) | T06 — promote validation statuses | Use `gsd_requirement_update` for R002, R003, R005, R006, R008, R009, R010, R016, R017, R018, R019, R020 with the evidence-path narrative. Cannot edit REQUIREMENTS.md directly — must use the tool (regenerates the markdown from DB). |
| `.gsd/PROJECT.md` | T04 — fix "111 adapters" → "108 adapters" | Roadmap drift documented in MEM037/MEM122 and S03's deviations. Land the correction in PROJECT.md as part of S13. The roadmap text in M002-ROADMAP.md is also affected but is historical; correct PROJECT.md only. |
| `.gsd/milestones/M002/M002-VALIDATION.md` | T06 — milestone validation artifact | Generated via `gsd_validate_milestone` per its tool contract. Verdict: passed (assuming the gauntlet greens). Includes successCriteriaChecklist, sliceDeliveryAudit, crossSliceIntegration, requirementCoverage. |
| `.gsd/milestones/M002/M002-SUMMARY.md` | T06 — milestone close artifact | Generated via `gsd_complete_milestone` once all slices are complete + verification passed. |
| `.gsd/milestones/M002/slices/S13/uat-evidence/` | T01–T05 — operator evidence dump | New directory. Holds: live-scrape log excerpts, screenshots of /parts + /parts/:id + /account/alerts + inbox render, perf-gate PASSED.json copy, compliance-audit stdout, backfill log excerpt + cursor JSON snapshot, /admin/extraction-health JSON dump. |
| `.gsd/milestones/M002/slices/S13/S13-UAT.md` | T06 — committed UAT script + verdict | Mirror S09/S10/S11 UAT pattern. Records each demo gate's pass/fail with evidence link. |

### What S13 doesn't touch (deliberately out of scope)

- **AccountAlerts MEM097 self-cancel useEffect bug** — flagged in S07 follow-ups, captured in MEM097/MEM102. Hidden by vitest sync mocks; surfaces only in production-latency UI but doesn't block the milestone. Document as carry-forward.
- **Lint baseline 108 errors** — pre-existing in PriceAlertSubscribeButton/AccountAlerts/ui/* and pre-existing test files. MEM062 baseline. Not a regression. T06 records the number; doesn't pay it down.
- **Vitest e2e collection noise** — 7 e2e/*.spec.ts files crash collection because they import @playwright/test (MEM128/MEM129). S12 fixed via vitest.config.ts include/exclude — confirm still applied.
- **Backfill *complete*** — R005 says "started, not complete." T05 just kicks it off. Long-running completion is post-merge.
- **Lint rule R017 enforcement** — already landed in S12 via vitest grep-guard + ESLint no-restricted-imports rule. Confirm in T06.

### What runs on a live stack

T01, T02, T04, T05 ALL require:
- `docker-compose up -d` (Postgres 16 on port 5432)
- `cd backend && alembic upgrade head` (migrations)
- `cd backend && python ../scripts/populate_sample_data.py` (seed parts + observations + retailers)
- `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust uvicorn app.main:app --port 8000` (backend)
- `cd frontend && npm run dev` (frontend on :4000)
- For T01's SES path: live AWS SES credentials + a real inbox

**Auto-mode flow:** spawn a background bg_shell for each long-lived process, AskUserQuestion to confirm env vars, then run the demo statement step-by-step. The slice plan should encode an explicit checkpoint pattern: "operator confirms uvicorn responds at /health" before T01 proceeds.

### Live-scrape vs. archive-rescrape vs. sample-data trade-offs

Three viable options for proving the universal-extraction → category-extraction → ingest → UI flow end-to-end:

| Option | Pros | Cons | Recommended |
|---|---|---|---|
| Live retailer fetch (`python -m app.crawlers --adapter bcracing --limit 1`) | Truly end-to-end, exercises real HTTP path, real adapter parsing | Rate-limit risk, retailer downtime risk, cookie/TLS flakiness, can be blocked by anti-bot | Yes if a coilover/brake/turbo specialist URL is healthy at UAT time. T0 (http) tier preferred — bcracing.com is the cleanest. |
| Archive rescrape (run `backfill --limit 1` against a single archived part) | Deterministic, no outbound HTTP, exercises the full extraction → ingest → admin-endpoint visibility loop | Doesn't exercise the live fetcher path | Yes as fallback if live fetch flakes. Same code path post-fetch. |
| Sample-data + injected observation (POST /api/listings/observation directly) | Deterministic, fast, exercises only price-history → UI → alert email path | Doesn't exercise extraction at all | No — skips the whole extraction loop the slice plan wants demonstrated. |

The slice plan lines (verbatim from ROADMAP S13): "Run a live scrape. Observe in logs: universal extraction → category extraction → Pydantic validation → ingest → Part.specifications populated." Translation: option 1 with option 2 as fallback. Option 3 doesn't satisfy the spirit.

### Live SES email path

`backend/app/core/email.py::send_price_drop_alert_email` is wired to call `boto3.client("ses").send_email`. Local development typically dry-runs (verify by reading email.py). For T01's UAT bar, override via env to force live send. Use a `+`-suffix on a real inbox so unsubscribing doesn't clutter the operator's inbox indefinitely. Capture:
- Server log line `price_alert_email_sent: alert_id=... user_id=... success=true`
- Email render screenshot (full template — part name, current price, retailer, CTA, unsubscribe link)
- Click unsubscribe → confirm 302 redirect → `/account/alerts?status=success` lands → row removed
- Re-check `GET /api/part-price-alerts/me` → row marked `active=False` (or absent — soft-delete pattern from S07)

### Perf-gate RUN context (T02)

Reference: `backend/scripts/perf/README.md`. Locust scenario: `--users 50 --spawn-rate 10 --run-time 60s`, weight 4:1 GET:POST. Budget: GET p95 < 200ms, POST p95 < 500ms, error_rate == 0. Evidence drops at `backend/.perf-runs/price-history-{PASSED,FAILED}-<iso8601>.json`. The script auto-generates a part-id pool from the top 500 parts by observation count — this requires `populate_sample_data` to have seeded enough rows. If the pool is too small, the script logs and exits with a clear error; not a flake.

### Compliance audit (T04)

Reference: `backend/app/crawlers/compliance_audit.py`. Run from backend/ as `python -m app.crawlers.compliance_audit`. Expected stdout:

```
M002/S03 adapter compliance audit
T0 (http): 83/83 compliant
T1 (tls): 15/15 compliant
T2 (browser): 10/10 compliant
Total: 108/108 compliant
OK — every adapter declares at least one category_targets entry
```

Exit 0. The 108 (not 111) figure is canonical per MEM037 / MEM122 — the IS_FALLBACK GenericHtmlParser instances per tier are excluded from ADAPTER_REGISTRY by `__init_subclass__`. The roadmap and the milestone vision both say "111" — that's documented drift, not a regression. Test fixtures throughout (S04/S11) hardcode 108.

### Backfill kickoff (T05)

Reference: `backend/app/crawlers/backfill.py`. CLI: `python -m app.crawlers.backfill --batch-size 100 --limit 100 --max-failure-rate 0.5`. Requires same env as crawler runner (CRAWLER_USER_ID, CRAWLER_DEFAULT_CATEGORY_NAME). Cursor lands at `backend/.crawler-state/backfill_cursor.json`. R005's gate is "started" (not complete). After the run:
- INFO log line per batch: `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns`
- Cursor file persists for resume
- Hit `/api/admin/extraction-health` → coverage block should show parts_with_specs > 0 if the run touched a part with universal-extractor output

If the backfill produces specifications-populated parts, /admin/extraction-health's per-tier coverage gradient will reflect it. That's the cross-cut with R006.

### Final test gauntlet (T06)

| Suite | Command | Expected | Notes |
|---|---|---|---|
| Backend full | `cd backend && TESTING=true pytest -n auto --rootdir=. -q --no-cov` | exit 0, all passing | Per CLAUDE.md "always pass -n auto"; SQLite in-memory, no Postgres needed for tests. |
| Backend OpenAPI snapshot | (included above) | exit 0 | Verifies T03 regenerated the snapshot correctly. |
| Frontend type-check | `cd frontend && npm run type-check` | exit 0 | tsc -b --noEmit. |
| Frontend unit | `cd frontend && npm test -- --run` | exit 0, ~597 tests | MEM128 noise on e2e/*.spec.ts collection — confirm S12's vitest.config.ts fix still applied. |
| Frontend e2e | `cd frontend && npm run test:e2e` | exit 0, ~35 passing / ~10 skipped | All 7 spec files green at mobile/tablet/desktop. |
| Frontend lint | `cd frontend && npm run lint` | exit 1, 108 errors | MEM062 baseline; not a regression. Document explicitly in M002-VALIDATION.md. |
| Compliance audit | `cd backend && python -m app.crawlers.compliance_audit` | exit 0, 108/108 | T04's gate. |
| Perf gate | `bash backend/scripts/perf/run_price_history_loadtest.sh` | exit 0, PASSED.json drops | T02's gate. |

### Verification checklist mapping (slice plan demo statement)

The slice plan's "After this:" demo statement breaks down as 6 falsifiable checks. Map each to an evidence file:

| Demo line | Evidence | Task |
|---|---|---|
| Pick a real coilover product URL. Run a live scrape. | Adapter run log excerpt + crawled_pages row | T01 |
| Observe in logs: universal extraction → category extraction → Pydantic validation → ingest → Part.specifications populated. | Server log excerpt with the four log lines | T01 |
| Visit /parts and find the part — sparkline renders. | Screenshot /parts | T01 |
| Click into detail view — retailer breakdowns visible. | Screenshot /parts/:id | T01 |
| Subscribe with threshold above current price; trigger observation; email arrives. | Screenshot /parts/:id (subscribe dialog), screenshot /account/alerts, screenshot inbox email | T01 |
| Confirm backfill job running (admin extraction-health shows progress). | Screenshot /admin/extraction-health + console output of backfill run | T05 |
| Re-run S05 load test — p95 still inside budget. | PASSED.json dump | T02 |

## Pitfalls / Don't Hand-Roll

- **Don't write a new e2e Playwright spec for the live flow.** The slice-plan boundary-map says "E2E Playwright spec exercising the full live flow" but the existing 7 e2e spec files already cover the priority surfaces with mocked APIs at three viewports. A "live flow" Playwright spec would require live SES credentials in CI which is wrong. The S13 demo gate is operator-driven UAT, not Playwright. Treat the boundary-map line as aspirational; the live UAT artifact (S13-UAT.md + uat-evidence/) is the deliverable.
- **Don't manually edit REQUIREMENTS.md or DECISIONS.md.** Use `gsd_requirement_update` and `gsd_save_decision` — the tools regenerate the markdown from DB. Direct edits get clobbered next render.
- **Don't `cd` to project root from the worktree.** Working dir is `/home/tyler-webb/Documents/Github/CarModPicker/.gsd/worktrees/M002`. All commands operate relative.
- **Don't run pytest without TESTING=true** when the backend/app.crawlers package is in the call graph (MEM008) — boto3 head_bucket fires at import.
- **Don't run pytest from project root with a partial path** — many subagents have surfaced "no tests collected" when the path is wrong (MEM058 for OpenAPI snapshot).
- **Don't bypass the compliance_audit script and assert "111/111"** — the live count is 108. MEM037 / MEM122 are explicit; fixtures are 108-shaped.
- **Don't retry the perf gate on FAIL.** FAILED.json's remediation string is "Open R036 (materialized part_price_summary) per D004." Auto-mode must checkpoint; manual decision required.
- **Don't try to bring up Docker from auto-mode.** It's not bash-runnable in this harness reliably. Operator must do it; checkpoint and ask.
- **Don't migrate ViewPart's PriceHistoryLineChart in isolation.** It and the S06 "Price summary (90 days)" block both render on /parts/:id today. Confirm with the user first whether to delete the legacy chart entirely (T03 path (a)) or refactor it to the new shape (path (b)). Asking-once is cheaper than reverting.
- **Don't trust that the legacy=true shim has zero out-of-band callers.** Grep `chrome-extension/` first; the Chrome extension scrapes are a separate consumer.
- **Don't promote R019 to validated without a fresh PASSED.json on disk.** S05 explicitly leaves R019 active pending the live run; that's S13's bar.

## Sources

- `.gsd/REQUIREMENTS.md` — R002, R003, R005, R006, R008, R009, R010, R016, R017, R018, R019, R020 still `active`; S13 is the validation gate for most.
- `.gsd/milestones/M002/M002-CONTEXT.md` § "Final Integrated Acceptance" — six concrete checks that constitute milestone close.
- `.gsd/milestones/M002/M002-ROADMAP.md` § S13 demo statement + boundary-map S13 inputs.
- `.gsd/milestones/M002/slices/S05/S05-SUMMARY.md` § Follow-ups — explicit "S13 audits all callers of GET /api/parts/{id}/price-history and removes the legacy=true shim" + "Manual perf-gate run before S13 milestone close."
- `.gsd/milestones/M002/slices/S07/S07-SUMMARY.md` § Known Limitations — "Live SES email send … is deferred to S13."
- `.gsd/milestones/M002/slices/S04/S04-SUMMARY.md` § Known Limitations — "Live-runtime backfill verification deferred to S13 final integration verification."
- `.gsd/milestones/M002/slices/S11/S11-SUMMARY.md` § Follow-ups — "S13: final integration verification — exercise live scrape → extraction → ingest → /admin/extraction-health visibility in a real backend scenario."
- `.gsd/milestones/M002/slices/S12/S12-SUMMARY.md` § What S13 inherits — "S13 only needs the live full-stack milestone-validation pass."
- `backend/scripts/perf/README.md` — perf-gate runbook.
- `backend/app/crawlers/compliance_audit.py` — audit script entrypoint.
- `backend/app/crawlers/backfill.py` — backfill CLI.
- `backend/app/api/endpoints/parts.py:1185+` — legacy=true shim location.
- `frontend/src/pages/builder/ViewPart.tsx:82` — sole legacy-shim caller in the frontend.

## Related Memory

| Memory | Why relevant |
|---|---|
| MEM037 | "111 adapters" in roadmap, 108 in registry (canonical for S13) |
| MEM122 | Backend extraction-health contract is 108/108 not 111/111 |
| MEM006 | Visual-regression strategy: Playwright at 3 breakpoints + manual UAT for ~17 ripple pages — S13 owns the "smoke ~17 pages manually" carry-forward from S12 |
| MEM008 | TESTING=true required for any python -c against app.crawlers.* |
| MEM058 / MEM088 | OpenAPI snapshot path is `backend/tests/test_openapi_snapshot.py` (no api/ segment); regenerate command |
| MEM044 | SQLAlchemy JSON null three-shape gotcha (relevant for backfill empty-specs filter that T05 will exercise) |
| MEM046 | Failure-rate sourced from DB not CloudWatch (relevant for /admin/extraction-health visual smoke) |
| MEM062 | Lint baseline = 108 errors (108 still after S12 — not a regression) |
| MEM097 / MEM102 | AccountAlerts useEffect self-cancel bug — carry forward, do not fix in S13 |
| MEM107 / MEM115 / MEM121 | Reskin scope discipline — confirms S12's interactive-vs-chrome split was correct; nothing for S13 to revisit |
| MEM128 / MEM129 | vitest e2e collection noise — confirm S12's fix still applied during T06 |

## Skills Discovered

None installed. The work touches:
- FastAPI/SQLAlchemy/pytest (already covered by existing CLAUDE.md context)
- Playwright (already covered by S08–S12 patterns)
- Locust (in-house perf-gate harness — locked in S05)
- AWS SES (in-house email path — wired in M001)

No new framework introduced; no skill install warranted.
