---
id: T02
parent: S07
milestone: M002
key_files:
  - backend/app/api/endpoints/part_price_alerts.py
  - backend/app/api/services/part_price_alert_service.py
  - backend/app/main.py
  - backend/tests/api/endpoints/test_part_price_alerts.py
  - backend/tests/fixtures/openapi_snapshot.json
key_decisions:
  - Service exposes module-level functions (mirrors part_listing_service.py), not a class — matches the codebase's existing service style and avoids BaseCRUDService coupling that the narrower per-user surface doesn't need.
  - DELETE path filters to active=True in the service-layer lookup so a double-DELETE returns 404 (not silently 204) — makes the soft-delete contract honest. The plan said 'delete by non-owner → 404' but didn't constrain double-delete; chose 404 for symmetry with non-owner.
  - Endpoint POST verifies part_id existence with a SELECT before upsert and raises 404. Catches the unknown-part case explicitly rather than letting the FK fire later in the flush — gives a cleaner error envelope to the client.
  - Non-owner PATCH and DELETE return 404 (not 403) via a unified get_alert_for_owner lookup, matching the slice's privacy posture: don't leak alert-id existence to non-owners.
  - Regenerated tests/fixtures/openapi_snapshot.json — adding /part-price-alerts to main.py legitimately drifts the snapshot and the snapshot test was failing until regeneration.
duration: 
verification_result: passed
completed_at: 2026-04-25T22:26:25.661Z
blocker_discovered: false
---

# T02: Add per-user price-drop alert CRUD endpoints + service (subscribe / list-mine / patch / soft-delete)

**Add per-user price-drop alert CRUD endpoints + service (subscribe / list-mine / patch / soft-delete)**

## What Happened

Implemented the full user-facing CRUD surface for the S07 price-drop-alert loop, sitting on top of the model+schemas T01 already shipped.

Built three artifacts plus a registry edit:

1. `app/api/services/part_price_alert_service.py` — module-level functions (mirrors part_listing_service.py style; no class, no DI ceremony):
   - `create_or_update_alert(db, user_id, part_id, threshold_cents)` — upsert keyed on the (user_id, part_id) UNIQUE constraint; reactivates a soft-deleted row instead of inserting a duplicate, so the endpoint never has to catch IntegrityError.
   - `list_active_alerts_for_user(db, user_id)` — newest-first, active-only.
   - `get_alert_for_owner(db, alert_id, user_id)` — single-source-of-truth ownership lookup; used by PATCH to enforce 404-not-403 (don't leak existence to a non-owner).
   - `deactivate_alert(db, alert_id, user_id)` — filters on active=True so a double-DELETE returns 404 (not silently 204), making the endpoint contract honest.

2. `app/api/endpoints/part_price_alerts.py` — hand-rolled APIRouter (deliberately NOT BaseEndpointRouter — the surface is intentionally narrower: scoped to current_user, no admin paths, no list-all). All four routes require `get_current_user`. The POST verifies `part_id` exists (404 if not) BEFORE upsert; PATCH/DELETE go through the owner-lookup helper so non-owner attempts return 404 (not 403).

3. `app/main.py` — registered the router via `endpoint_registry.register_endpoint(... prefix='/part-price-alerts' ...)` exactly as the plan specified.

4. `tests/api/endpoints/test_part_price_alerts.py` — 17 cases covering every plan-listed contract: anon→401 (×4 routes), create-new, idempotent re-subscribe (only one row in DB after two POSTs), reactivate-soft-deleted-on-resubscribe, cross-user isolation on /me, /me excludes inactive, patch-threshold success + ge=0 → 422, patch-by-non-owner → 404, delete-soft (row stays, active=False), delete-by-non-owner → 404 (and original alert untouched), delete-unknown → 404, subscribe-with-unknown-part → 404, subscribe-negative-threshold → 422.

Pre-existing T01 verification failure (alembic upgrade head with exit 255): traced to the gate running alembic from the repo root where alembic.ini doesn't exist. From `backend/`, both `alembic upgrade head` and `alembic current` run cleanly (`9aa798d6107e (head)`). The migration itself is fine; this is a verification-gate-rooting issue not a code defect — left untouched here since this task is T02.

Captured patterns MEM087 (hand-rolled router pattern for narrow per-user surfaces) and MEM088 (OpenAPI snapshot regeneration command — adding any new endpoint drifts tests/fixtures/openapi_snapshot.json, regenerated as part of this task).

## Verification

Ran the plan's exact verification command from `backend/`: `pytest tests/api/endpoints/test_part_price_alerts.py -n auto --rootdir=. -q --no-cov` → 17/17 pass in 5.56s. Also re-ran with the OpenAPI snapshot test included after regenerating the snapshot (adding the new endpoint legitimately drifted it): 18/18 pass in 5.79s. Type-check via `pyright app/api/endpoints/part_price_alerts.py app/api/services/part_price_alert_service.py` → 0 errors / 0 warnings. The slice-level runtime-signal log requirements (`price_alert_evaluated`, `price_alert_email_sent`) are T03 concerns — this task only added the subscribe-time `part_price_alert_subscribed: alert_id=... user_id=... part_id=... threshold_cents=...` INFO log on the POST path. The /me inspection surface required by the slice's "Inspection surfaces" verification line is now live and exercised by the cross-user-isolation test.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest tests/api/endpoints/test_part_price_alerts.py -n auto --rootdir=. -q --no-cov` | 0 | ✅ pass | 5560ms |
| 2 | `pytest tests/test_openapi_snapshot.py tests/api/endpoints/test_part_price_alerts.py -n auto --rootdir=. -q --no-cov` | 0 | ✅ pass | 5790ms |
| 3 | `pyright app/api/endpoints/part_price_alerts.py app/api/services/part_price_alert_service.py` | 0 | ✅ pass | 3000ms |

## Deviations

None. Implemented exactly to the plan: 4 endpoints, 3 service functions, registered under /part-price-alerts, all 9 plan-listed test cases plus 8 extra coverage cases (auth-on-each-route, list-excludes-inactive, double-delete, etc.).

## Known Issues

Pre-existing T01 verification gate failure: `alembic upgrade head` and `alembic current` exit 255 because the gate runs them from the repo root where alembic.ini doesn't exist. Both commands succeed when run from `backend/`. Migration is functionally correct (`alembic current` reports `9aa798d6107e (head)`). This is a gate-rooting issue, not a code defect — flagging here for visibility but T02 doesn't own the fix.

## Files Created/Modified

- `backend/app/api/endpoints/part_price_alerts.py`
- `backend/app/api/services/part_price_alert_service.py`
- `backend/app/main.py`
- `backend/tests/api/endpoints/test_part_price_alerts.py`
- `backend/tests/fixtures/openapi_snapshot.json`
