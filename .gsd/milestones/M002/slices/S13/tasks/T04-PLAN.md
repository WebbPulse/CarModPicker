---
estimated_steps: 5
estimated_files: 4
skills_used: []
---

# T04: Run compliance-audit + admin extraction-health live verification + fix PROJECT.md adapter-count drift

Final adapter-contract proof against the live stack. Three verifications:

1. Compliance audit: `cd backend && python -m app.crawlers.compliance_audit`. Expected output (per MEM037/MEM122 — 108 not 111): exit 0, stdout contains `Total: 108/108 compliant` and per-tier breakdown `T0 (http): 83/83 compliant`, `T1 (tls): 15/15 compliant`, `T2 (browser): 10/10 compliant`. Capture stdout to `.gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt`.

2. Admin extraction-health endpoint live hit: against the running uvicorn from T01, log in as an admin user (use the test admin or promote the test user via `python -c 'from app.api.models.user import User; ... .is_admin=True'`), grab the JWT cookie, then `curl -H 'Cookie: <admin-token>' http://localhost:8000/api/admin/extraction-health | python -m json.tool > .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json`. Assert in the captured JSON: `compliance.compliant == 108`, `compliance.total == 108`, `compliance.per_tier.http == '83/83'`, `compliance.per_tier.tls == '15/15'`, `compliance.per_tier.browser == '10/10'`, `coverage.per_tier` keys present, `failure_rate_7d` is a list, `window.days == 7`. Visual smoke /admin/extraction-health in the browser (operator) — confirm the S11 UI rendering matches the JSON shape; capture a screenshot to `.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-ui.png`.

3. Fix PROJECT.md adapter-count drift: per MEM037/MEM122 and S03's deviations, the roadmap text in PROJECT.md still says '111 adapters' in places. The live ADAPTER_REGISTRY has 108. Read PROJECT.md, find every '111' that refers to adapter count (the 3-adapter delta is IS_FALLBACK GenericHtmlParser instances per tier excluded from the registry per D-03), and correct to '108' with a brief inline note. Do NOT modify M002-ROADMAP.md (historical artifact — slice plans/summaries already note the drift).

Verification: `grep -n '111' .gsd/PROJECT.md | grep -i adapter` returns no hits after the correction. The compliance-audit stdout file exists and contains '108/108'. The admin-extraction-health.json file exists and contains valid JSON with `compliance.compliant: 108`.

## Inputs

- ``backend/app/crawlers/compliance_audit.py` — script-as-test gate (S03)`
- ``backend/app/api/endpoints/admin/extraction_health.py` — admin endpoint (S04)`
- ``.gsd/PROJECT.md` — contains stale '111 adapters' text to correct`

## Expected Output

- ``.gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt` — `python -m app.crawlers.compliance_audit` stdout (108/108)`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json` — live endpoint JSON dump`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health-ui.png` — browser screenshot of S11 UI rendering`
- ``.gsd/PROJECT.md` — adapter count corrected from 111 to 108 with inline note`

## Verification

test -f .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt && grep -q '108/108' .gsd/milestones/M002/slices/S13/uat-evidence/compliance-audit-stdout.txt && test -f .gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json && python -c 'import json;d=json.load(open(".gsd/milestones/M002/slices/S13/uat-evidence/admin-extraction-health.json"));assert d["compliance"]["compliant"]==108'

## Observability Impact

compliance-audit-stdout.txt and admin-extraction-health.json are the durable proofs that the M002 adapter contract held at milestone close. Future agents inspecting M002's adapter contract should read these committed artifacts; the compliance-audit script remains the canonical gate at PR time.
