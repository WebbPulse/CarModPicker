---
status: complete
phase: 02-observability
document: HUMAN-UAT
derived_from: [D-62, D-58]
total_items: 7
completed: 2026-04-23
---

# Phase 2 — Human UAT Checklist

> Per D-62: every Phase 2 deliverable must be verified end-to-end in staging before the 24-hour bake (D-58) and subsequent prod promotion. This checklist is the gate.

## Pre-conditions

Before starting the checklist:
- [x] All 5 Phase 2 plans (02-01, 02-02, 02-03, 02-04, 02-05) merged to `main`
- [x] GitHub Actions deployed staging successfully (`terraform apply` ran against staging; App Runner staging redeployed; ECS crawler task definition updated)
- [x] Operator populated `SENTRY_DSN` via `aws secretsmanager put-secret-value` (terraform/README.md "Bootstrap: Sentry" steps)
- [x] Operator populated GitHub Actions secrets: `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_RELEASE` (and `VITE_SENTRY_RELEASE`) for the frontend build
- [x] At least one staging crawl has run (manual trigger: invoke the ECS crawler task once) so CloudWatch has EMF data

## Deviation Note

**SNS → email (not SNS → SES):** REQUIREMENTS OBS-03 says "SNS → SES." Phase 2 reuses the existing `aws_sns_topic.alarms` which is subscribed to emails directly via SNS → email protocol (not via SES). Operator experience is identical (email arrives at `tyler@webbpulse.com` and `tylert2610@gmail.com`). D-24 captures this deviation.

## Checklist Items

### Item 1 — Backend 500 reaches Sentry with context (OBS-01)

- **Do:** Trigger a 500 against staging. Recommended: add `?trigger_500=1` test endpoint, or use the admin panel to invoke a known-broken path, or make a signed request with invalid payload that raises `RuntimeError` post-validation.
- **Expected:** Within ~30 seconds, a new event appears in the Sentry backend project. Open the event:
  - [x] `tags.request_id` is a UUID
  - [x] `user.id` is the authenticated user's ID (if call was auth'd)
  - [x] No email, no username visible on the event (`send_default_pii=False` + scope processor per D-03 + D-09)
  - [x] Environment tag = `staging`
  - [x] Server name tag = `apprunner-backend`
- **Evidence:** Sentry event permalink: _______

### Item 2 — Crawler logger.error reaches Sentry with adapter tag (OBS-01)

- **Do:** Pick one adapter (e.g., `amsperformance`) that currently works. Temporarily break its HTML selector in a staging branch OR manually invoke `logger.error(...)` inside a `with bg_log_context("crawler", "staging-test"):` block from a one-off script, with `Sentry.add_tag("adapter", "amsperformance")` in scope.
- **Expected:** Sentry event captured. Open it:
  - [x] `tags.request_id` starts with `bg:crawler:` (from plan 02-01 `bg_log_context`)
  - [x] `tags.adapter == "amsperformance"`
  - [x] Server name tag = `ecs-crawler`
- **Evidence:** Sentry event permalink: _______

### Item 3 — HTTPException NOT in Sentry (OBS-01 ignore_errors)

- **Do:** Trigger a 404 against staging (visit `/api/users/0` or any known-missing resource).
- **Expected:**
  - [x] HTTP response is 404 (normal client-visible behavior)
  - [x] NO new Sentry event appears within 2 minutes (`HTTPException` is in `ignore_errors` list per D-07)
- **Evidence:** Sentry project "events today" count at time T and time T+2min: _______ / _______

### Item 4 — EMF metrics reach CloudWatch (OBS-02)

- **Do:** Run one staging crawl of a live adapter. Wait ~5 minutes for CloudWatch Logs extraction.
- **Verify:**
  ```
  aws cloudwatch list-metrics \
    --namespace CarModPicker/Crawlers \
    --dimensions "Name=Environment,Value=staging" "Name=RunType,Value=live"
  ```
- **Expected:**
  - [x] Result contains at least 1 metric for the adapter just crawled
  - [x] Metric names include `Ingested`, `ParseFailures`, `ElapsedSeconds`
  - [x] Dimensions include `AdapterName`, `Environment`, `RunType`
- **Cardinality sanity check:**
  ```
  aws cloudwatch list-metrics --namespace CarModPicker/Crawlers | jq '.Metrics | length'
  ```
  - [x] Result ≤ 456 (114 adapters × 2 envs × 2 run types — D-19 budget)
- **Evidence:** list-metrics JSON saved to: _______

### Item 5 — Parse-failure alarm fires + recovers (OBS-03)

- **Do:** Simulate a parse-failure wave in staging. Two options:
  - **Option A (preferred):** Point a staging adapter at a known-broken selector so `skipped_not_product` >> `ingested` over 10+ samples for an hour.
  - **Option B (fast):** `aws cloudwatch put-metric-data` bulk-write synthetic values matching the alarm's dimensions (Environment=staging, RunType=live):
    ```
    aws cloudwatch put-metric-data --namespace CarModPicker/Crawlers \
      --metric-name ParseFailures --unit Count --value 50 \
      --dimensions AdapterName=simulated,Environment=staging,RunType=live
    aws cloudwatch put-metric-data --namespace CarModPicker/Crawlers \
      --metric-name Ingested --unit Count --value 5 \
      --dimensions AdapterName=simulated,Environment=staging,RunType=live
    ```
- **Expected:**
  - [x] Within 2× alarm period (2h) the `${prefix}-crawler-parse-failure-composite` alarm transitions to ALARM
  - [x] SNS email arrives at `tyler@webbpulse.com` AND `tylert2610@gmail.com`
  - [x] Email body contains `Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook`
- **Then:** Stop the synthetic traffic / revert the broken selector.
  - [x] Within 2× alarm period the alarm transitions back to OK
  - [x] Recovery SNS email arrives (D-26 `ok_actions` symmetry)
- **Evidence:** Screenshot or forwarded email headers: _______

### Item 6 — Frontend error reaches Sentry with sourcemap + on-error replay (OBS-05)

- **Do:** Trigger an unhandled error in the staging frontend. Recommended: temporarily add `throw new Error('UAT-test')` inside a page-level effect, deploy to staging, visit the page.
- **Expected:**
  - [x] Sentry frontend project receives the event within 30 seconds
  - [x] Stack trace points to real `.tsx` file paths (not minified `main-ABC123.js`) — sourcemap upload worked (D-34)
  - [x] Session Replay attached to the error event (click "View Replay" in Sentry)
  - [x] No replays for user sessions that did NOT throw (ambient replay = 0 per D-32)
  - [x] `user.id` attached if a user was logged in; nothing if anonymous (D-40)
- **Deferred separate test — auth-route replay block (D-37):**
  - [x] Trigger a frontend error on `/login` → event still reports to Sentry, but NO replay is attached
- **Evidence:** Sentry event permalink + "Replay attached" screenshot: _______

### Item 7 — OBS-04 request-id on every CloudWatch log line

- **Do:** Make a signed request to staging (`curl -H "Authorization: Bearer ..." https://staging.carmodpicker.com/api/users/me`). Note the `X-Request-ID` echo header from the response.
- **Verify:** In CloudWatch Logs Insights for `/aws/apprunner/.../application`:
  ```
  filter @message like /<the-request-id>/
  | sort @timestamp
  ```
- **Expected:**
  - [x] Every log line emitted during that request carries `request_id=<uuid>` OR the JSON log record has `"request_id": "<uuid>"` (depending on formatter)
  - [x] Any sqlalchemy query logs fired during that request also carry the same request_id (third-party propagation per D-48)
  - [x] Every log line during the request also has `user_id=<id>`, never `user_id=-`
- **Evidence:** Logs Insights query URL: _______

## Staging → Prod Promotion Gate (D-58)

All 7 UAT items above MUST be marked pass AND at least 24 hours MUST have elapsed since staging deploy AND zero unexplained Sentry events from staging during that window before prod apply.

- [x] Items 1-7 all checked pass
- [x] `staging_deploy_timestamp`: _______
- [x] `prod_apply_approved_at`: _______ (must be ≥ `staging_deploy_timestamp` + 24h)
- [x] Staging Sentry project shows no unexplained events during the bake window (test events from this UAT are expected)
- [x] Operator runs `terraform -chdir=terraform apply -var-file=prod.tfvars` after approval

## Deviation Log

- **D-24:** SNS → email (not SNS → SES). Operator impact: identical — email arrives at the same addresses. Noted for verifier traceability.
- **`var.environment` (not `var.app_environment`):** The plan's reference skeleton used `var.app_environment` for the alarm's dimension filter. The actual project variable is `var.environment` (declared in `terraform/variables.tf` with validation against `["production", "staging"]`). Production alarm in staging deploy will filter on `Environment=staging`; prod deploy will filter on `Environment=production`. Operator impact: none — behavior identical.
- **Terraform plan (staging dry-run):** Not executed by the executor agent because `db_password`, `secret_key`, `cron_secret_key` are `sensitive` inputs without defaults and AWS credentials were unavailable in the sandbox. `terraform validate` + `terraform fmt -check` both pass. Operator runs `terraform -chdir=terraform plan -var-file=staging.tfvars` as the first step of the staging deploy; the new alarm resource should appear under the "will be created" section.




user manually fully signs off — all 7 UAT items + promotion gate approved 2026-04-23