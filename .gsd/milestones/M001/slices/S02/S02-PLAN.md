# S02: Observability

**Status:** ✅ completed 2026-04-23
**Goal:** Production errors are visible in Sentry, per-adapter crawler metrics flow into CloudWatch, and a parse-failure alarm fires automatically — all without changing any URL, schema, or external contract.
**Demo:** Unhandled exception → Sentry with request_id/user_id/SQL context; crawler run → CloudWatch EMF metrics in `CarModPicker/Crawlers`; parse-failure alarm fires → SNS → SES email.

## Must-Haves

- Sentry SDK 2.x backend (FastAPI/Starlette/SQLAlchemy/Logging integrations + before_send scope processor)
- `@sentry/react` + Session Replay on-error + ErrorBoundary
- CloudWatch EMF per-adapter metrics (Ingested/ParseFailures/ElapsedSeconds)
- Terraform parse-failure alarm (composite, RunType=live filter)
- request_id/user_id propagation audit + bg_log_context

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/02-observability/` (5 PLAN/SUMMARY pairs: 02-01 through 02-05).

## Files Likely Touched

`backend/app/core/sentry.py`, `backend/app/crawlers/runner.py`, `frontend/src/`, `terraform/`
