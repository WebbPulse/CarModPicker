---
estimated_steps: 6
estimated_files: 11
skills_used: []
---

# T01: Run live full-stack UAT walkthrough — extraction → ingest → /parts sparkline → /parts/:id breakdown → alert email → unsubscribe

Execute the slice's demo statement end-to-end against a live local stack. This is the highest-blast-radius task in S13 — if it fails, every later task is wasted. Operator pre-flight: docker-compose up -d (Postgres 16), `cd backend && alembic upgrade head`, `cd backend && python ../scripts/populate_sample_data.py` (seed coilover/brake/turbo parts + observations + retailers + a test user with verified email), `CRAWLER_USER_ID=<uuid> CRAWLER_DEFAULT_CATEGORY_NAME=exhaust uvicorn app.main:app --port 8000` (backend), `cd frontend && npm run dev` (frontend on :4000). Confirm GET http://localhost:8000/health returns 200 and GET http://localhost:8000/ready returns 200 before proceeding.

Branch decision for the live-fetch portion: prefer archive_rescrape against a representative S3-archived HTML body OR `python -m app.crawlers --adapter bcracing --limit 1` if the retailer is healthy at UAT time. Both exercise universal-extraction → category-extraction → Pydantic validation → ingest → Part.specifications populated. Sample-data injection alone is INSUFFICIENT — the slice plan demo statement requires the extraction loop be exercised. Tail the backend log during the run and capture: `universal_extraction_extracted`, `category_extraction_validated: part_id=<uuid>`, `ingest_payload: parse_status=parsed_ok`, and the resulting Part.specifications dict.

Walk the frontend demo: log in as the test user; visit /parts and confirm the chosen part shows a sparkline + delta line; click into /parts/:id and confirm the 'Price summary (90 days)' block renders with the per-retailer breakdown (flat list ≤3 retailers, Tabs >3); confirm the legacy PriceHistoryLineChart STILL RENDERS (T03 deletes it — at this point it must still be intact); subscribe to a price drop with threshold=current_price+$5 (so the next observation will fire); inject one observation below threshold via `python -c 'from app.api.services.part_listing_service import create_or_update_listing_and_price...'` against the live DB OR replay an archive_rescrape with a downward-shifted price; tail the log for `price_alert_evaluated: verdict=fired` and `price_alert_email_sent: success=true`. Operator confirms email arrives in `tylert2610+m002-uat@gmail.com` (or the configured fixture inbox); operator clicks the unsubscribe link → 302 redirect → /account/alerts?status=success → row removed.

Capture all evidence into `.gsd/milestones/M002/slices/S13/uat-evidence/`: backend log excerpt (universal+category+ingest+alert lines, redacted of email addresses), screenshots of /parts (sparkline visible), /parts/:id (retailer breakdown, both ≤3 and >3 cases if sample data permits), /account/alerts (subscribed state + post-unsubscribe state), inbox email render (recipient redacted). Document each artifact in S13-UAT.md with a one-line caption.

AUTONOMOUS-MODE CHECKPOINT: Auto-mode CANNOT bring up Docker. The executor must verify the stack is live (curl /health, curl /ready, curl /api/parts/?limit=1 expecting 200) before proceeding. If any check fails, write a blocker note to T01-SUMMARY.md describing what's down and exit cleanly — do NOT attempt to launch Docker. Operator resumes the task after bringing the stack up.

SES live-send caveat: if `app.core.email.send_price_drop_alert_email` dry-runs by default in dev (verify by reading email.py), set the env vars to force live send. The S07-deferred 'live SES UAT' is the heart of T01 — without an email arriving in the operator's inbox, T01 has not completed.

## Inputs

- ``backend/app/crawlers/base.py` — universal extraction post-hook output to tail`
- ``backend/app/api/services/part_price_alert_service.py` — evaluator log lines `price_alert_evaluated` / `price_alert_email_sent` to capture`
- ``backend/app/core/email.py` — SES send dispatch behavior; verify dry-run vs live`
- ``backend/app/main.py` — /health and /ready endpoints for operator pre-flight`
- ``scripts/populate_sample_data.py` — seed script for parts/observations/retailers/users`
- ``frontend/src/pages/parts/PartsCatalog.tsx` — /parts sparkline rendering surface`
- ``frontend/src/pages/builder/ViewPart.tsx` — /parts/:id retailer breakdown surface (legacy chart still present at this point)`
- ``frontend/src/pages/account/AccountAlerts.tsx` — /account/alerts management surface`

## Expected Output

- ``.gsd/milestones/M002/slices/S13/uat-evidence/extraction-and-alert.log` — backend log excerpt with universal+category+ingest+alert lines (email redacted)`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/parts-sparkline.png` — /parts page screenshot`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/parts-detail-breakdown.png` — /parts/:id page screenshot`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/account-alerts-subscribed.png` — /account/alerts before unsubscribe`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/account-alerts-unsubscribed.png` — /account/alerts after unsubscribe`
- ``.gsd/milestones/M002/slices/S13/uat-evidence/inbox-email-render.png` — email render with recipient redacted`
- ``.gsd/milestones/M002/slices/S13/S13-UAT.md` — committed UAT script + per-step verdict + evidence links`

## Verification

test -f .gsd/milestones/M002/slices/S13/S13-UAT.md && test -d .gsd/milestones/M002/slices/S13/uat-evidence && test $(ls .gsd/milestones/M002/slices/S13/uat-evidence/ | wc -l) -ge 5 && grep -q 'price_alert_email_sent' .gsd/milestones/M002/slices/S13/uat-evidence/*.log

## Observability Impact

Captures and commits structured-log evidence for the full extraction → ingest → alert → email path. Future agents inspect `.gsd/milestones/M002/slices/S13/uat-evidence/extraction-and-alert.log` to confirm what the live system actually emitted at the M002-close gate. Email addresses MUST be redacted in the committed log; `+`-suffix fixture inbox isolates UAT mail from operator's primary inbox.
