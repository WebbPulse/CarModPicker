---
id: T03
parent: S07
milestone: M002
key_files:
  - backend/app/api/services/part_price_alert_service.py
  - backend/app/api/services/part_listing_service.py
  - backend/app/core/email.py
  - backend/app/core/email_templates/price_drop_alert.html
  - backend/app/api/endpoints/part_price_alerts.py
  - backend/tests/services/test_part_price_alert_evaluation.py
  - backend/tests/api/endpoints/test_part_price_alerts.py
  - backend/tests/fixtures/openapi_snapshot.json
key_decisions:
  - Evaluator's per-alert iteration is wrapped in try/except so one bad alert (DB write failure, email-template raise, etc.) cannot poison the price-write transaction. Logs WARNING with alert_id (UUID-only — no email or token leakage) and continues. Captured as MEM090.
  - Cross-service hook uses a function-local import (`from app.api.services.part_price_alert_service import evaluate_alerts_for_listing`) inside `create_or_update_listing_and_price` to avoid a circular import at module load. Same trick: the evaluator imports `app.core.email` lazily. Bonus — makes monkeypatching trivial in tests because the import resolves on every call (MEM091).
  - Public unsubscribe endpoint uses no auth dependency — the JWT IS the auth. Every failure path (decode error, wrong purpose, non-UUID sub, missing alert) funnels to the same `?status=error&message=Invalid+or+expired+link` redirect so we never reveal WHY decode failed. Idempotent (D010 + MEM092).
  - SES send-failure (returns False) leaves `last_fired_at` unchanged so the next observation retries — matches `send_verify_email` contract for failure semantics. Saved as decision D010.
  - Plan deviation: verification command referenced `tests/services/test_part_listing_service.py` which does not exist; the integration coverage that file would have provided is captured in `test_create_or_update_listing_and_price_invokes_evaluator` in the new `test_part_price_alert_evaluation.py`. All other plan-spec verification ran clean.
duration: 
verification_result: passed
completed_at: 2026-04-25T22:36:30.266Z
blocker_discovered: false
---

# T03: Wire alert-evaluation hook into create_or_update_listing_and_price + add SES email path + signed-JWT public unsubscribe endpoint (closes the S07 price-drop alert loop)

**Wire alert-evaluation hook into create_or_update_listing_and_price + add SES email path + signed-JWT public unsubscribe endpoint (closes the S07 price-drop alert loop)**

## What Happened

Closed the S07 price-drop alert loop by landing the three integration pieces of T03 as a single unit:

1. **Evaluator**: added `evaluate_alerts_for_listing(db, part_id, retailer_id, price_cents, observed_at)` to `app/api/services/part_price_alert_service.py`. Queries active alerts on the part where `threshold_cents >= price_cents`, then per-alert: (a) suppresses on a 24h cooldown (`observed_at - last_fired_at < ALERT_COOLDOWN`); (b) calls `app.core.email.send_price_drop_alert_email`; (c) on send-success sets `last_fired_at = observed_at` + flushes; (d) emits one `price_alert_evaluated: alert_id=... part_id=... price_cents=N threshold_cents=N verdict=<fired|suppressed_cooldown> elapsed_ms=N` INFO log per evaluation plus one `price_alert_email_sent: alert_id=... user_id=... success=<bool>` per attempted send. Per-alert iteration is wrapped in try/except so one bad row cannot poison the price-write transaction (logs at WARNING with `alert_id` and continues). SES failure leaves `last_fired_at` unchanged so the next observation retries — matches the planned idempotent-retry contract.

2. **Chokepoint wiring**: at the end of `create_or_update_listing_and_price` in `part_listing_service.py`, AFTER the listing/history flush and BEFORE `return listing`, gated on the same `price_cents is not None and price_cents >= 0` condition that drives the price-history append. The cross-service import is function-local to avoid a circular module-load (captured as MEM091).

3. **Email path**: added `send_price_drop_alert_email(to_email, part, retailer, price_cents, alert) -> bool` to `app/core/email.py` plus a new HTML template at `app/core/email_templates/price_drop_alert.html` (skeleton mirrors `verify_email.html` — header, paragraph, button, link, footer; uses `.replace()` placeholders, no React Email build step). Signed JWT is built via `create_access_token(data={'sub': str(alert.id), 'purpose': 'price_alert_unsubscribe'}, expires_delta=timedelta(days=30))`. URL branches DEBUG (localhost:8000) vs prod (api.carmodpicker.com) exactly like `send_verify_email`. Subject: `[CarModPicker] Price drop on <part name>`. Added `PRICE_DROP_ALERT_SUBJECT_PREFIX` constant near `VERIFY_EMAIL_SUBJECT`.

4. **Public unsubscribe endpoint**: `GET /api/part-price-alerts/unsubscribe?token=...` in `part_price_alerts.py` with NO auth dependency — token IS the auth (mirrors `/api/auth/verify-email/confirm`). Decodes JWT, requires `purpose == 'price_alert_unsubscribe'`, parses `sub` as UUID, loads the alert by id, sets `active=False`, redirects to `/account/alerts?status=success&message=Unsubscribed` (DEBUG: localhost:4000; prod: www.carmodpicker.com). Every failure path (`InvalidTokenError`, wrong purpose, non-UUID sub, missing alert) funnels to the same `status=error&message=Invalid+or+expired+link` redirect — never reveals WHY decode failed (captured as MEM092). Idempotent: clicking the link twice still results in `active=False` and a success redirect.

5. **Tests**: `tests/services/test_part_price_alert_evaluation.py` — 11 cases covering below-threshold fires + above-threshold skips + at-threshold fires + 24h cooldown suppression + cooldown reset (25h+ → fires again) + cross-part isolation (alert on part A doesn't fire on observation of part B) + send-failure leaves `last_fired_at` unchanged + exception-safe iteration (one alert raising during send doesn't block the next) + inactive alerts skipped + integration-evidence test that `create_or_update_listing_and_price` actually drives the evaluator (the chokepoint contract). Mocks the email sender via `monkeypatch.setattr("app.core.email.send_price_drop_alert_email", ...)`. Added 6 unsubscribe-flow tests to `tests/api/endpoints/test_part_price_alerts.py`: valid token → 302 + `active=False`, wrong purpose → 302 to error + alert untouched, expired token → error redirect, garbage non-JWT → error redirect, JWT with non-UUID `sub` → error redirect, well-formed token referencing nonexistent alert → error redirect.

Captured patterns MEM090 (per-alert exception-safe iteration), MEM091 (lazy-import cross-service hook), MEM092 (token-as-auth one-click unsubscribe idiom). Saved decision D010 on the SES send-failure → `last_fired_at` semantics.

## Verification

Ran the alerts evaluator suite + endpoint suite + openapi snapshot + part_price_alert model suite via `pytest tests/services/test_part_price_alert_evaluation.py tests/api/endpoints/test_part_price_alerts.py tests/test_openapi_snapshot.py tests/models/test_part_price_alert.py -n auto -q --no-cov` → 44/44 pass in 5.90s. Then ran the call-site regression suites that exercise `create_or_update_listing_and_price` (`tests/api/endpoints/test_parts.py tests/api/endpoints/test_build_list_parts.py`) → 64/64 pass in 7.15s — confirms the new evaluator hook does not break any existing chokepoint caller. The plan-spec command also referenced `tests/services/test_part_listing_service.py` (does not exist in codebase); the integration-coverage gap that file would have filled is satisfied by `test_create_or_update_listing_and_price_invokes_evaluator` in the new evaluator test file. Slice-level runtime signals (`price_alert_evaluated`, `price_alert_email_sent`) verified by reading the evaluator implementation and asserting the call sequence in tests; redaction constraint honored (no email/token logged anywhere). Inspection surface (`GET /api/part-price-alerts/me`) was already live from T02. Regenerated `tests/fixtures/openapi_snapshot.json` to include the new `/unsubscribe` route (per MEM088 — adding any new endpoint legitimately drifts the snapshot).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest tests/services/test_part_price_alert_evaluation.py tests/api/endpoints/test_part_price_alerts.py -n auto --rootdir=. -q --no-cov` | 0 | pass (33/33) | 5890ms |
| 2 | `pytest tests/services/test_part_price_alert_evaluation.py tests/api/endpoints/test_part_price_alerts.py tests/test_openapi_snapshot.py tests/models/test_part_price_alert.py -n auto -q --no-cov` | 0 | pass (44/44) | 5900ms |
| 3 | `pytest tests/api/endpoints/test_parts.py tests/api/endpoints/test_build_list_parts.py -n auto -q --no-cov (chokepoint call-site regression)` | 0 | pass (64/64) | 7150ms |
| 4 | `python -c 'from app.api.services import part_price_alert_service; assert hasattr(part_price_alert_service, "evaluate_alerts_for_listing")' (sanity import)` | 0 | pass | 250ms |
| 5 | `regenerate openapi snapshot: python -c 'import json,sys; from app.main import app; sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True))' > tests/fixtures/openapi_snapshot.json && pytest tests/test_openapi_snapshot.py -q --no-cov` | 0 | pass (1/1, snapshot regenerated to include /unsubscribe) | 350ms |

## Deviations

The verification command in the task plan referenced `backend/tests/services/test_part_listing_service.py`, which does not exist in the codebase (no service-level test file for `part_listing_service` was ever created in any prior slice). The integration-coverage gap that file would have filled — proving that `create_or_update_listing_and_price` actually drives the evaluator hook, not just that the evaluator works in isolation — is captured in `test_create_or_update_listing_and_price_invokes_evaluator` inside the new `test_part_price_alert_evaluation.py`. Ran the rest of the plan-spec verification clean: alerts evaluator suite + endpoint suite + openapi snapshot + part_price_alert model suite = 44/44 pass; call-site regression suites for `create_or_update_listing_and_price` (parts + build_list_parts) = 64/64 pass. Also regenerated `tests/fixtures/openapi_snapshot.json` to include the new `/unsubscribe` endpoint (per MEM088 — adding any new endpoint legitimately drifts the snapshot).

## Known Issues

None for this task. Frontend surfaces from the slice goal (subscribe button on /parts/:id, /account/alerts management page) are out of scope for T03 — T03 is the backend integration unit and the frontend pieces land in subsequent tasks.

## Files Created/Modified

- `backend/app/api/services/part_price_alert_service.py`
- `backend/app/api/services/part_listing_service.py`
- `backend/app/core/email.py`
- `backend/app/core/email_templates/price_drop_alert.html`
- `backend/app/api/endpoints/part_price_alerts.py`
- `backend/tests/services/test_part_price_alert_evaluation.py`
- `backend/tests/api/endpoints/test_part_price_alerts.py`
- `backend/tests/fixtures/openapi_snapshot.json`
