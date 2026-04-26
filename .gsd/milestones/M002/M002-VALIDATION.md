---
verdict: pass
remediation_round: 0
---

# Milestone Validation: M002

## Success Criteria Checklist
## M002 Success Criteria — Final Checklist (2026-04-25)

The roadmap's nine success criteria evaluated against shipped, audited evidence. The vision text says "111 adapters" — reconciled to canonical 108/108 contract per MEM037/MEM122 (the 3-adapter delta is IS_FALLBACK GenericHtmlParser instances per tier excluded from the registry per D-03). Compliance is binary; coverage is gradient.

- [x] **All 111 adapters compliant with new extraction pattern** — RECONCILED to 108/108 (canonical). M002/S13/T04 live audit: T0 (http) 83/83, T1 (tls) 15/15, T2 (browser) 10/10. Evidence: `.gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt`. Vision text 111 vs canonical 108 reconciled per MEM037/MEM122.
- [x] **30–50 of T0+T1 adapters surface meaningful structured fields where HTML cooperates** — Coverage gradient surfaces in `GET /api/admin/extraction-health` `coverage.per_tier.{http,tls}.parts_with_specs` and `field_presence_heatmap`. M002/S13/T05 backfill run repopulated 97/100 specs (0 failures) on the live local stack. Evidence: `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-post-backfill.json`.
- [x] **Every part card with observations shows sparkline + price-delta line; per-part detail view shows retailer breakdowns + listing-level history** — M002/S06 shipped Sparkline.tsx + PriceDeltaLine.tsx; M002/S10 reskinned PartsCatalog onto the new design system preserving the surface. Playwright e2e price-history.spec.ts:480 (sparklines + delta) and price-history.spec.ts:533 (retailer breakdown + stale caveat) green at mobile/tablet/desktop. Evidence: refreshed `frontend/e2e/price-history.spec.ts-snapshots/` baselines + M002/S13/T01 live UAT walkthrough.
- [x] **Price-drop alerts subscription works end-to-end with email firing on threshold breach** — M002/S07 shipped CRUD endpoints + Alembic migration + observation-write-path evaluator + SES React Email template + /account/alerts management page + unsubscribe-token redirect. Verified live at M002/S13/T01: subscribe → trigger observation below threshold → SES email arrives at `tylert2610+m002-uat@gmail.com` → click unsubscribe → 302 → row removed. Backend logs: `price_alert_evaluated: verdict=fired`, `price_alert_email_sent: success=true`. Evidence: T01 extraction-and-alert.log + price-alerts.spec.ts-snapshots/ green at 3 viewports.
- [x] **shadcn primitives committed under components/ui/ replace hand-rolled components/common/ across all ~20 pages** — M002/S08 shipped 9+ primitives (button, dialog, dropdown-menu, combobox, toast, tabs, input, select, sheet) plus card/alert/spinner/pagination in S11. M002/S09–S11 reskinned priority pages; M002/S12 swept Tier A (statics+auth), Tier C1 (Profile/Home/Search/AccountAlerts/UserCard/ViewBuildLog), Tier C2 (9 builder/parts/buildLists pages + 21 inner components), and Tier D admin pages, then deleted `components/common/` and `components/buttons/` directories with three-layer enforcement (vitest grep-guard, ESLint no-restricted-imports, physical deletion). Evidence: gauntlet vitest 594 passed (includes no-legacy-primitives.test.ts) + `test ! -d frontend/src/components/{common,buttons}` returns 0.
- [x] **Playwright screenshot tests green at three breakpoints for kitchen-sink + build-list + parts catalog + admin** — M002/S13/T06 refreshed 24 stale visual baselines that drifted between S08 and S12 (kitchen-sink ui/* additions + reskin ripple per MEM113/MEM115); subsequent stability run returned 35 passed / 10 skipped at mobile/tablet/desktop. Evidence: gauntlet-evidence.json item #4.
- [x] **Re-extraction backfill against S3 self-archive started (idempotent, resumable, can finish post-merge)** — M002/S04 shipped `backend/app/crawlers/backfill.py`. M002/S13/T05 ran live: dry-run + 100-part real run both green (97/100 repopulated, 0 failures), per-batch logging, cursor checkpoint at `backend/.crawler-state/backfill_cursor.json` for operator --resume. R005 contract is 'started, not complete' — long-tail completion post-merge. Evidence: `.gsd/milestones/M002/slices/S13/uat-evidence/backfill-run.log` + `backfill-cursor-snapshot.json`.
- [x] **Price-history list-endpoint p95 inside budget at 10× current traffic in load test** — M002/S05 shipped perf gate infrastructure (locustfile + parser + run script with deterministic exit-code contract). M002/S13/T02 re-ran the gate against the live stack at 10× config (50 users, 10 spawn-rate, 60s) on 2026-04-26 UTC: PASSED with GET p95=95ms (budget <200ms), POST p95=130ms (budget <500ms), 0 failures across 1893 requests. R036 (materialized part_price_summary) precondition not met — stays deferred per D004. Evidence: `.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json`.
- [x] **Admin extraction-health view distinguishes compliance (binary, 111/111) from coverage (per-tier gradient)** — M002/S04 shipped `GET /api/admin/extraction-health`; M002/S11 rebuilt the admin shell + extraction-health UI on the new design system. Live JSON contract verified at M002/S13/T04: `compliance.compliant=108, compliance.total=108, per_tier {http:'83/83', tls:'15/15', browser:'10/10'}`, `coverage.per_tier` with field-presence heatmap, `failure_rate_7d` rolling-7d window. Compliance binary, coverage gradient as designed. RECONCILED to 108 canonical per MEM037/MEM122. Evidence: `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json`.

## Slice Delivery Audit
## Slice Delivery Audit S01–S13

Each slice's claimed contract vs. shipped evidence. All 13 slices delivered the boundary contract documented in `M002-ROADMAP.md`.

- **S01 — SpecRegistry + base CategorySpec + 3 initial models + ingest validation hook**: SHIPPED. `backend/app/crawlers/specs/{registry,base,coilover,brake,turbo,universal}.py`; ingest validates payload.specifications via SpecRegistry.resolve(); fail-soft on Pydantic ValidationError (drops spec block, logs WARN, emits ExtractionFailureRate EMF, part still persists). 23 contract+integration tests green; full crawler suite 1284 passed at slice close.
- **S02 — Universal-field extractor + RetailerCrawlerAdapter post-hook + suppression mechanism**: SHIPPED. `backend/app/crawlers/parsing.py` extensions for weight/material/finish/warranty/fitment_notes (each returning value + confidence); base-class post-hook auto-merges into ScrapedPayload.specifications; per-adapter suppression via class attribute. Bridge `category_bridge.py` maps DB category names → SpecRegistry sub-slugs (parent-aware, MEM022).
- **S03 — All 108 adapters declare category_targets + compliance_audit script**: SHIPPED. `backend/app/crawlers/compliance_audit.py` (script-as-test, exit 0 on 108/108) + `category_targets` ClassVar on every T0/T1/T2 adapter, validated at import time against default_registry. Per-tier breakdown 83/15/10 (canonical 108 per MEM037/MEM122; vision '111' references IS_FALLBACK GenericHtmlParser instances excluded per D-03).
- **S04 — Idempotent resumable backfill + admin extraction-health endpoint + EMF metric**: SHIPPED. `backend/app/crawlers/backfill.py` (chunked, idempotent via empty-specs filter, resumable via cursor JSON), `backend/app/api/endpoints/admin/extraction_health.py` (compliance + coverage + 7d failure rates with dialect-aware JSON-extract per MEM047), CloudWatch EMF `extraction_failure_rate` per adapter (env-gated, fail-soft per MEM015).
- **S05 — Price-history aggregation API + perf gate infra**: SHIPPED. `GET /api/parts/{id}/price-history` (windowed, retailer-filterable; legacy=true shim later removed in S13/T03), `POST /api/parts/price-history` (batch min/max/last/trend with link-group dedup), `part_price_aggregation_service` (canonical-coalesce expression). Perf gate: locustfile + CSV parser + run script with deterministic exit codes (0 PASS / 1 FAIL / 2 crash / 3-6 setup errors per MEM050/MEM053). 18 endpoint + 11 service tests green; Locust 2.43.4 added to backend/requirements.txt per MEM057.
- **S06 — Sparkline + PriceDeltaLine components + per-part detail view**: SHIPPED. `frontend/src/components/charts/Sparkline.tsx` (zero-/single-/multi-observation rendering), `PriceDeltaLine.tsx`, ViewPart 'Price summary (90 days)' block with retailer breakdowns (≤3 list / >3 Tabs) and 60d stale caveat. 26 vitest cases green.
- **S07 — Price-drop alerts + SES email path + subscription-management UI**: SHIPPED. `part_price_alert.py` model + Alembic migration + CRUD endpoints + observation-write-path evaluator + React Email template (`backend/app/core/email_templates/price_drop_alert.html`) + `/account/alerts` page + unsubscribe-token redirect. Live SES UAT deferred to S13/T01 — completed at M002 close.
- **S08 — Design-system substrate: tokens + 9 primitives + kitchen-sink + Playwright config**: SHIPPED. `frontend/src/styles/tokens.css` (CSS-variable HSL channels via Tailwind v4 @theme bridge), 9 primitives under `components/ui/`, KitchenSink page rendering every state, `playwright.config.ts` with mobile/tablet/desktop projects (all chromium per MEM066/MEM068), `components.spec.ts` toHaveScreenshot at 0.2% pixel-diff threshold per R013.
- **S09 — /build-lists/{id} reskinned**: SHIPPED. Page on new design system; build-list.spec.ts visual regression + edit-dialog focus/Escape + tab-order keyboard tests at all 3 viewports. R014 promoted at S13/T06.
- **S10 — /parts catalog reskinned with sparkline integration**: SHIPPED. PartsCatalog onto ui/* primitives; parts-catalog.spec.ts visual regression + add-to-build-list dialog focus + tab-traversal keyboard tests at all 3 viewports. R015 promoted at S13/T06.
- **S11 — /admin shell + ExtractionHealth view reskinned**: SHIPPED. AdminDashboard reskinned + ExtractionHealth admin page rendering compliance + per-tier coverage gradient + per-adapter failure rates over 7d window. admin.spec.ts dashboard + extraction-health visual regressions at 3 viewports. Card/Alert/Spinner/Pagination primitives added.
- **S12 — Sweep all ~17 remaining pages + retire components/common/**: SHIPPED. Tier A (14 statics + auth + GoogleAuthFlow), Tier C1 (Profile/Home/Search/AccountAlerts/UserCard/ViewBuildLog), Tier C2 (9 builder/parts/buildLists + 21 inner components), Tier D (admin) all migrated. Three-layer R017 enforcement: vitest grep-guard, ESLint no-restricted-imports, physical deletion of `components/common/` + `components/buttons/`.
- **S13 — Live full-stack UAT + perf-gate re-run + legacy-shim removal + milestone close**: SHIPPED. T01 live extraction → ingest → /parts sparkline → /parts/:id breakdown → SES alert email → unsubscribe (operator-driven). T02 perf gate re-run PASSED at 10×. T03 removed legacy=true shim + PriceHistoryLineChart (only code increment owed by S13). T04 live compliance audit (108/108) + admin extraction-health JSON capture. T05 backfill kicked off (started, not complete). T06 final gauntlet, requirement promotion, milestone validation.

## Cross-Slice Integration
## Cross-Slice Integration

The full M002 loop was exercised end-to-end at S13/T01 against a live local stack (Postgres 16 via docker-compose, uvicorn :8000, vite :4000, AWS SES). One real product URL flowed through:

1. **Live scrape** → adapter `parse_product_page()` returns ScrapedPayload with raw structured fields
2. **Universal extraction (S02)** → base-class post-hook merges weight/material/finish/warranty/fitment_notes into payload.specifications
3. **Category bridge (S02 MEM022)** → resolves DB category name to SpecRegistry sub-slug (parent-aware: 'suspension'+coilover-keyword → 'coilover')
4. **Pydantic validation (S01)** → SpecRegistry.resolve() returns CategorySpec; model_validate succeeds; payload.specifications stays populated. Fail-soft branch (MEM015) drops invalid spec blocks without crashing ingest
5. **Ingest** → Part row created/updated with specifications populated; structured log `ingest_payload: parse_status=parsed_ok`
6. **/parts sparkline (S06+S10)** → PartsCatalog renders Sparkline + PriceDeltaLine for the part; click-through navigates to /parts/:id
7. **/parts/:id detail (S06)** → 'Price summary (90 days)' block shows retailer breakdown (Tabs >3 retailers, flat list ≤3); 60d stale caveats applied where applicable
8. **Subscribe (S07)** → /account/alerts subscribe form posts to part-price-alerts CRUD endpoint with threshold above current price
9. **Trigger observation** → observation injected below threshold; observation-write-path evaluator fires; structured log `price_alert_evaluated: alert_id=... verdict=fired`
10. **SES email path (S07)** → React Email HTML rendered; SES send via IAM role; structured log `price_alert_email_sent: alert_id=... success=true`. Operator confirms email arrives at `tylert2610+m002-uat@gmail.com` fixture inbox
11. **Unsubscribe** → operator clicks unsubscribe link → 302 redirect → /account/alerts?status=success → row removed
12. **Backfill verification (S04)** → S13/T05 confirmed admin extraction-health endpoint reports the canonical 108/108 contract + post-backfill coverage delta; backfill cursor written for operator --resume

No cross-slice integration gaps surfaced. The S05 legacy=true price-history query-param shim — the only code-debt item carved out at S05 close — was removed cleanly at S13/T03 with OpenAPI snapshot regenerated and all consumers (frontend ViewPart.tsx + parts.ts + Chrome extension) confirmed clean. Backend tests green. Frontend type-check + vitest + lint at MEM062 baseline.

The 24 visual-regression baselines that drifted between S08 and S12 (per MEM113/MEM115 reskin ripple) were refreshed at S13/T06 as expected slice-close work, not as a remediation gate. Three-viewport e2e suite returns 35 passed / 10 skipped against the refreshed baselines.

## Requirement Coverage
## Requirement Coverage

**20 of 20 in-scope M002 requirements promoted to validated.** No active requirements remain in M002 scope. Deferred / out-of-scope requirements (R030–R047) are intentionally beyond M002 — LLM-based extraction (M003), light theme (R035), materialized part_price_summary (R036, conditional on R019 perf miss — precondition not met), Cloudflare bypass for T2 adapters (R034), and infrastructure follow-ups (R040–R046).

### Promoted at M002/S13/T06 (12 + R014/R015 cross-checked)

| ID | Class | Validation source |
|----|-------|-------------------|
| R002 | core-capability | S02 universal extractor + S13/T01 live extraction logs + S13/T04 compliance audit |
| R003 | core-capability | S03 compliance audit (108/108 canonical per MEM037/MEM122) + S13/T04 live verification |
| R005 | operability | S04 backfill CLI + S13/T05 live run (dry-run + 100-part real run, 97/100 specs repopulated, cursor written) |
| R006 | admin/support | S04 admin extraction-health endpoint + S11 reskinned UI + S13/T04 live JSON contract dump |
| R008 | primary-user-loop | S06 Sparkline + PriceDeltaLine + S10 PartsCatalog integration + S13/T06 baselines green at 3 viewports |
| R009 | primary-user-loop | S06 detail view + retailer breakdown + 60d caveat + S13/T06 baselines green at 3 viewports |
| R010 | primary-user-loop | S07 alerts CRUD + SES + unsubscribe + S13/T01 live SES round-trip + S13/T06 baselines green |
| R014 | primary-user-loop | S09 /build-lists/{id} reskin + S13/T06 build-list e2e green (visual + dialog focus + tab-order) at 3 viewports |
| R015 | primary-user-loop | S10 /parts catalog reskin + S13/T06 parts-catalog e2e green at 3 viewports |
| R016 | admin/support | S11 admin shell + ExtractionHealth + S13/T06 admin e2e green at 3 viewports |
| R017 | quality-attribute | S12 components/common+buttons retirement with three-layer enforcement (grep-guard + ESLint + physical deletion) |
| R018 | quality-attribute | Crawler test suite green: gauntlet pytest 2800 passed / 15 skipped / 0 failed |
| R019 | quality-attribute | S13/T02 perf gate re-run PASSED at 10× (GET p95=95ms, POST p95=130ms, 0 failures across 1893 requests) |
| R020 | quality-attribute | S09/S10/S11 keyboard specs (tab order, focus, Escape on dialogs) + Radix focus-trap baseline + S13/T06 e2e green |

### Already validated at slice close

| ID | Validated at | Reason |
|----|--------------|--------|
| R001 | M002/S01 | SpecRegistry + base CategorySpec + 3 concrete models + 23 contract+integration tests |
| R004 | M002/S01 | Fail-soft ingest validation: drops spec block, logs WARN, emits EMF, part persists. 3 integration tests + caplog assertions |
| R007 | M002/S05 | GET/POST price-history endpoints + aggregation service + 18 endpoint + 11 service tests |
| R011 | M002/S08 | tokens.css full shadcn vocabulary + Tailwind v4 @theme bridge |
| R012 | M002/S08 | 9 ui/* primitives committed (button/input/select/tabs/combobox/dialog/dropdown-menu/sheet/toast) |
| R013 | M002/S08 | components.spec.ts kitchen-sink toHaveScreenshot at 3 viewports with 0.2% pixel-diff threshold |

### Deferred / out-of-scope (not in M002 contract)

R030–R033 (LLM extractor + suggestions + summarization), R034 (T2 Cloudflare bypass), R035 (light theme), R036 (materialized part_price_summary — precondition not met since R019 PASSED), R040–R047 (OpenTelemetry, async SQLAlchemy, read replicas, Redis cache, embedding-based disambiguation, version_id_col CC, canary runs, user-facing announcement). All correctly classified per the original M002 PRD.

## Verification Class Compliance
## Verification Classes

S07's live SES UAT was deferred to S13/T01 by design — the slice plan explicitly carved this out as the milestone-close demo statement, not a slice-internal verification. Round-trip subscribe → trigger observation → SES email arrives → unsubscribe was completed by the operator at S13/T01 with the redacted-recipient `tylert2610+m002-uat@gmail.com` fixture inbox per the slice plan's redaction constraints.

S05's perf gate at 10× live traffic was deferred to S13/T02 by design — S05 shipped the perf-gate infrastructure (locustfile + parser + run script with deterministic exit codes per MEM050/MEM053); the live 10× run against a live uvicorn was R019's concern. Completed S13/T02 with PASSED verdict on first re-run.

R005 backfill 'started, not complete' contract — long-tail completion is post-merge using the committed cursor snapshot. The cursor at `backend/.crawler-state/backfill_cursor.json` records `last_processed_part_id=019daecf-5841-7b5f-80d1-4308c375acbd` so an operator can `python -m app.crawlers.backfill --resume` to finish the run.

24 visual-regression baselines drifted between S08 and S12 due to the design-system reskin ripple (per MEM113/MEM115 — every page that was screenshot before the reskin needs a baseline refresh). S13/T06 refreshed all 24 PNGs as expected slice-close work.


## Verdict Rationale
M002 ships clean. Live UAT exercised the full extraction → ingest → UI → alert email loop end-to-end against a live local stack with real SES send + unsubscribe round-trip; perf gate met R019 budget at 10× on first re-run (no R036 precondition); all S08–S12 design-system surfaces verified at 3 viewports after S13/T06 refreshed 24 baselines that drifted from the reskin ripple per MEM113/MEM115 (expected slice-close work, not a remediation gate); 108-adapter compliance held against the live stack; backfill kicked off with cursor checkpoint for operator --resume; 20 of 20 in-scope requirements validated; final gauntlet returned 6 of 6 commands at the M002 close-gate verdicts (5 pass + 1 lint at MEM062 baseline with zero new errors in S13-touched files).
