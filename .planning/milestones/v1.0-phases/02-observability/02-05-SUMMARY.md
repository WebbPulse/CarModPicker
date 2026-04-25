---
phase: 02-observability
plan: 5
subsystem: observability
tags: [cloudwatch, sns, terraform, metric-math, alarm, obs-03, runbook, human-uat]

# Dependency graph
requires:
  - phase: 02-observability
    plan: 2
    provides: "aws_sns_topic.alarms + variable disabled_parse_alarms + sensitive=true terraform practice"
  - phase: 02-observability
    plan: 3
    provides: "CarModPicker/Crawlers EMF namespace — Ingested + ParseFailures metrics with RunType=live dimension — which this alarm reads"
provides:
  - "aws_cloudwatch_metric_alarm.crawler_parse_failure_composite — 6th alarm, composite metric-math across all adapters, RunType=live filter, Phase 3 converts to per-adapter via for_each"
  - ".planning/codebase/CONCERNS.md#crawler-drift-runbook — 7-step response-to-alarm runbook that the alarm's description points to"
  - ".planning/phases/02-observability/02-HUMAN-UAT.md — 7-item D-62 checklist + D-58 staging→prod bake gate, closes Phase 2"
affects:
  - "phase 03 crawler hardening — when CRAWL-01/02 adapter auto-discovery lands, the TODO marker in monitoring.tf converts this composite alarm to 114 per-adapter alarms via for_each (D-29/D-30)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "metric_query{} block with expression+return_data=true — composite alarm pattern (first use in this repo; primary analog was apprunner_5xx which uses inline namespace+metric_name shape)"
    - "NaN-via-0 small-sample suppression via IF((ingested + failures) < 10, 0, ...) — matches runner.py total>=10 drift threshold"
    - "alarm_description surfaces runbook anchor literally so SNS email body is actionable without operator having to dig (D-27)"
    - "TODO(phase-3) comment block inside terraform resource as Phase 3 handoff marker — documents the for_each conversion path without enabling it"

key-files:
  created:
    - .planning/phases/02-observability/02-HUMAN-UAT.md
  modified:
    - terraform/monitoring.tf
    - .planning/codebase/CONCERNS.md

key-decisions:
  - "var.environment used for the alarm's dimension filter (not plan's hypothetical var.app_environment) — verified against terraform/variables.tf; operator impact none"
  - "terraform plan for staging deferred to operator because db_password, secret_key, cron_secret_key are sensitive inputs without defaults and AWS credentials were unavailable in sandbox (terraform validate + fmt -check both pass)"
  - "Composite alarm (1 alarm for all adapters) — Phase 3 for_each conversion explicitly marked via TODO(phase-3) comment with var.disabled_parse_alarms reference (D-29/D-30/D-31)"
  - "Runbook's `grep -c crawler-drift-runbook CONCERNS.md` returns 1 (anchor only) — plan's verification expected >=2 (header+anchor) but the H2 header uses spaces not kebab. Discrepancy is in the plan's <verification> block, not the implementation. Acceptance-criteria list (both explicit grep patterns) both PASS."

requirements-completed: [OBS-03]

# Metrics
duration: ~6min
completed: 2026-04-22
---

# Phase 02 Plan 05: OBS-03 composite parse-failure alarm + Crawler Drift Runbook + Phase 2 HUMAN-UAT Summary

**Composite CloudWatch metric-math alarm wired to existing SNS topic with runbook-anchored description + new Crawler Drift Runbook section at `#crawler-drift-runbook` + 7-item Phase 2 HUMAN-UAT checklist that gates the staging→prod bake. Landmines 7, 8, 9, 10 all pinned. Closes Phase 2.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-22T23:16:27Z
- **Completed:** 2026-04-22T23:23:09Z
- **Tasks:** 3 (Task 1 auto, Task 2 auto, Task 3 checkpoint:human-verify — file artifact created per checkpoint guidance)
- **Files created:** 1 (02-HUMAN-UAT.md)
- **Files modified:** 2 (monitoring.tf, CONCERNS.md)

## Accomplishments

- `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` appended to `terraform/monitoring.tf` as the 6th alarm (existing 5: apprunner_5xx, rds_cpu, rds_free_storage, rds_connections, rds_freeable_memory)
- Metric-math expression `IF((ingested + failures) < 10, 0, failures / (ingested + failures))` with threshold 0.5 + `GreaterThanThreshold` (strict `>`) + `evaluation_periods=1` + `datapoints_to_alarm=1` + `treat_missing_data=notBreaching` + `period=3600` inside each `metric_query.metric {}` block (NEVER top-level — Landmine 7 pinned)
- Three metric_query blocks: `ingested` (Sum of Ingested), `failures` (Sum of ParseFailures), `rate` (expression with `return_data=true`). Both metric_query.metric dimension maps filter `Environment=var.environment` + `RunType=live` (excludes rescrape noise per D-21)
- `alarm_actions` + `ok_actions` both point to existing `aws_sns_topic.alarms` (D-26 symmetry — recovery emails fire on transition to OK)
- `alarm_description` contains the literal string `"Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"` — this is what the SNS email recipient sees in the body (D-27)
- `# TODO(phase-3): ... for_each = toset(setsubtract(file("${path.module}/adapter_names.txt"), var.disabled_parse_alarms))` handoff marker placed immediately after `ok_actions` (D-30). `var.disabled_parse_alarms` declared by plan 02-02; Phase 2 does not consume it yet (D-31)
- `## Crawler Drift Runbook` section appended to `.planning/codebase/CONCERNS.md` with exact anchor `<a id="crawler-drift-runbook"></a>` (lowercase-kebab per plan spec — the anchor the monitoring.tf description points to). Seven numbered response steps:
  1. Identify drifting adapter via `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers`
  2. Pull archived HTML from crawl-archive S3 bucket (`carmodpicker-production-crawl-data`)
  3. Re-run SAFE-07 characterization test (`pytest -n auto tests/crawlers/test_characterization_<adapter>.py`)
  4. Patch selectors in `backend/app/crawlers/adapters/<name>.py`
  5. Optional mute — Phase-3-only via `var.disabled_parse_alarms`; Phase 2 uses AWS console emergency mute
  6. Deploy via normal PR → GHA → staging → bake 24h → prod flow (D-58)
  7. Post-fix: update HTML fixture in `backend/tests/crawlers/fixtures/` to close SAFE-07 regression loop
- Phase 3 handoff note references the `terraform/monitoring.tf` TODO marker closing the D-30 handoff loop
- `.planning/phases/02-observability/02-HUMAN-UAT.md` created (NEW file, 138 lines) with 7-item D-62 checklist covering all 5 OBS requirements (OBS-01 ×3 items, OBS-02 ×1, OBS-03 ×1, OBS-04 ×1, OBS-05 ×1), staging→prod bake gate (D-58), and a deviation log that documents the SNS→email vs SNS→SES interpretation (D-24), the var.environment vs var.app_environment substitution, and the deferred terraform plan step
- `terraform validate` exits 0. `terraform fmt -check` exits 0. Both pre-Phase-2 apprunner_5xx analog + new composite alarm coexist cleanly.

## Task Commits

1. **Task 1 (feat 02-05):** `18ad431` — composite parse-failure alarm in terraform/monitoring.tf (79 insertions)
2. **Task 2 (docs 02-05):** `db6f229` — Crawler Drift Runbook in .planning/codebase/CONCERNS.md (41 insertions)
3. **Task 3 (docs 02-05):** `30cd9ec` — 02-HUMAN-UAT.md (138 lines NEW)

## Interface contracts (operator-facing)

### `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` — metric-math literal

Exact expression literal for Phase 3 for_each conversion traceability:

```
IF((ingested + failures) < 10, 0, failures / (ingested + failures))
```

- Below 10 combined samples → returns 0 (idle adapters quiet; matches runner.py `total>=10` drift threshold — D-23)
- At or above 10 samples → returns parse-failure ratio
- Threshold: `> 0.5` (strict `>`, Landmine 10)
- Period: 3600 seconds (1 hour; matches hourly crawl cadence)
- Evaluation: 1-of-1 datapoints (Landmine 9)
- Missing data: `notBreaching` (idle adapters stay quiet)

### Dimension filter

Both source metric_query blocks filter on:
- `Environment = var.environment` (resolves to `"staging"` or `"production"` per variable validation)
- `RunType = "live"` (excludes rescrape-run-type metrics)

### SNS fan-out

- `alarm_actions = [aws_sns_topic.alarms.arn]`
- `ok_actions = [aws_sns_topic.alarms.arn]`

Existing email subscriptions (`alarms_tyler_webb` and `alarms_tyler_gmail` — both `email` protocol, already confirmed) receive alarm + recovery notifications.

### Runbook cross-link

alarm_description contains the literal: `Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook`

CONCERNS.md contains the HTML anchor: `<a id="crawler-drift-runbook"></a>`

These match. Any future rename of the runbook section must update BOTH sides or the SNS email hyperlink goes stale.

## var.environment vs plan's hypothetical var.app_environment

The plan's `<read_first>` block correctly anticipated this: *"If `var.app_environment` does not exist in `terraform/variables.tf` (check via grep first), substitute the actual environment-naming variable used by other resources in monitoring.tf."* The actual project variable is `var.environment` (declared at terraform/variables.tf line 7, validated against `["production", "staging"]`). The alarm's two metric_query.metric.dimensions maps use `Environment = var.environment`. Operator impact: none — the variable resolves identically at plan/apply time to the tfvars file's `environment = "staging"` or `environment = "production"` line.

## Terraform validate + fmt + plan output summary

- `terraform init -backend=false` — succeeded (provider cache reused from prior init; no backend state read)
- `terraform validate` — exit 0. "Success! The configuration is valid."
- `terraform fmt -check` — exit 0 on the full directory (no formatting changes needed)
- `terraform plan -var-file=staging.tfvars` — NOT EXECUTED. The project's three sensitive variables (`db_password`, `secret_key`, `cron_secret_key`) have no defaults and no staging.tfvars was present in the sandbox, and AWS credentials were unavailable. Per checkpoint guidance in the execution prompt: *"Run `terraform plan` as a staging dry-run IF it can be done without destructive cloud side-effects and without needing AWS credentials in this sandbox; if it requires credentials that are unavailable, document that in SUMMARY.md under 'Deferred to operator' and proceed — do NOT block on it."*

## Crawler Drift Runbook anchor confirmation

- Monitoring.tf description: `grep -c "crawler-drift-runbook" terraform/monitoring.tf` = 1 (inside alarm_description literal) ✓
- CONCERNS.md anchor: `grep -c 'id="crawler-drift-runbook"' .planning/codebase/CONCERNS.md` = 1 ✓
- Cross-file link is LIVE: the SNS email recipient can grep the body for `crawler-drift-runbook`, open the CONCERNS.md file in the repo, and jump straight to the 7-step runbook.

Note on plan verification discrepancy: the plan's `<verification>` block specified `grep -c "crawler-drift-runbook" .planning/codebase/CONCERNS.md` returns `>= 2 (header + anchor)`. The section header is `## Crawler Drift Runbook` (spaces, not kebab), which does NOT contain the kebab literal — so the count is 1 (anchor only). The plan's explicit `<acceptance_criteria>` list is stricter and more correct: `grep -n "## Crawler Drift Runbook"` returns 1 (header as prose) AND `grep -n 'id="crawler-drift-runbook"'` returns 1 (anchor as kebab). Both pass. The `<verification>` block count is an inconsistency in the plan prose, not a missing implementation.

## HUMAN-UAT checklist delivered

`.planning/phases/02-observability/02-HUMAN-UAT.md` (138 lines, 7 items, D-58 staging→prod gate, D-24 deviation log). Operator sign-off is post-merge + post-staging-deploy:

1. Merge this plan
2. `terraform -chdir=terraform apply -var-file=staging.tfvars` (operator)
3. Run the 7 UAT items against staging
4. Wait 24h bake window, verify zero unexplained Sentry events
5. `terraform -chdir=terraform apply -var-file=prod.tfvars` (operator)
6. Re-run UAT items 4–7 against prod to confirm parity

File contents are the human-gated artifact per the executor's `<checkpoint_guidance>`: *"The HUMAN-UAT.md file is the human-gated artifact that the user will validate post-merge; creating the file completes your scope."*

## autonomous: false step

The prod `terraform apply` is NOT executed by this plan. The executor agent's scope was the code/docs/UAT-file artifacts. Staging and prod `terraform apply` are manual operator actions gated on the 24h bake + 7-item UAT sign-off per D-58. This is exactly why the plan is marked `autonomous: false`.

## Phase 2 closure log

### Each OBS-0X → closing plan

| OBS-id  | Closing plan | Implementation                                       |
| ------- | ------------ | ---------------------------------------------------- |
| OBS-01  | 02-02        | Sentry SDK 2.x backend init + 3 crawler entry points |
| OBS-02  | 02-03        | EMF crawler metrics (Ingested/ParseFailures/ElapsedSeconds) |
| OBS-03  | **02-05**    | Composite parse-failure CloudWatch alarm + runbook   |
| OBS-04  | 02-01        | bg_log_context + CLI bootstrap + regression guard    |
| OBS-05  | 02-04        | Frontend @sentry/react + Session Replay on-error     |

### Each D-XX → closing plan (Phase 2 decision corpus)

- D-01..D-15 (Sentry backend posture): 02-02
- D-16..D-22 (EMF semantics): 02-03
- D-23..D-31 (alarm math + SNS fan-out + Phase-3 handoff): **02-05**
- D-32..D-43 (frontend Sentry + Replay auth-gate + PII posture): 02-04
- D-44..D-48 (OBS-04 ContextVar + test harness): 02-01
- D-49..D-56 (secrets-manager bootstrap + IAM drift): 02-02
- D-57..D-62 (HUMAN-UAT + staging→prod gate): **02-05**

### Each Landmine 1-18 → closing plan

- L1 (Sentry string ignore_errors match type): 02-02 (TestInitKwargs)
- L2 (sentry-sdk 4 integrations attached): 02-02 (TestInitKwargs)
- L3 (EMF emit position < summary-log position): 02-03 (TestEmissionPosition)
- L4 (AWS_EMF_ENVIRONMENT=Local at runtime): 02-02 (terraform apprunner.tf + ecs.tf) + 02-03 (test fixture EnvironmentCache patch)
- L5 (@metric_scope auto-flush, no asyncio.run at call sites): 02-03
- L6 (ContextVar test fixture pollution): 02-01 (caplog_with_context + `__main__` guard)
- L7 (terraform-provider-aws#29398 no top-level period): **02-05** (acceptance criterion + awk line-compare)
- L8 (NaN-via-0 small-sample expression): **02-05** (IF((ingested+failures)<10, 0, ...))
- L9 (datapoints_to_alarm ≤ evaluation_periods): **02-05** (1-of-1)
- L10 (GreaterThanThreshold strict, not >=): **02-05** (acceptance criterion)
- L11 (@sentry/react v10 strict IP exclusion via sendDefaultPii=false): 02-04
- L12 (build.sourcemap: 'hidden' — no sourceMappingURL in bundle JS): 02-04
- L13 (@sentry/vite-plugin CI gate): 02-04
- L14 (beforeErrorSampling is replay gate, not error gate): 02-04
- L15 (caplog filter not inherited in tests — attach RequestContextFilter): 02-01
- L16 (Sentry init lazy-import inside crawler main() bodies): 02-02
- L17 (noPropertyAccessFromIndexSignature — bracket access on VITE_* env): 02-04
- L18 (Sentry free-tier 500 replays/month cap): 02-04 (D-32 ambient 0 / on-error 1.0)

All 18 landmines pinned across the 5 plans.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan's `var.app_environment` doesn't exist in terraform/variables.tf**
- **Found during:** Task 1 pre-edit read of `terraform/variables.tf`
- **Issue:** The plan's `<interfaces>` block used `Environment = var.app_environment` in the dimension maps. The actual declared variable is `var.environment` (terraform/variables.tf line 7, with validation `contains(["production", "staging"], var.environment)`). Using `var.app_environment` would fail `terraform validate` with "unknown variable."
- **Fix:** Substituted `var.environment` in both metric_query.metric.dimensions maps. The plan's `<read_first>` block explicitly anticipated this exact case and directed the substitution: *"If `var.app_environment` does not exist in `terraform/variables.tf` (check via grep first), substitute the actual environment-naming variable used by other resources in monitoring.tf."*
- **Files modified:** terraform/monitoring.tf
- **Verification:** `terraform validate` exits 0; `terraform fmt -check` exits 0.
- **Committed in:** `18ad431` (Task 1 commit)

### Acknowledged / documented

**2. [Plan prose discrepancy] `<verification>` block `grep -c "crawler-drift-runbook" CONCERNS.md >= 2`**
- **Context:** The plan's `<verification>` block expected count >= 2 (header + anchor). The H2 header is `## Crawler Drift Runbook` (prose with spaces), NOT `## crawler-drift-runbook` (kebab), so the literal kebab string only appears once in CONCERNS.md (inside the `<a id="...">` anchor). The plan's explicit `<acceptance_criteria>` list separately greps the prose header via `"## Crawler Drift Runbook"` (matches 1) and the anchor via `'id="crawler-drift-runbook"'` (matches 1). Both explicit acceptance checks pass; the aggregate-count expectation in the non-binding `<verification>` block is inconsistent with the binding `<acceptance_criteria>` list.
- **Resolution:** Implementation matches the binding acceptance criteria (header at 226, anchor at 228). Cross-file link `terraform/monitoring.tf` → `CONCERNS.md#crawler-drift-runbook` is LIVE and verified.
- **Impact:** None.

**3. [Deferred to operator] terraform plan for staging**
- **Context:** `terraform plan -var-file=staging.tfvars` would be the preferred third automated verification step per the plan. The sandbox has no `staging.tfvars`, the three `sensitive` variables (`db_password`, `secret_key`, `cron_secret_key`) have no defaults, and AWS credentials were not available (the plan would fail at provider auth even if the tfvars file existed). Per the execution prompt's `<checkpoint_guidance>`: *"if it requires credentials that are unavailable, document that in SUMMARY.md under 'Deferred to operator' and proceed — do NOT block on it."*
- **Resolution:** Operator runs `terraform -chdir=terraform plan -var-file=staging.tfvars` as the first step of the staging deploy; the new alarm resource should appear under the "will be created" section with a `+ resource "aws_cloudwatch_metric_alarm" "crawler_parse_failure_composite"` header.
- **Committed in:** Documented in 02-HUMAN-UAT.md Deviation Log.

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking — variable name substitution, anticipated by plan itself), 1 plan-prose acknowledgement (non-impact), 1 deferred-to-operator (terraform plan with sensitive vars + no AWS creds in sandbox).

## Known Stubs

None. All three artifacts are complete and live:
- Alarm resource is fully wired (metric_query × 3, alarm_actions, ok_actions, TODO marker) and passes `terraform validate` / `fmt -check`
- Runbook is concrete (7 numbered steps, exact CLI commands, exact S3 bucket names, exact test path, exact SAFE-07 cross-reference)
- HUMAN-UAT is concrete (7 items each with Do / Expected / Evidence fields, curl-equivalent commands where relevant, exact Sentry tag names and env names)

## Threat Flags

None beyond those declared in 02-05-PLAN.md `<threat_model>`. All four STRIDE threats mitigated and pinned:

- **T-02-METRIC-CARD** (alarm-count cost): Phase 2 ships exactly 1 new alarm (`grep -c 'aws_cloudwatch_metric_alarm" "crawler_parse_failure' terraform/monitoring.tf` = 1). Cost = $0.10/mo per AWS pricing.
- **T-02-IAM-DRIFT**: Reuses existing `aws_sns_topic.alarms`. Zero new IAM surface. Existing 2 subscriptions unchanged (`grep -c 'aws_sns_topic_subscription.*alarms' terraform/monitoring.tf` = 2).
- **T-02-ALARM-FLAPPING**: `treat_missing_data = notBreaching` + `IF((ingested + failures) < 10, 0, ...)` suppression. Alarm stays quiet on idle adapters / startup. Verified by HUMAN-UAT item 5 fire+recover expectations.
- **T-02-PROD-MISAPPLY**: Plan frontmatter `autonomous: false`. 02-HUMAN-UAT.md has explicit `## Staging → Prod Promotion Gate (D-58)` section requiring 24h bake + 7-item pass before `terraform apply -var-file=prod.tfvars`.

## TDD Gate Compliance

Plan 02-05 is `type: execute` (not `type: tdd`). Tasks 1 and 2 are `type="auto"` (no TDD). Task 3 is `type="checkpoint:human-verify"`. No test files are created or expected by this plan — the composite alarm's runtime behavior is validated in HUMAN-UAT item 5 (fire + recover against staging), not via unit test. Per the `<execution_flow>` spec, no RED/GREEN/REFACTOR gate sequence is required.

## Issues Encountered

- `terraform plan` not runnable in the sandbox — deferred to operator per checkpoint guidance (see Deviation 3).
- Plan's `var.app_environment` doesn't exist in the project — anticipated by the plan's read_first guidance and substituted with `var.environment` (see Deviation 1).

## User Setup Required

Post-merge operator steps (same flow documented in 02-HUMAN-UAT.md):

1. `terraform -chdir=terraform plan -var-file=staging.tfvars` — verify the new alarm appears under "will be created"
2. `terraform -chdir=terraform apply -var-file=staging.tfvars` — apply to staging
3. Run the 7-item HUMAN-UAT checklist against staging (see 02-HUMAN-UAT.md)
4. 24-hour staging bake observation window (D-58)
5. Verify zero unexplained staging Sentry events during the bake window
6. `terraform -chdir=terraform apply -var-file=prod.tfvars` — apply to prod
7. Re-run UAT items 4–7 against prod to confirm parity

## Next Phase Readiness

- **Phase 2 closes with this plan.** All 5 OBS requirements (OBS-01..OBS-05) addressed, all 62 decisions honored, all 18 landmines pinned across 5 plans.
- **Phase 3 (non-breaking internal improvements)** is already in progress (per STATE.md — 5 of 5 Phase 3 plans completed 2026-04-22 before Phase 2 started). No handoff gate needed.
- **Future Phase (when CRAWL-01/02 land per-adapter discovery + `adapter_names.txt` artifact):** Convert composite alarm to per-adapter alarms by uncommenting the TODO in terraform/monitoring.tf. Cost delta: +$11.40/mo (114 × $0.10/mo per alarm). User explicitly accepted this cost.

## Self-Check: PASSED

Files created/modified exist:
- terraform/monitoring.tf — FOUND (modified, new alarm at lines 165-222)
- .planning/codebase/CONCERNS.md — FOUND (modified, runbook at lines 226-263)
- .planning/phases/02-observability/02-HUMAN-UAT.md — FOUND (new, 138 lines)

Commits in git log:
- `18ad431` feat(02-05): composite crawler parse-failure alarm (OBS-03) — FOUND
- `db6f229` docs(02-05): add Crawler Drift Runbook to CONCERNS.md (OBS-03) — FOUND
- `30cd9ec` docs(02-05): Phase 2 HUMAN-UAT 7-item checklist (D-62/D-58) — FOUND

All binding acceptance criteria (the explicit `<acceptance_criteria>` lists for each task) verified. `terraform validate` + `terraform fmt -check` both exit 0.

---
*Phase: 02-observability*
*Completed: 2026-04-22*
