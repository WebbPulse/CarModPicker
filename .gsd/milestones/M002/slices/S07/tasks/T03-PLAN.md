---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T03: Wire alert-evaluation hook into create_or_update_listing_and_price + add SES email + signed-JWT unsubscribe endpoint

Close the alert loop: every price-write through the canonical chokepoint MUST evaluate active alerts on that part and fire email when threshold is breached. Add three pieces in this task because they form a single integration unit. (1) Evaluation service: `backend/app/api/services/part_price_alert_service.py::evaluate_alerts_for_listing(db, part_id, retailer_id, price_cents, observed_at)`. Query active alerts WHERE part_id matches AND threshold_cents >= price_cents. For each match: (a) check 24h cooldown — `if alert.last_fired_at and (observed_at - alert.last_fired_at) < timedelta(hours=24): log 'suppressed_cooldown'; continue`; (b) call `send_price_drop_alert_email(user.email, part, retailer, price_cents, alert)` from app.core.email; (c) on send-success update `alert.last_fired_at = observed_at` and db.add+flush; (d) emit one structured INFO log per evaluated alert (`price_alert_evaluated: alert_id=... verdict=...`). Service must be exception-safe — wrap each per-alert iteration in try/except so a single bad alert can't poison the price-write transaction; log the exception and continue. Call site: at the end of `create_or_update_listing_and_price` in `backend/app/api/services/part_listing_service.py` AFTER `db.flush()` and BEFORE `return listing`, gated on `price_cents is not None and price_cents >= 0` (same condition that triggers the price-history append). (2) Email path: add `send_price_drop_alert_email(user_email, part, retailer, price_cents, alert) -> bool` to `backend/app/core/email.py`. Build the unsubscribe URL via `create_access_token(data={'sub': str(alert.id), 'purpose': 'price_alert_unsubscribe'}, expires_delta=timedelta(days=30))`; format URL using the same DEBUG/prod branch as send_verify_email (`http://localhost:8000/api/part-price-alerts/unsubscribe?token=...` in DEBUG, `https://api.carmodpicker.com/api/part-price-alerts/unsubscribe?token=...` in prod). Subject: `[CarModPicker] Price drop on <part name>`. Add `PRICE_DROP_ALERT_SUBJECT` constant near VERIFY_EMAIL_SUBJECT. Build a minimal HTML template at `backend/app/core/email_templates/price_drop_alert.html` with `{{PART_NAME}}`, `{{CURRENT_PRICE}}` (formatted USD), `{{RETAILER_NAME}}`, `{{PART_URL}}`, `{{UNSUBSCRIBE_URL}}` placeholders — copy the structural skeleton from `verify_email.html` (header, paragraph, button, link, footer). Use simple .replace() like the existing helpers — no React Email build step. (3) Public unsubscribe endpoint: `GET /api/part-price-alerts/unsubscribe?token=...` in `part_price_alerts.py` (no auth dependency — token IS the auth, like verify-email/confirm). Decode JWT; require `purpose == 'price_alert_unsubscribe'`; load alert by id; set active=False; redirect to `http://localhost:4000/account/alerts?status=success&message=Unsubscribed` in DEBUG, `https://www.carmodpicker.com/account/alerts?status=success&message=Unsubscribed` in prod. Invalid/expired token → redirect with `status=error&message=Invalid+or+expired+link`. Tests: `backend/tests/services/test_part_price_alert_evaluation.py` covers below-threshold fires + above-threshold skips + 24h cooldown suppression + cooldown reset after recovery (last_fired_at set then a higher price observation — next under-threshold observation 25h later DOES fire) + cross-user isolation (alice's alert doesn't fire on bob's listing on a different part) + send-failure leaves last_fired_at unchanged + exception-safe iteration (one bad alert doesn't block another). Mock `app.core.email.send_price_drop_alert_email` with monkeypatch returning True/False. Add unsubscribe-flow tests to `test_part_price_alerts.py` (valid token → 302 + alert.active=False; bad purpose → 302 to error; expired → 302 to error).

## Inputs

- ``backend/app/api/services/part_listing_service.py``
- ``backend/app/api/services/part_price_alert_service.py``
- ``backend/app/core/email.py``
- ``backend/app/core/email_templates/verify_email.html``
- ``backend/app/api/endpoints/auth/core.py``
- ``backend/app/api/dependencies/auth.py``
- ``backend/app/api/models/part_price_alert.py``
- ``backend/app/api/models/user.py``
- ``backend/app/api/models/retailer.py``

## Expected Output

- ``backend/app/api/services/part_price_alert_service.py``
- ``backend/app/api/services/part_listing_service.py``
- ``backend/app/core/email.py``
- ``backend/app/core/email_templates/price_drop_alert.html``
- ``backend/app/api/endpoints/part_price_alerts.py``
- ``backend/tests/services/test_part_price_alert_evaluation.py``
- ``backend/tests/api/endpoints/test_part_price_alerts.py``

## Verification

TESTING=true pytest backend/tests/services/test_part_price_alert_evaluation.py backend/tests/api/endpoints/test_part_price_alerts.py backend/tests/services/test_part_listing_service.py -n auto --rootdir=backend -q --no-cov

## Observability Impact

Adds two new structured INFO log shapes — `price_alert_evaluated: alert_id=... part_id=... price_cents=N threshold_cents=N verdict=<fired|suppressed_cooldown|skip_above_threshold> elapsed_ms=N` per evaluated alert and `price_alert_email_sent: alert_id=... user_id=... success=<bool>`. Failure visibility: any exception in per-alert iteration is logged at WARNING with alert_id and re-raised silently (does not poison the price-write transaction); SES failure leaves last_fired_at None so retry semantics are correct. Redaction: do NOT log email addresses or unsubscribe tokens — alert_id + user_id (UUID) only. Failure mode: SES outage → emails silently fail-closed (send returns False), last_fired_at stays None, next observation tries again. Load: K active alerts per part means K extra SELECT/UPDATE on every price write — acceptable at current catalog scale; flag if a single part exceeds 100 active alerts (out-of-scope for this slice). Negative test: 24h cooldown suppression, exception-safe iteration, send-failure idempotency.
