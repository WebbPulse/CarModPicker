# S07: Price-drop alerts (subscription, threshold, email) — UAT

**Milestone:** M002
**Written:** 2026-04-25T23:01:20.986Z

# S07 UAT — Price-drop alerts (subscription, threshold, email)

This slice's UAT is mocked-SES (the live email send falls to S13). Tests + Playwright + manual smoke cover the demo flow.

## Preconditions

- Local backend running (`uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` from `backend/`) with Postgres up via `docker-compose up -d`
- Database has been migrated to head (`cd backend && alembic upgrade head` → `9aa798d6107e (head)`)
- Local frontend running (`npm run dev` from `frontend/`) on port 4000 proxying /api to 8000
- A test user account exists with `email_verified=true` (pass the EmailVerifiedRoute gate)
- At least one Part with a Retailer + at least one PartListing observation exists (use `python ../scripts/populate_sample_data.py` from `backend/`)
- Logged in as the test user in the browser

## Test Case 1: Subscribe to a part (happy path)

1. Navigate to `/parts/<part_id>` for a part with a known best price (e.g. `current_best_price = $100`)
2. Locate the "Notify me on price drop" button next to the "Price summary (90 days)" header
3. Click the button → a Radix Dialog opens with a threshold input prefilled to `100`
4. Change the value to `99` and click "Subscribe"
5. **Expected:**
   - Dialog closes
   - Trigger button label flips to "Manage alert ($99.00)"
   - Network panel shows `POST /api/part-price-alerts/` with body `{ "part_id": "<uuid>", "threshold_cents": 9900 }` returning 201
   - Backend log shows `part_price_alert_subscribed: alert_id=... user_id=... part_id=... threshold_cents=9900`

## Test Case 2: Re-subscribe is idempotent

1. With the Test Case 1 alert still active, click "Manage alert ($99.00)"
2. Change threshold to `89` and click "Subscribe"
3. **Expected:**
   - Same alert row in DB (no duplicate); threshold_cents=8900; active=True
   - Trigger button label flips to "Manage alert ($89.00)"
   - DB query: `SELECT COUNT(*) FROM part_price_alerts WHERE user_id=<user> AND part_id=<part>` returns exactly 1

## Test Case 3: Anonymous user redirect

1. Log out
2. Navigate to `/parts/<part_id>`
3. Click "Notify me on price drop"
4. **Expected:**
   - Browser navigates to `/login?next=/parts/<part_id>`
   - Dialog never opens
   - No network call to `/api/part-price-alerts/me` or `/api/part-price-alerts/`

## Test Case 4: Threshold validation (negative value)

1. Logged in, on `/parts/<part_id>`, click "Notify me on price drop"
2. Enter `-5` and click "Subscribe"
3. **Expected:**
   - Inline error: "Threshold must be 0 or greater" (or backend's 422 detail)
   - No network call (client-side guard rejects before submit)
   - Dialog stays open with the value preserved

## Test Case 5: Threshold breach fires alert (mocked SES)

This is exercised at the unit-test layer because live SES is deferred to S13. To verify locally:

1. From `backend/`: `pytest tests/services/test_part_price_alert_evaluation.py::test_below_threshold_fires_email -n auto -q --no-cov`
2. **Expected:** test passes — confirms `evaluate_alerts_for_listing` calls `send_price_drop_alert_email` exactly once when an observation comes in at or below threshold, sets `last_fired_at` on send-success, and emits the structured `price_alert_evaluated: verdict=fired` log
3. To verify the chokepoint hook is wired: `pytest tests/services/test_part_price_alert_evaluation.py::test_create_or_update_listing_and_price_invokes_evaluator -n auto -q --no-cov`
4. **Expected:** test passes — confirms a real call through `create_or_update_listing_and_price` drives the evaluator

## Test Case 6: 24h cooldown suppression and recovery

1. From `backend/`: `pytest tests/services/test_part_price_alert_evaluation.py::test_cooldown_suppression tests/services/test_part_price_alert_evaluation.py::test_cooldown_reset_after_recovery -n auto -q --no-cov`
2. **Expected:** both tests pass — confirms a second observation under threshold within 24h of a fired alert emits `verdict=suppressed_cooldown` and does NOT call SES, and that an observation 25h+ later (or after a recovery above-threshold observation) DOES fire again

## Test Case 7: View and unsubscribe via /account/alerts

1. Logged in with at least one active alert
2. Navigate to `/account/alerts`
3. **Expected:**
   - Heading "Your price-drop alerts" renders
   - Each active alert is listed with: linked part name (→ `/parts/<part_id>`), threshold formatted as USD, created_at, "Last sent <date>" or "Not sent yet", and an Unsubscribe button
4. Click "Unsubscribe" on a row
5. **Expected:**
   - `DELETE /api/part-price-alerts/<id>` fires, returns 204
   - Row disappears from the visible list (optimistic remove)
   - Reloading the page confirms the row is gone (and the underlying DB row has `active=False`)

## Test Case 8: Empty state

1. Unsubscribe from all alerts
2. Reload `/account/alerts`
3. **Expected:** Empty-state copy "You have no active price-drop alerts. Visit a part page to create one." with a `Browse parts` link to `/parts`

## Test Case 9: Public unsubscribe link (token-as-auth)

1. Generate a valid signed JWT for an alert (or copy one from a logged email body in dev):
   ```python
   from app.api.dependencies.auth import create_access_token
   from datetime import timedelta
   token = create_access_token(data={'sub': str(alert.id), 'purpose': 'price_alert_unsubscribe'}, expires_delta=timedelta(days=30))
   ```
2. Visit `http://localhost:8000/api/part-price-alerts/unsubscribe?token=<token>` in a fresh browser tab (not authenticated — token IS the auth)
3. **Expected:**
   - 302 redirect to `http://localhost:4000/account/alerts?status=success&message=Unsubscribed`
   - Alert row in DB has `active=False`
   - The `/account/alerts` page renders a green SuccessAlert banner reading "Unsubscribed" with a Dismiss button
4. Visit the same URL again (idempotency check)
5. **Expected:** Same redirect; alert stays `active=False`; success banner appears again

## Test Case 10: Public unsubscribe link — invalid token paths (uniform error)

For each of the following malformed tokens, visit `/api/part-price-alerts/unsubscribe?token=<bad>`:

- a) Garbage non-JWT: `?token=not-a-jwt`
- b) Expired token (manually forge with `expires_delta=timedelta(seconds=-1)`)
- c) JWT with wrong purpose: `purpose='verify_email'`
- d) JWT with non-UUID sub: `sub='not-a-uuid'`
- e) Well-formed token referencing a deleted alert id

**Expected (every case):** 302 redirect to `/account/alerts?status=error&message=Invalid+or+expired+link`. The frontend renders an ErrorAlert banner. NO information leak about WHY the token failed (privacy-preserving — same redirect for all failure modes).

## Test Case 11: Cross-user isolation

1. As user Alice, subscribe to part P1 with threshold $100
2. As user Bob, subscribe to part P2 with threshold $50
3. Trigger an observation on P1 at $90
4. **Expected:** Alice's alert fires (last_fired_at populated). Bob's alert remains untouched (last_fired_at=NULL, active=True). Confirmed by `pytest tests/services/test_part_price_alert_evaluation.py::test_cross_part_isolation -n auto -q --no-cov`.
5. Visit `/account/alerts` as Bob → only Bob's P2 alert listed (Alice's is not visible)

## Test Case 12: Playwright e2e demo flow

1. From `frontend/`: `npm run test:e2e -- price-alerts.spec.ts`
2. **Expected:** 3/3 pass at mobile (375px) / tablet / desktop. The spec exercises subscribe → assert button label flips to "Manage alert ($99.00)" → take one bounded screenshot per viewport → navigate to `/account/alerts` → assert row visible → click unsubscribe → assert DELETE called and row disappears.
3. Three baseline screenshots are committed under `frontend/e2e/price-alerts.spec.ts-snapshots/` for visual regression.

## Edge cases verified at unit-test layer

- Send-failure leaves last_fired_at unchanged → next observation retries (`test_send_failure_leaves_last_fired_at_unchanged`)
- Exception-safe per-alert iteration → one bad alert doesn't poison the parent transaction (`test_exception_safe_iteration_continues_after_failure`)
- Inactive alerts are excluded from evaluation (`test_inactive_alerts_skipped`)
- At-threshold equality fires (≤, not <) (`test_at_threshold_fires`)
- /me excludes inactive alerts (T02 `test_list_mine_excludes_inactive`)
- Soft-delete via DELETE keeps the row, sets active=False (T02 `test_delete_soft_deletes`)

## Deferred to S13

- Live SES send against a real email address with the actual `price_drop_alert.html` template rendered in Gmail/Outlook/Apple Mail
- End-to-end integration against a real product URL: scrape → universal extraction → Pydantic validation → ingest → price-history append → evaluator → SES send → email arrives in inbox
