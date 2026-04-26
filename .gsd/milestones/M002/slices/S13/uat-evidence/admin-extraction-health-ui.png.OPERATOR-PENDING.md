# admin-extraction-health-ui.png — operator capture pending

Auto-mode cannot capture the S11 UI render because the frontend dev server is not running in this worktree (M002 worktree only has the backend on :8000 active during T04 execution). The task plan flags this as an operator action ("Visual smoke /admin/extraction-health in the browser (operator) — confirm the S11 UI rendering matches the JSON shape").

The JSON contract has been live-verified — see `admin-extraction-health.json` in this directory:
- compliance.compliant: 108
- compliance.total: 108
- compliance.per_tier: {http: '83/83', tls: '15/15', browser: '10/10'}
- coverage.per_tier present for all 3 tiers
- failure_rate_7d is a list of 56 entries
- window.days: 7

## Operator capture procedure

1. From the primary worktree (not M002): `cd frontend && npm run dev` (port 4000)
2. Backend should already be on :8000 — if not, `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
3. Sign in as admin: username `admin`, password `admin123` (TOTP from operator's authenticator)
4. Navigate to `/admin/extraction-health`
5. Capture full-page screenshot to this directory as `admin-extraction-health-ui.png` (replacing this marker)
6. Confirm the rendered UI matches the JSON above:
   - Compliance card hero: "108/108"
   - Per-tier pills: 83/83 http, 15/15 tls, 10/10 browser
   - Coverage card heatmap rendered (likely all-zeros or sparse — extraction backfill hasn't populated specifications yet on prod data)
   - Failure-Rate table rendered (or "No failures in window" empty-state if all rates are 0)
