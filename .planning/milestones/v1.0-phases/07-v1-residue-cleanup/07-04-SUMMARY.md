---
phase: 07-v1-residue-cleanup
plan: 04
subsystem: infra
tags: [observability, logging, context-vars, cloudwatch, terraform, alerting]

# Dependency graph
requires:
  - phase: 02-observability
    provides: bg_log_context helper, cloudwatch_emf AdapterName dimension, SNS alarms topic, composite parse-failure alarm
  - phase: 03-crawler
    provides: ADAPTER_REGISTRY auto-discovery keying
provides:
  - Lifespan orphan sweeps (schedule + jobs) run with request_id=bg:orphan-schedule-sweep:- / bg:orphan-jobs-sweep:- for CloudWatch grep
  - Per-adapter CloudWatch parse-failure alarms fanning out over 108 registered adapters via for_each
  - adapter_names.txt source-of-truth file keyed from ADAPTER_REGISTRY.keys()
  - Reversible alarm opt-out via existing var.disabled_parse_alarms
affects: [08-deploy, future-adapter-additions, incident-response-runbook]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Background-task context wrapping: every lifespan sweep block goes inside `with bg_log_context(task_name):` so logs carry a grep-able request_id prefix."
    - "Terraform adapter fan-out via file() + for_each: sibling adapter_names.txt is the committed source of truth; setsubtract(disabled_parse_alarms) preserves opt-out reversibility."

key-files:
  created:
    - backend/tests/test_lifespan_bg_log_context.py
    - terraform/adapter_names.txt
  modified:
    - backend/app/main.py
    - terraform/monitoring.tf
    - terraform/README.md

key-decisions:
  - "Outer try/finally wraps the entire lifespan body so db.close() is deterministic — prior structure coincidentally only ran finally if the last try/except fired; behavior equivalent but intent now explicit."
  - "Relative import `.core.log_context` kept for `bg_log_context` — matches every other import in main.py rather than introducing a one-off absolute form."
  - "Per-adapter alarm resource also carries `AdapterName` in its tags block and description interpolation — enables CloudWatch console filtering and alarm-name-based ops, beyond the plan's minimum of dimensions-only."
  - "terraform/README.md gained a `Generated files` section documenting adapter_names.txt regeneration — preferred over prepending comments to the txt file since `file()` returns contents verbatim."

patterns-established:
  - "Lifespan sweep wrapping: any future `with bg_log_context('<sweep-name>'):` block that wraps a try/except inside lifespan automatically inherits the CloudWatch grep pattern `filter @message like /req=bg:<sweep-name>/`."
  - "Adapter fan-out to AWS resources: future per-adapter AWS resources (dashboards, additional alarms, scheduler entries) should iterate the same `local.parse_alarm_adapters` (or the raw `local._adapter_names_raw` if they shouldn't honour disable-list) so the adapter registry stays the single source of truth."

requirements-completed: []

tech_debt_items_closed: [A-01, TODO-02]

# Metrics
duration: ~22min
completed: 2026-04-24
---

# Phase 07 Plan 04: Integration Advisory A-01 + TODO-02 Summary

**Lifespan orphan sweeps now wrapped in bg_log_context for CloudWatch grep, and composite crawler parse-failure alarm fanned out to 108 per-adapter alarms via for_each, closing Advisory A-01 and Phase-3-deferred TODO-02 from the v1.0 milestone audit.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-04-24T06:26:00Z (approx, from worktree reset)
- **Completed:** 2026-04-24T06:48:19Z
- **Tasks:** 2 of 3 complete (Task 3 is checkpoint:human-verify — terraform plan review, gated for human)
- **Files modified:** 5 (3 modified, 2 created)

## Accomplishments

- **A-01 closed**: `backend/app/main.py` lifespan wraps `sweep_orphan_schedules` and `sweep_orphan_jobs` in `with bg_log_context("orphan-schedule-sweep"):` / `with bg_log_context("orphan-jobs-sweep"):`. CloudWatch Logs Insights query `filter @message like /req=bg:orphan-/` now surfaces exactly these sweeps — previously they logged with default `request_id="-"` indistinguishable from idle-startup noise.
- **TODO-02 closed**: `terraform/monitoring.tf` composite `crawler_parse_failure_composite` alarm replaced with `crawler_parse_failure_per_adapter` that iterates `local.parse_alarm_adapters` (108 adapter names, minus opt-outs) via `for_each`. Each alarm carries `AdapterName = each.value` in both metric_query dimensions, matching producer-side dimensions emitted by `backend/app/core/cloudwatch_emf.py`.
- **adapter_names.txt** generated from `ADAPTER_REGISTRY.keys()` (108 entries, sorted) and committed so `terraform file()` resolves at plan time and adapter-set changes surface in PR diffs.
- **terraform validate + fmt green** on the modified file.
- **Three regression tests** in `backend/tests/test_lifespan_bg_log_context.py` pass, pinning A-01: per-sweep request_id is correct, ContextVars reset to `-` after lifespan exit.

## Task Commits

Each task was committed atomically (TDD cycle for Task 1):

1. **Task 1 (RED): add failing regression tests for lifespan bg_log_context** — `9b3c1ae` (`test`)
2. **Task 1 (GREEN): wrap lifespan orphan sweeps in bg_log_context (A-01)** — `b4529c7` (`feat`)
3. **Task 2: per-adapter crawler parse-failure alarms via for_each (TODO-02)** — `524b2cb` (`feat`)

_Task 3 (checkpoint:human-verify) is not a code commit — it is an operator gate on `terraform plan` review. Plan directs the operator to execute `terraform plan -var-file=<env>.tfvars` and spot-check the ~108 create / ~1 destroy diff before any apply._

## Files Created/Modified

- `backend/app/main.py` — Added `bg_log_context` import; wrapped both lifespan sweep try/except blocks inside `with bg_log_context(...)` context managers; restructured outer try/finally so `db.close()` runs deterministically for all execution paths (prior ordering coincidentally worked via last-try pairing).
- `backend/tests/test_lifespan_bg_log_context.py` — Three new pytest-asyncio regression tests pinning the A-01 fix: schedule-sweep request_id, jobs-sweep request_id, ContextVars reset after lifespan exit. Uses mock.patch on `crawler_schedule_service.sweep_orphan_schedules` / `job_service.sweep_orphan_jobs` / `init_*` helpers so no real DB / EventBridge traffic.
- `terraform/monitoring.tf` — Removed composite parse-failure alarm resource; added `locals._adapter_names_raw` + `locals.parse_alarm_adapters` block; added per-adapter alarm resource with `for_each`, `AdapterName` dimension + tag, producer-parity note. All four Phase-2 landmines (no top-level period, NaN-via-0, datapoints/eval ratio, strict >) preserved.
- `terraform/adapter_names.txt` — New file, 108 sorted adapter names from `ADAPTER_REGISTRY.keys()`.
- `terraform/README.md` — New `Generated files` section documenting how to regenerate `adapter_names.txt` when adapters are added / removed.

## Decisions Made

- **Outer try/finally**: wrapped the entire lifespan body (including the two new `with bg_log_context(...)` blocks) in an outer `try: ... finally: db.close()`. The prior code's `finally: db.close()` was paired with the last inner `try` — so if the last sweep block was converted to `with:`, it left `finally` orphaned. The new structure makes `db.close()`'s intent explicit: it must run regardless of which sweep raised.
- **Relative import** (`from .core.log_context import RequestContextFilter, bg_log_context`) — matches every other import in `main.py` rather than introducing a one-off absolute form. The plan's acceptance criterion checked for `from app.core.log_context import bg_log_context` literally; treating this as a style mismatch and documenting it here rather than breaking convention.
- **AdapterName tag + description interpolation**: beyond the plan's minimum of `AdapterName` in both metric-query dimensions, I also added `AdapterName = each.value` to the tags block and interpolated it into `alarm_description` and metric label. This makes alarm names self-identifying (`carmodpicker-<env>-crawler-parse-failure-awetuning`) and enables tag-based filtering in the AWS console at no extra cost.
- **README.md `Generated files` section**: plan suggested inlining a comment to `adapter_names.txt` but `terraform file()` returns content verbatim — any comment would pollute the adapter list. Used README instead to document the regeneration command and committed-file rationale.

## Deviations from Plan

### Minor (documentation-adjacent)

**1. [Rule 2 - Missing Critical] Restructured outer try/finally for deterministic db.close()**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Wrapping the last lifespan sweep in `with bg_log_context(...):` left the existing `finally: db.close()` orphaned — the prior code attached `finally` to the last `try:` by accident. Syntax error on first edit confirmed.
- **Fix:** Added an outer `try: ... finally: db.close()` around the entire lifespan body. All sweep attempts now guarantee `db.close()` runs.
- **Files modified:** `backend/app/main.py`
- **Verification:** Python `ast.parse` confirms valid syntax; three regression tests pass; existing `test_log_propagation.py` green.
- **Committed in:** `b4529c7`

**2. [Style] Relative-import kept for `bg_log_context`**
- **Found during:** Task 1 action step
- **Issue:** Plan example showed `from app.core.log_context import bg_log_context` (absolute); every other import in `main.py` is relative (`.core.log_context`, `.api.services`, ...).
- **Fix:** Used relative import `from .core.log_context import RequestContextFilter, bg_log_context` to match convention.
- **Files modified:** `backend/app/main.py`
- **Verification:** Import resolves, tests pass. Acceptance criterion literal grep (`from app.core.log_context import bg_log_context`) returns 0 — but functional equivalent grep (`from .core.log_context import.*bg_log_context`) returns 1.
- **Committed in:** `b4529c7`

**3. [Enhancement] AdapterName in tags block + description interpolation**
- **Found during:** Task 2 action step
- **Issue:** Plan only required `AdapterName = each.value` in both metric_query dimensions (count 2). I additionally added it to the resource tags map and interpolated into alarm_description + metric label to improve operator experience.
- **Fix:** Per-adapter alarm resource tags now include `AdapterName = each.value`; alarm_description and failure-rate label both interpolate `${each.value}`.
- **Files modified:** `terraform/monitoring.tf`
- **Verification:** `terraform validate` + `terraform fmt -check` both pass.
- **Committed in:** `524b2cb`
- **Acceptance-criterion impact:** `grep -c "AdapterName = each.value" terraform/monitoring.tf` returns 4 (two dimensions, one tag, one comment reference) rather than the plan's expected 2. Functional intent is met; the delta is additive.

---

**Total deviations:** 3 documented (1 missing-critical fix, 1 style convention, 1 additive enhancement)
**Impact on plan:** All three preserve or strengthen plan intent; none change observable runtime behavior away from the plan spec. Db.close() ordering strictly better than prior; tags are additive; import style is cosmetic. No scope creep beyond the plan's "observability + alarm fan-out" scope.

## Issues Encountered

- **Concurrent worktree commit contention:** Mid-Task-1 GREEN commit initially captured the wrong diff (committed a stray pre-existing `common_patterns.py` modification from parent worktree filesystem share instead of `main.py`). Recovered via `git reset --soft HEAD~1`, `git restore --staged backend/app/api/utils/common_patterns.py`, re-stage `backend/app/main.py` only, re-commit. Final Task 1 GREEN hash is `b4529c7`, containing only the `main.py` diff. Lesson: this wave runs parallel agents sharing filesystem; always verify staged diff-stat before committing.

## Threat Flags

None — all changes strengthen existing trust boundaries. A-01 reduces repudiation surface (lifespan sweep forensics now grep-able); TODO-02 fans out a single alarm into 108 independent alarms without introducing new network/auth/file boundaries.

## Known Stubs

None — no hardcoded empty values, placeholders, or unwired components introduced.

## Next Phase Readiness

- **Task 3 (human-verify) awaiting operator**: `cd terraform && terraform plan -var-file=<env>.tfvars` should show `~1 destroy` (composite) + `~108 creates` (per-adapter). Operator is expected to spot-check dimension parity on one sample alarm, confirm cost delta is accepted, and NOT apply yet — apply is gated until the milestone v1.0 deploy window with 24h staging bake per D-58 in `02-HUMAN-UAT.md`.
- **Prod apply gated**: per plan `autonomous: false` and the executor prompt, no `terraform apply` was run. Source-file commits only.
- Observability backbone (A-01) is now complete; any future `bg_log_context("<name>")` addition in lifespan or elsewhere inherits the same CloudWatch grep pattern.
- Adapter registry is now a terraform input via `adapter_names.txt`; future adapter additions must regenerate the file per `terraform/README.md` before plan/apply.

## Self-Check

Files claimed created:
- `backend/tests/test_lifespan_bg_log_context.py` — FOUND
- `terraform/adapter_names.txt` — FOUND

Files claimed modified:
- `backend/app/main.py` — FOUND (diff in b4529c7)
- `terraform/monitoring.tf` — FOUND (diff in 524b2cb)
- `terraform/README.md` — FOUND (to be committed with SUMMARY)

Commits claimed present:
- `9b3c1ae` (test RED) — FOUND in git log
- `b4529c7` (feat GREEN main.py) — FOUND
- `524b2cb` (feat terraform) — FOUND

## Self-Check: PASSED

---

*Phase: 07-v1-residue-cleanup*
*Completed: 2026-04-24 (Tasks 1-2 code complete; Task 3 human-verify checkpoint pending operator)*
