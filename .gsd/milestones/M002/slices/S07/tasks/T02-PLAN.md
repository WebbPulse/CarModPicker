---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Implement part_price_alerts CRUD service + endpoints (subscribe / list-mine / update / delete)

Implement the full user-facing CRUD surface for price alerts as a hand-rolled router (NOT BaseEndpointRouter — the surface is intentionally narrower: scoped to current_user, no admin paths, no list-all). Route file: `backend/app/api/endpoints/part_price_alerts.py`. Register in main.py via `endpoint_registry.register_endpoint(part_price_alerts.router, prefix='/part-price-alerts', tags=['part-price-alerts'], description='Per-user price-drop alerts')`. Service file: `backend/app/api/services/part_price_alert_service.py` exposing pure functions (mirror part_listing_service.py style — module functions, not a class): `create_or_update_alert(db, user_id, part_id, threshold_cents) -> PartPriceAlert` (upsert on the unique constraint: if a row exists for this (user_id, part_id) and active=True, update threshold; if exists and active=False, set active=True and update threshold; else insert), `list_active_alerts_for_user(db, user_id) -> list[PartPriceAlert]`, `deactivate_alert(db, alert_id, user_id) -> bool` (returns False if alert doesn't exist or doesn't belong to user — endpoint maps to 404). Endpoints (all require get_current_user): POST `/` body=PartPriceAlertCreate → 201 PartPriceAlertRead (also verifies the part_id exists, 404 if not); GET `/me` → list[PartPriceAlertRead] (active=True only); PATCH `/{alert_id}` body=PartPriceAlertUpdate → PartPriceAlertRead (404 if not owner); DELETE `/{alert_id}` → 204 (404 if not owner — soft-delete by setting active=False). Tests: `backend/tests/api/endpoints/test_part_price_alerts.py` with cases for: anon → 401, create new alert, re-subscribe updates threshold (idempotent), list-mine returns only the current user's alerts (cross-user isolation), patch threshold, delete sets active=False, delete by non-owner → 404, threshold_cents must be ge=0 → 422, unknown part_id → 404. Use the existing `client` fixture from conftest.py and the `auth_headers` pattern from test_users.py for authenticated requests.

## Inputs

- ``backend/app/api/models/part_price_alert.py``
- ``backend/app/api/schemas/part_price_alert.py``
- ``backend/app/api/dependencies/auth.py``
- ``backend/app/api/endpoints/bug_reports.py``
- ``backend/app/api/services/part_listing_service.py``
- ``backend/app/api/utils/response_patterns.py``
- ``backend/app/main.py``
- ``backend/tests/api/endpoints/test_users.py``

## Expected Output

- ``backend/app/api/endpoints/part_price_alerts.py``
- ``backend/app/api/services/part_price_alert_service.py``
- ``backend/app/main.py``
- ``backend/tests/api/endpoints/test_part_price_alerts.py``

## Verification

TESTING=true pytest backend/tests/api/endpoints/test_part_price_alerts.py -n auto --rootdir=backend -q --no-cov
