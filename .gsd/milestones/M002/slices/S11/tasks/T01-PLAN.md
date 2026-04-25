---
estimated_steps: 3
estimated_files: 2
skills_used: []
---

# T01: Add typed admin extraction-health API client

Extend `frontend/src/api/admin.ts` with `getExtractionHealth()` returning a typed `ExtractionHealthResponse` whose shape exactly mirrors the backend Pydantic model in `backend/app/api/endpoints/admin/extraction_health.py` (`ComplianceBlock`, `CoverageBlock` with `per_tier: Record<'http'|'tls'|'browser', CoverageTierBlock>`, `FailureRateRow[]`, `WindowMeta`). Also export the supporting interfaces so the page component can import them. Add a vitest unit test in `frontend/src/api/admin.test.ts` covering the new function: hits `GET /admin/extraction-health` and resolves with the typed response (use the existing axios-mock pattern already in that file).

This task is purely additive — do not touch existing exports. Do not import the `Part` type or any non-admin types. Mirror `getTableCounts()` style: thin axios call returning the typed response.

No failure modes / load profile / negative tests block here — the function is a 1-line wrapper; coverage is satisfied by the happy-path unit test plus the e2e mock in T04.

## Inputs

- ``frontend/src/api/admin.ts``
- ``frontend/src/api/admin.test.ts``
- ``backend/app/api/endpoints/admin/extraction_health.py``

## Expected Output

- ``frontend/src/api/admin.ts``
- ``frontend/src/api/admin.test.ts``

## Verification

cd frontend && npm test -- --run admin.test.ts && npm run type-check
