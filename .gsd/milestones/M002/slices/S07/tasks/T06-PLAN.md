---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T06: Playwright e2e covering the demo: subscribe → mocked-observation fires → unsubscribe

Add `frontend/e2e/price-alerts.spec.ts` covering the slice's demo statement at the three viewports (mobile/tablet/desktop). Use `page.route(/\/api\/(?!.*\.ts)/, ...)` per MEM082 to avoid intercepting Vite source modules. Module-level fixtures: an authenticated test user, one `Part` with a known retailer + best-price observation. Test flow: (1) navigate to `/parts/<part_id>`, click 'Notify me on price drop', enter threshold $99 in the dialog, submit; assert POST /part-price-alerts/ was made with the right body and the button label flips to 'Manage alert ($99.00)'. (2) Navigate to `/account/alerts`; assert the new alert is listed. (3) Click 'Unsubscribe' on the row; assert DELETE /part-price-alerts/{id} was called and the row disappears. The 'mocked observation fires email' assertion is done at the unit-test layer (T03 service tests) — Playwright covers UI flow only, not the backend hook. Pin Date.now() if any rendering depends on it (last_fired_at formatting, etc.) per MEM079. Three baseline screenshots committed under `frontend/e2e/price-alerts.spec.ts-snapshots/` for the three viewports — only one screenshot test (after subscribe + before unsubscribe) to keep the snapshot count bounded. Reuse the playwright.config.ts viewports established in S08.

## Inputs

- ``frontend/e2e/price-history.spec.ts``
- ``frontend/playwright.config.ts``
- ``frontend/src/api/part_price_alerts.ts``
- ``frontend/src/components/parts/PriceAlertSubscribeButton.tsx``
- ``frontend/src/pages/account/AccountAlerts.tsx``
- ``frontend/src/App.tsx``

## Expected Output

- ``frontend/e2e/price-alerts.spec.ts``
- ``frontend/e2e/price-alerts.spec.ts-snapshots/``

## Verification

cd frontend && npm run test:e2e -- price-alerts.spec.ts
