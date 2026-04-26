---
id: T01
parent: S11
milestone: M002
key_files:
  - frontend/src/api/admin.ts
  - frontend/src/api/admin.test.ts
key_decisions:
  - Typed `ComplianceBlock.per_tier` and `CoverageBlock.per_tier` keys as the literal union `'http' | 'tls' | 'browser'` (matching backend `_TIER_KEYS`) for compile-time tier exhaustiveness in the consuming page; left `per_field` keys as `Record<string, number>` since UNIVERSAL_FIELD_NAMES is a runtime frozenset that may evolve.
  - Used the path `/admin/extraction-health` (no trailing slash) per explicit task plan wording; backend handler is mounted at `/admin/extraction-health/` via prefix + `/` route, FastAPI resolves the no-slash form by redirect — same as other admin endpoints already in this client.
duration: 
verification_result: passed
completed_at: 2026-04-26T00:05:54.537Z
blocker_discovered: false
---

# T01: Add typed adminApi.getExtractionHealth() client + unit test mirroring backend ExtractionHealthResponse

**Add typed adminApi.getExtractionHealth() client + unit test mirroring backend ExtractionHealthResponse**

## What Happened

Extended `frontend/src/api/admin.ts` with a typed `getExtractionHealth()` method and the supporting interfaces (`ComplianceBlock`, `CoverageBlock`, `CoverageTierBlock`, `FailureRateRow`, `WindowMeta`, `ExtractionHealthResponse`) whose shapes exactly mirror the Pydantic models in `backend/app/api/endpoints/admin/extraction_health.py`. The interfaces are exported so the page component (T03) can import them directly. Tier keys on `CoverageBlock.per_tier` and `ComplianceBlock.per_tier` are typed as the literal union `'http' | 'tls' | 'browser'` — the backend uses the same `_TIER_KEYS` tuple — while `CoverageTierBlock.per_field` is `Record<string, number>` because the field names come from `UNIVERSAL_FIELD_NAMES` and may evolve.\n\nThe call style (`apiClient.get<ExtractionHealthResponse>('/admin/extraction-health')`) follows the existing thin-wrapper pattern of `getTableCounts()`, `getCrawlBucketSummary()`, etc. The path is `/admin/extraction-health` (no trailing slash) per the explicit task plan and the slice S11 goal — FastAPI resolves this against the backend's `prefix="/admin/extraction-health"` + `@router.get("/")` mount via redirect (same pattern other admin routers use).\n\nAdded one happy-path vitest in `frontend/src/api/admin.test.ts` under a new `describe('adminApi — extraction health')` block, using the existing shared `apiClient` mock from `setup.ts` (no per-file `vi.mock` needed). The test asserts the URL, the full payload round-trip, and exercises the nested type structure: `compliance.compliant`, `coverage.per_tier.http.per_field['brand']`, `failure_rate_7d[0].rate`, `window.days`. The fixture also implicitly verifies MEM037's canonical 108/108 compliance shape and MEM046/D009's tier classification on `FailureRateRow.tier`.\n\nThis task is purely additive — no existing exports were modified, no `Part` or non-admin types imported. Coverage for failure modes / load profile / negative tests is deferred to T04's e2e mock per the task plan.

## Verification

Ran the slice-defined verification commands from the working directory:\n\n1. `cd frontend && npm test -- --run admin.test.ts` — 3 admin test files (api/admin.test.ts, pages/admin/AdminDashboard.test.tsx, pages/admin/CrawlerAdmin.test.tsx), 58 tests total, all green. The pinpoint run `npm test -- --run src/api/admin.test.ts` shows 38 tests passing in the api module specifically (37 prior + 1 new for `getExtractionHealth`).\n2. `npm run type-check` (`tsc -b --noEmit`) — clean exit, no errors. The new exported interfaces (`ExtractionHealthResponse`, `ComplianceBlock`, `CoverageBlock`, `CoverageTierBlock`, `FailureRateRow`, `WindowMeta`) compile under `exactOptionalPropertyTypes: true` and the `'http' | 'tls' | 'browser'` literal-union tier keys round-trip through the test fixture without TS2345.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm test -- --run admin.test.ts` | 0 | ✅ pass | 1260ms |
| 2 | `cd frontend && npm test -- --run src/api/admin.test.ts` | 0 | ✅ pass | 545ms |
| 3 | `cd frontend && npm run type-check` | 0 | ✅ pass | 4000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/api/admin.ts`
- `frontend/src/api/admin.test.ts`
