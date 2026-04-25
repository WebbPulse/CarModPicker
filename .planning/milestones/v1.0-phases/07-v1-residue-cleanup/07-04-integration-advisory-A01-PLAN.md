---
phase: 07
plan: 04
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/main.py
  - terraform/monitoring.tf
  - terraform/adapter_names.txt
  - backend/tests/test_lifespan_bg_log_context.py
# terraform apply to prod gates on human review after plan check (parse-failure alarm fan-out from 1 -> ~114 alarms is user-visible cost change: $11.40/mo)
autonomous: false
tech_debt_items:
  - A-01    # bg_log_context unused in production (main.py:102-132 lifespan orphan-job sweep)
  - TODO-02 # terraform/monitoring.tf:216 per-adapter for_each TODO (phase-3 for_each conversion was deferred; Phase 07 owns it)
must_haves:
  truths:
    - "`backend/app/main.py` lifespan function wraps the orphan-EventBridge-schedule sweep in `bg_log_context(\"orphan-schedule-sweep\")`"
    - "`backend/app/main.py` lifespan function wraps the orphan-background-jobs sweep in `bg_log_context(\"orphan-jobs-sweep\")`"
    - "A regression test asserts that any exception raised inside the sweep blocks has `request_id` set to `bg:orphan-schedule-sweep:-` / `bg:orphan-jobs-sweep:-` via the `RequestContextFilter`, not the default `-`"
    - "`terraform/monitoring.tf` `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` is replaced with a `for_each`-driven per-adapter alarm block reading from `terraform/adapter_names.txt`"
    - "`terraform plan` (local, without AWS creds) parses cleanly; `terraform validate` exits 0"
    - "TODO marker at `terraform/monitoring.tf:216` is resolved (removed or repositioned as a historical note on the new resource)"
  artifacts:
    - path: "backend/app/main.py"
      provides: "Lifespan orphan sweeps now run under bg_log_context — CloudWatch log grep `filter @message like /req=bg:orphan-/` finds the sweeps"
      contains: "bg_log_context(\"orphan-schedule-sweep\")"
    - path: "terraform/monitoring.tf"
      provides: "Per-adapter parse-failure alarm fan-out via for_each over adapter_names.txt; composite alarm removed"
      contains: "for_each = toset("
    - path: "terraform/adapter_names.txt"
      provides: "Newline-separated list of 114 adapter ADAPTER_NAME values (matches ADAPTER_REGISTRY keys at 2026-04-24)"
      min_lines: 108
    - path: "backend/tests/test_lifespan_bg_log_context.py"
      provides: "Regression that proves the lifespan sweep blocks use bg_log_context — RequestContextFilter reads the bg:orphan-* request_id values"
      min_lines: 50
  key_links:
    - from: "backend/app/main.py::lifespan"
      to: "backend/app/core/log_context.py::bg_log_context"
      via: "with bg_log_context(\"orphan-schedule-sweep\"):"
      pattern: "bg_log_context\\("
    - from: "terraform/monitoring.tf::aws_cloudwatch_metric_alarm.crawler_parse_failure_per_adapter"
      to: "terraform/adapter_names.txt"
      via: "for_each = toset(setsubtract(split(\"\\n\", trimspace(file(\"${path.module}/adapter_names.txt\"))), var.disabled_parse_alarms))"
      pattern: "file\\(\".*adapter_names\\.txt\"\\)"
---

<objective>
Close two cross-cutting tech-debt items:
1. **A-01** — `bg_log_context` is defined in `backend/app/core/log_context.py` but not invoked in `backend/app/`, so the lifespan orphan-job sweeps at `main.py:102-132` log with `request_id="-"`. This plan wires `bg_log_context` into both sweep blocks so CloudWatch grep `filter @message like /req=bg:orphan-/` finds them.
2. **TODO-02** — `terraform/monitoring.tf:216` has a phase-3 TODO marker to convert the composite parse-failure alarm to per-adapter via `for_each`. Phase 3 deferred; this plan resolves it.

Purpose: Both items are documented in `.planning/v1.0-INTEGRATION-CHECK.md` §Advisory A-01 and `.planning/v1.0-MILESTONE-AUDIT.md` Phase 02 item 2 (TODO at `terraform/monitoring.tf:216`). Closing them removes the last two integration-advisory items before milestone close.

Output: `main.py` lifespan wrapped with bg_log_context around both sweep blocks; `terraform/monitoring.tf` converted to per-adapter `for_each` with operator-visible resource set; `adapter_names.txt` seeded with the 108 registered adapter names.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/v1.0-MILESTONE-AUDIT.md
@.planning/v1.0-INTEGRATION-CHECK.md
@CLAUDE.md

<interfaces>
### `bg_log_context` signature (backend/app/core/log_context.py:17-34)
```python
@contextmanager
def bg_log_context(task_name: str, job_id: str | None = None) -> Generator[None, None, None]:
    """Set request_id + user_id ContextVars for a background task scope.

    On enter: request_id = "bg:{task_name}:{job_id or '-'}", user_id = "bg".
    On exit: ContextVars are reset via token (re-entrant-safe).
    """
    rid_token = request_id_var.set(f"bg:{task_name}:{job_id or '-'}")
    uid_token = user_id_var.set("bg")
    try:
        yield
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)
```

### Current lifespan block in `backend/app/main.py` (lines 86-127)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        init_crawler_service_account(db)
    except Exception:
        logger.exception("Failed to initialize service accounts on startup")
    try:
        init_crawler_adapter_configs(db)
    except Exception:
        logger.exception("Failed to initialize crawler adapter configs on startup")
    try:
        init_car_generations(db)
    except Exception:
        logger.exception("Failed to initialize car generations on startup")
    try:
        # Best-effort: delete EventBridge schedules under our prefix that no
        # longer correspond to a live crawler_schedules row. Also cleans up
        # legacy per-adapter schedules from the previous implementation.
        swept = crawler_schedule_service.sweep_orphan_schedules(db)
        if swept:
            logger.info("Swept %d orphan EventBridge schedule(s) on startup", len(swept))
    except Exception:
        logger.exception("Orphan EventBridge schedule sweep failed on startup")
    try:
        # Any background_jobs row still in "running" but owned by a previous
        # worker_instance_id (or lacking one) can only exist because the prior
        # process was killed mid-job — uvicorn --reload, SIGKILL, crash,
        # redeploy. Mark those failed so the admin UI doesn't show phantom
        # running jobs forever. ECS-backed jobs are skipped.
        orphans = job_service.sweep_orphan_jobs(db, current_worker_instance_id=WORKER_INSTANCE_ID)
        if orphans:
            logger.warning(
                "Marked %d stale background job(s) as failed on startup (ids=%s)",
                len(orphans),
                [str(o.id) for o in orphans],
            )
    except Exception:
        logger.exception("Orphan background-job sweep failed on startup")
    finally:
        db.close()
    yield
```

### Current terraform composite alarm (terraform/monitoring.tf:165-220)
```hcl
resource "aws_cloudwatch_metric_alarm" "crawler_parse_failure_composite" {
  alarm_name        = "${local.prefix}-crawler-parse-failure-composite"
  alarm_description = "Parse-failure rate >50% across all live-mode crawlers. Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 0.5
  treat_missing_data  = "notBreaching"
  metric_query {
    id = "ingested"
    metric {
      metric_name = "Ingested"
      namespace   = "CarModPicker/Crawlers"
      period      = 3600
      stat        = "Sum"
      dimensions = {
        Environment = var.environment
        RunType     = "live"
      }
    }
  }
  metric_query {
    id = "failures"
    metric {
      metric_name = "ParseFailures"
      namespace   = "CarModPicker/Crawlers"
      period      = 3600
      stat        = "Sum"
      dimensions = {
        Environment = var.environment
        RunType     = "live"
      }
    }
  }
  metric_query {
    id          = "rate"
    expression  = "IF((ingested + failures) < 10, 0, failures / (ingested + failures))"
    label       = "Parse failure rate (suppressed below 10 samples)"
    return_data = true
  }
  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  # TODO(phase-3): convert composite alarm to per-adapter via:
  #   for_each = toset(setsubtract(file("${path.module}/adapter_names.txt"), var.disabled_parse_alarms))
  # after CRAWL-01/02 adapter auto-discovery lands; add AdapterName dimension
  # to each metric_query.metric.dimensions map. Cost: 114 alarms x $0.10/mo = $11.40/mo.
}
```

### Existing `var.disabled_parse_alarms` (terraform/variables.tf:146-150)
```hcl
variable "disabled_parse_alarms" {
  description = "Adapter names to exclude from per-adapter parse-failure alarms..."
  type        = list(string)
  default     = []
}
```

### ADAPTER_REGISTRY count at planning time (2026-04-24)
`python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; print(len(ADAPTER_REGISTRY))"` → 108. There are 114 `.py` files under `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/` — non-adapter scaffolding accounts for the 114 vs 108 gap. The alarm must iterate the 108 ADAPTER_NAME values, not the 114 filenames.

### Existing tests that exercise lifespan (for reference only, do NOT modify them)
- `backend/tests/test_log_propagation.py` — has `bg_log_context` unit tests at lines 123-155; these verify the helper in isolation.
- `backend/tests/test_health_endpoint.py` — exercises the `/health` + `/ready` path which runs after lifespan completes.

### ADAPTER_REGISTRY iteration pattern (for the one-shot script to generate adapter_names.txt)
```python
from app.crawlers.adapters import ADAPTER_REGISTRY
for name in sorted(ADAPTER_REGISTRY.keys()):
    print(name)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: A-01 — wrap lifespan orphan sweeps in bg_log_context</name>

  <read_first>
    - backend/app/main.py  (lines 85-130 — current lifespan function; note the two try/except blocks that need wrapping)
    - backend/app/core/log_context.py  (confirm bg_log_context signature and that task_name is a required positional arg)
    - backend/tests/test_log_propagation.py  (lines 120-160 — existing bg_log_context unit-test pattern; reuse its style for the new regression test)
    - .planning/v1.0-INTEGRATION-CHECK.md  (§Advisory A-01 — full rationale and recommended action-b: "wrap the two sweep blocks in `main.py:lifespan` with `with bg_log_context(\"orphan-sweep\"):`")
  </read_first>

  <files>backend/app/main.py, backend/tests/test_lifespan_bg_log_context.py</files>

  <behavior>
    - `main.py` change: wrap the EventBridge-schedule sweep try/except in `with bg_log_context("orphan-schedule-sweep"):` and the background-jobs sweep try/except in `with bg_log_context("orphan-jobs-sweep"):`. Both should run their existing try/except bodies INSIDE the context manager so exceptions caught by `logger.exception` inherit the bg:request_id.
    - Regression test: spy on `bg_log_context` (or on `request_id_var`) and assert that, during the lifespan sweep blocks, `request_id_var.get()` returns the expected `bg:orphan-schedule-sweep:-` / `bg:orphan-jobs-sweep:-` values. Achievable without starting the real ASGI app — directly call the lifespan async context manager and mock the service methods.
  </behavior>

  <action>
    **Edit 1: `backend/app/main.py`** — add import (if not already present) and wrap the two sweep blocks.

    Add import at the top of the file, next to the other `app.core` imports:
    ```python
    from app.core.log_context import bg_log_context
    ```

    Replace the EventBridge-schedule sweep block (current lines ~101-109):
    ```python
    # BEFORE
    try:
        # Best-effort: delete EventBridge schedules under our prefix that no
        # longer correspond to a live crawler_schedules row. ...
        swept = crawler_schedule_service.sweep_orphan_schedules(db)
        if swept:
            logger.info("Swept %d orphan EventBridge schedule(s) on startup", len(swept))
    except Exception:
        logger.exception("Orphan EventBridge schedule sweep failed on startup")
    ```
    With:
    ```python
    # AFTER (A-01): wrap in bg_log_context so any log/exception emitted by
    # crawler_schedule_service.sweep_orphan_schedules is tagged with
    # request_id="bg:orphan-schedule-sweep:-" for CloudWatch grep.
    with bg_log_context("orphan-schedule-sweep"):
        try:
            # Best-effort: delete EventBridge schedules under our prefix that no
            # longer correspond to a live crawler_schedules row. Also cleans up
            # legacy per-adapter schedules from the previous implementation.
            swept = crawler_schedule_service.sweep_orphan_schedules(db)
            if swept:
                logger.info("Swept %d orphan EventBridge schedule(s) on startup", len(swept))
        except Exception:
            logger.exception("Orphan EventBridge schedule sweep failed on startup")
    ```

    Replace the background-jobs sweep block (current lines ~110-124):
    ```python
    # BEFORE
    try:
        orphans = job_service.sweep_orphan_jobs(db, current_worker_instance_id=WORKER_INSTANCE_ID)
        if orphans:
            logger.warning(
                "Marked %d stale background job(s) as failed on startup (ids=%s)",
                len(orphans),
                [str(o.id) for o in orphans],
            )
    except Exception:
        logger.exception("Orphan background-job sweep failed on startup")
    ```
    With:
    ```python
    # AFTER (A-01): wrap in bg_log_context so any log/exception emitted by
    # job_service.sweep_orphan_jobs is tagged with
    # request_id="bg:orphan-jobs-sweep:-" for CloudWatch grep.
    with bg_log_context("orphan-jobs-sweep"):
        try:
            orphans = job_service.sweep_orphan_jobs(db, current_worker_instance_id=WORKER_INSTANCE_ID)
            if orphans:
                logger.warning(
                    "Marked %d stale background job(s) as failed on startup (ids=%s)",
                    len(orphans),
                    [str(o.id) for o in orphans],
                )
        except Exception:
            logger.exception("Orphan background-job sweep failed on startup")
    ```

    **Edit 2: `backend/tests/test_lifespan_bg_log_context.py`** — create new regression test.

    ```python
    """A-01 regression: lifespan orphan sweeps must run inside bg_log_context
    so log lines emitted by sweep_orphan_schedules / sweep_orphan_jobs carry
    request_id="bg:orphan-schedule-sweep:-" / "bg:orphan-jobs-sweep:-" rather
    than the default "-".

    See .planning/v1.0-INTEGRATION-CHECK.md §Advisory A-01.
    """
    from __future__ import annotations

    import pytest
    from unittest.mock import patch, MagicMock

    from app.core.log_context import request_id_var, user_id_var


    @pytest.mark.asyncio
    async def test_orphan_schedule_sweep_runs_under_bg_log_context():
        """During crawler_schedule_service.sweep_orphan_schedules, the
        request_id ContextVar should be 'bg:orphan-schedule-sweep:-'.
        """
        from app import main as main_module

        captured_request_ids: list[str] = []

        def fake_sweep_orphan_schedules(db) -> list:
            # Capture the request_id at the exact moment the sweep runs.
            captured_request_ids.append(request_id_var.get())
            return []

        def fake_sweep_orphan_jobs(db, current_worker_instance_id=None) -> list:
            return []

        with patch.object(
            main_module.crawler_schedule_service,
            "sweep_orphan_schedules",
            side_effect=fake_sweep_orphan_schedules,
        ), patch.object(
            main_module.job_service,
            "sweep_orphan_jobs",
            side_effect=fake_sweep_orphan_jobs,
        ), patch.object(
            main_module, "init_crawler_service_account", return_value=None
        ), patch.object(
            main_module, "init_crawler_adapter_configs", return_value=None
        ), patch.object(
            main_module, "init_car_generations", return_value=None
        ), patch("app.main.SessionLocal", return_value=MagicMock()):
            async with main_module.lifespan(MagicMock()):
                pass

        assert captured_request_ids == ["bg:orphan-schedule-sweep:-"], (
            f"Expected sweep_orphan_schedules to run with "
            f"request_id='bg:orphan-schedule-sweep:-', got {captured_request_ids}"
        )


    @pytest.mark.asyncio
    async def test_orphan_jobs_sweep_runs_under_bg_log_context():
        """During job_service.sweep_orphan_jobs, the request_id ContextVar
        should be 'bg:orphan-jobs-sweep:-'.
        """
        from app import main as main_module

        captured_request_ids: list[str] = []

        def fake_sweep_orphan_schedules(db) -> list:
            return []

        def fake_sweep_orphan_jobs(db, current_worker_instance_id=None) -> list:
            captured_request_ids.append(request_id_var.get())
            return []

        with patch.object(
            main_module.crawler_schedule_service,
            "sweep_orphan_schedules",
            side_effect=fake_sweep_orphan_schedules,
        ), patch.object(
            main_module.job_service,
            "sweep_orphan_jobs",
            side_effect=fake_sweep_orphan_jobs,
        ), patch.object(
            main_module, "init_crawler_service_account", return_value=None
        ), patch.object(
            main_module, "init_crawler_adapter_configs", return_value=None
        ), patch.object(
            main_module, "init_car_generations", return_value=None
        ), patch("app.main.SessionLocal", return_value=MagicMock()):
            async with main_module.lifespan(MagicMock()):
                pass

        assert captured_request_ids == ["bg:orphan-jobs-sweep:-"], (
            f"Expected sweep_orphan_jobs to run with "
            f"request_id='bg:orphan-jobs-sweep:-', got {captured_request_ids}"
        )


    @pytest.mark.asyncio
    async def test_request_id_is_reset_after_lifespan_exits():
        """After lifespan context exits, request_id_var should return to its
        default '-' (bg_log_context uses re-entrant-safe token reset).
        """
        from app import main as main_module

        with patch.object(
            main_module.crawler_schedule_service,
            "sweep_orphan_schedules",
            return_value=[],
        ), patch.object(
            main_module.job_service, "sweep_orphan_jobs", return_value=[]
        ), patch.object(
            main_module, "init_crawler_service_account", return_value=None
        ), patch.object(
            main_module, "init_crawler_adapter_configs", return_value=None
        ), patch.object(
            main_module, "init_car_generations", return_value=None
        ), patch("app.main.SessionLocal", return_value=MagicMock()):
            async with main_module.lifespan(MagicMock()):
                pass

        assert request_id_var.get() == "-", (
            f"request_id_var should reset to '-' after lifespan, got {request_id_var.get()!r}"
        )
        assert user_id_var.get() == "-", (
            f"user_id_var should reset to '-' after lifespan, got {user_id_var.get()!r}"
        )
    ```

    If `pytest-asyncio` is not already a project dependency, check `backend/requirements.txt` and `backend/pytest.ini` — it was used elsewhere? If not available, use `asyncio.run(...)` to drive the async context manager inside a sync test instead:
    ```python
    import asyncio
    def test_...():
        async def _run():
            async with main_module.lifespan(MagicMock()):
                pass
        asyncio.run(_run())
    ```
    Check the test by running `pytest --collect-only backend/tests/test_lifespan_bg_log_context.py` first — if `@pytest.mark.asyncio` is not recognized, fall back to the `asyncio.run` pattern.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto tests/test_lifespan_bg_log_context.py -v</automated>
  </verify>

  <acceptance_criteria>
    - `grep -c "bg_log_context(\"orphan-" backend/app/main.py` returns exactly `2`
    - `grep -c "from app.core.log_context import bg_log_context" backend/app/main.py` returns exactly `1`
    - `cd backend &amp;&amp; pytest -n auto tests/test_lifespan_bg_log_context.py -v` exits 0 with 3 passed
    - `cd backend &amp;&amp; pytest -n auto tests/ -x -k "not lifespan_bg_log_context"` — existing suite still passes (no regression)
    - A grep over `backend/app/` for `bg_log_context(` now returns at least 2 production callers (previously zero):
      `grep -rn "bg_log_context(" backend/app/` — count excluding the def line in log_context.py should be at least 2.
  </acceptance_criteria>

  <done>
    Lifespan orphan sweeps wrapped in `bg_log_context`. Three regression tests confirm the correct request_id is set during each sweep and that ContextVars reset after lifespan exit. Full suite green.
  </done>
</task>

<task type="auto">
  <name>Task 2: Generate adapter_names.txt + convert terraform alarm to per-adapter for_each</name>

  <read_first>
    - terraform/monitoring.tf  (lines 165-220 — current composite alarm; note existing var.disabled_parse_alarms usage pattern in the TODO comment)
    - terraform/variables.tf  (lines 146-150 — `var.disabled_parse_alarms` is already declared, type list(string), default [])
    - backend/app/crawlers/adapters/__init__.py  (confirm ADAPTER_REGISTRY structure; prefer this export over filesystem walk)
    - .planning/v1.0-MILESTONE-AUDIT.md  (Phase 02 item 2: "terraform/monitoring.tf:216" TODO marker)
  </read_first>

  <files>terraform/adapter_names.txt, terraform/monitoring.tf</files>

  <action>
    **Step 1: Generate `terraform/adapter_names.txt`**

    From the repo root, run:
    ```bash
    cd backend && python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; print('\n'.join(sorted(ADAPTER_REGISTRY.keys())))" > ../terraform/adapter_names.txt
    cd ..
    wc -l terraform/adapter_names.txt
    ```

    Expected output: one adapter name per line, sorted. Expected count: 108 (matches ADAPTER_REGISTRY len at 2026-04-24 per INTEGRATION-CHECK line 21).

    If the ADAPTER_REGISTRY import fails (module import errors because your shell's PYTHONPATH doesn't include `backend/`), prepend `PYTHONPATH=backend` to the `python -c` invocation. Do NOT fall back to globbing `backend/app/crawlers/adapters/**/*.py` — filenames include 6 non-adapter scaffold files, which would pollute the alarm fan-out with dead resources.

    Commit the generated file. It is a generated artifact but is committed rather than generated at `terraform plan` time because terraform's `file()` function requires it at plan time and we want the operator to review the set in PR diffs when adapters are added/removed.

    Add a one-line header comment is NOT supported by `file()` (it returns the full file contents verbatim). Instead, document the generation command in `terraform/README.md` (append a small section) — if the README doesn't exist, create it with just this:
    ```markdown
    ## Generated files

    ### `adapter_names.txt`

    Regenerate from the repo root whenever crawler adapters are added / removed:

    ```bash
    PYTHONPATH=backend python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; print('\n'.join(sorted(ADAPTER_REGISTRY.keys())))" > terraform/adapter_names.txt
    ```

    Consumed by `monitoring.tf` to fan out per-adapter CloudWatch parse-failure alarms.
    ```

    **Step 2: Replace the composite alarm in `terraform/monitoring.tf`**

    Delete the entire `resource "aws_cloudwatch_metric_alarm" "crawler_parse_failure_composite"` block (current lines 165-220, including the trailing `}`) and replace with:

    ```hcl
    # ---------------------------------------------------------------------------
    # Per-adapter parse-failure alarms — fan-out via for_each
    # ---------------------------------------------------------------------------
    # Phase 07 TODO-02 / Phase 2 A-01 follow-up: the Phase-2 composite alarm
    # (summed all adapters) is replaced by one alarm per adapter so an operator
    # immediately sees which adapter drifted. Cost impact: ~108 alarms at
    # $0.10/month = ~$10.80/month.
    #
    # Source of truth for adapter names: `terraform/adapter_names.txt`, regenerated
    # from `ADAPTER_REGISTRY.keys()` (see terraform/README.md). Opt out specific
    # adapters by adding their names to `var.disabled_parse_alarms`.
    #
    # Landmines pinned (carried from the composite alarm):
    #   7  — NO top-level `period` attribute (terraform-provider-aws#29398).
    #        period lives ONLY inside each metric_query.metric {} block.
    #   8  — NaN-via-0 small-sample suppression so GreaterThanThreshold is portable.
    #   9  — datapoints_to_alarm (1) <= evaluation_periods (1).
    #   10 — GreaterThanThreshold is strict > (NOT GreaterThanOrEqualToThreshold).
    # ---------------------------------------------------------------------------
    locals {
      _adapter_names_raw   = split("\n", trimspace(file("${path.module}/adapter_names.txt")))
      parse_alarm_adapters = toset(setsubtract(local._adapter_names_raw, var.disabled_parse_alarms))
    }

    resource "aws_cloudwatch_metric_alarm" "crawler_parse_failure_per_adapter" {
      for_each = local.parse_alarm_adapters

      alarm_name        = "${local.prefix}-crawler-parse-failure-${each.value}"
      alarm_description = "Parse-failure rate >50% for adapter ${each.value} (live runs only). Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"

      comparison_operator = "GreaterThanThreshold" # strict > (Landmine 10)
      evaluation_periods  = 1
      datapoints_to_alarm = 1 # 1 of 1 (Landmine 9)
      threshold           = 0.5
      treat_missing_data  = "notBreaching" # idle adapters stay quiet

      # NO top-level `period` — bug terraform-provider-aws#29398 / Landmine 7.
      # period lives only inside each metric_query.metric {} block below.

      metric_query {
        id = "ingested"
        metric {
          metric_name = "Ingested"
          namespace   = "CarModPicker/Crawlers"
          period      = 3600 # 1 hour — matches hourly crawl cadence
          stat        = "Sum"
          dimensions = {
            AdapterName = each.value
            Environment = var.environment
            RunType     = "live" # exclude rescrape (D-21)
          }
        }
      }

      metric_query {
        id = "failures"
        metric {
          metric_name = "ParseFailures"
          namespace   = "CarModPicker/Crawlers"
          period      = 3600
          stat        = "Sum"
          dimensions = {
            AdapterName = each.value
            Environment = var.environment
            RunType     = "live"
          }
        }
      }

      metric_query {
        id          = "rate"
        expression  = "IF((ingested + failures) < 10, 0, failures / (ingested + failures))"
        label       = "Parse failure rate for ${each.value} (suppressed below 10 samples)"
        return_data = true # exactly one query has return_data=true
      }

      alarm_actions = [aws_sns_topic.alarms.arn]
      ok_actions    = [aws_sns_topic.alarms.arn]

      tags = {
        AdapterName = each.value
        ManagedBy   = "Terraform"
        Phase       = "07"
      }
    }
    ```

    **Step 3: Run terraform validate**

    From `terraform/`:
    ```bash
    cd terraform
    terraform fmt -check -diff
    terraform validate
    ```

    `terraform fmt -check` should exit 0. `terraform validate` should exit 0 — note this requires `terraform init` to have been run previously in the project; if it hasn't, run `terraform init -backend=false` first (backend=false avoids needing S3 state credentials during local validation).

    If `terraform validate` reports errors, fix them and re-run. Do NOT run `terraform apply` — this plan is `autonomous: false` and the prod apply is gated on human review of the per-adapter alarm cost + fan-out diff.

    **Step 4: Export AdapterName dimension in the EMF emitter (verify, do not change)**

    Per `.planning/v1.0-INTEGRATION-CHECK.md` wire #2: `backend/app/utils/cloudwatch_emf.py:122-132` already emits dimensions `AdapterName × Environment × RunType` (D-19). So the per-adapter alarm's new `AdapterName = each.value` dimension on both `metric_query.metric.dimensions` maps will match producer-side dimensions without any app code change. Verify with:
    ```bash
    grep -n "AdapterName" backend/app/utils/cloudwatch_emf.py
    ```
    Must return at least one match. If not, STOP and escalate — the terraform change alone cannot fire alarms without the producer emitting matching dimensions.
  </action>

  <verify>
    <automated>cd terraform &amp;&amp; terraform fmt -check -diff &amp;&amp; terraform validate 2>&amp;1 | tail -10</automated>
  </verify>

  <acceptance_criteria>
    - `terraform/adapter_names.txt` exists and `wc -l terraform/adapter_names.txt` returns between 100 and 120 (ADAPTER_REGISTRY size; 108 at planning time with some wiggle room for adapter adds/removes)
    - `sort -c terraform/adapter_names.txt` exits 0 (file is sorted)
    - `grep -c "crawler_parse_failure_composite" terraform/monitoring.tf` returns `0` (composite alarm removed)
    - `grep -c "crawler_parse_failure_per_adapter" terraform/monitoring.tf` returns `1` (new per-adapter resource present)
    - `grep -c "for_each = local.parse_alarm_adapters" terraform/monitoring.tf` returns `1`
    - `grep -c "TODO(phase-3)" terraform/monitoring.tf` returns `0` (old TODO removed)
    - `grep -c "AdapterName = each.value" terraform/monitoring.tf` returns exactly `2` (one in each metric_query dimension map)
    - `cd terraform &amp;&amp; terraform fmt -check -diff` exits 0
    - `cd terraform &amp;&amp; terraform validate` exits 0 (backend=false init as needed)
    - `grep -n "AdapterName" backend/app/utils/cloudwatch_emf.py` returns at least 1 match (producer still emits AdapterName dimension, confirming alarm/producer parity)
  </acceptance_criteria>

  <done>
    `adapter_names.txt` generated and committed, composite alarm replaced by per-adapter `for_each` block, TODO marker resolved, `terraform validate` green.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Human review of terraform plan output for per-adapter alarm fan-out</name>
  <files>terraform/monitoring.tf, terraform/adapter_names.txt</files>
  <what-built>
    Terraform `monitoring.tf` changed from a single composite parse-failure alarm to ~108 per-adapter alarms. `terraform plan` will show ~108 alarm creates and 1 alarm destroy. Monthly CloudWatch cost increases by ~$10.80 (108 alarms x $0.10/mo). SNS topic unchanged - existing email subscriptions fire on any adapter drift.
  </what-built>
  <action>
    Human-gated review task. Execute steps listed in <how-to-verify> and respond at the <resume-signal>. This is a terraform plan review and is not automatable - the cost/resource diff must be consciously approved before any apply can happen.
  </action>
  <how-to-verify>
    1. `cd terraform && terraform plan -var-file=<env>.tfvars 2>&amp;1 | tee /tmp/07-04-plan.txt` - confirm plan shows roughly:
       - `~ 1 to destroy` (composite alarm)
       - `+ ~108 to create` (per-adapter alarms, one per line in `adapter_names.txt`)
       - No other unexpected resource changes
    2. Spot-check one per-adapter alarm resource in the plan output - confirm `AdapterName` dimension is set on both `ingested` and `failures` metric queries with the adapter name (e.g. `awetuning`, `stoptech`, etc.).
    3. Confirm `var.disabled_parse_alarms` is still empty (`default = []` in variables.tf) unless you intend to exclude specific noisy adapters at this time.
    4. Review the $10.80/month cost delta - this is acceptable per the existing TODO note at `monitoring.tf:218`.
    5. DO NOT apply yet - apply should happen during milestone v1.0 deploy gate, with 24h staging bake if feasible.
  </how-to-verify>
  <verify>Manual: operator replies "approved" after reviewing /tmp/07-04-plan.txt</verify>
  <resume-signal>
    Reply "approved" after reviewing the plan output. Reply with rejection notes if any unexpected resources show up (e.g., unrelated drift from other terraform work in progress) or if you want to trim the adapter list via `var.disabled_parse_alarms`.
  </resume-signal>
  <done>Operator has reviewed `terraform plan` output and approved the ~108 alarm fan-out diff.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| FastAPI app startup → AWS EventBridge | `crawler_schedule_service.sweep_orphan_schedules` calls EventBridge APIs. Now logs under `bg:orphan-schedule-sweep:-` so any unauthorized delete is traceable. |
| Terraform → AWS CloudWatch + SNS | 108 new alarms created; SNS topic unchanged. |
| adapter_names.txt → terraform file() | File is committed into git; any drift requires a PR. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-04-01 | Repudiation | Lifespan orphan-job sweeps | mitigate | Before this plan, sweep logs had `request_id=-` and could not be grep-separated from default startup noise. Wrapping in `bg_log_context` tags them `bg:orphan-*-sweep:-`, so CloudWatch Logs Insights query `filter @message like /req=bg:orphan-/` returns exactly the sweep activity — enables incident forensics. |
| T-07-04-02 | Denial of Service | Per-adapter alarm fan-out | accept | Alarm count increases from 1 to ~108. SNS topic can absorb this (Landmine note: SNS has no alarm-fan-in limits in the ranges we use). Per-adapter thresholding is unchanged (>50% parse failure over 1h with 10+ sample suppression). Each alarm is independent — bad adapter noise cannot amplify. |
| T-07-04-03 | Spoofing | AdapterName dimension match | mitigate | Producer side (`cloudwatch_emf.py`) already emits `AdapterName` dimension. Consumer side (alarm) now filters on `AdapterName = each.value`. Any adapter that emits a different `AdapterName` than its ADAPTER_REGISTRY key would silently miss alarms — but adapter-name mismatch would also break Phase 3 characterization tests. Existing `test_cloudwatch_emf.py:152-171` pins the dimension-set. |
| T-07-04-04 | Information Disclosure | adapter_names.txt in repo | accept | File lists crawler adapter names (retailer names like `awetuning`, `stoptech`, etc.). Same information is already discoverable by anyone scraping the product pages we crawl — no secrecy. Committing to terraform/ rather than ignoring keeps the PR diff self-contained when adapters are added/removed. |

**No new attack surface introduced.** The lifespan wrapping strengthens observability. The terraform fan-out was the originally-designed shape (Phase 2 deferred it only because ADAPTER_REGISTRY wasn't auto-discovered yet).
</threat_model>

<verification>
1. `grep -c "bg_log_context(\"orphan-" backend/app/main.py` → `2`
2. `cd backend && pytest -n auto tests/test_lifespan_bg_log_context.py -v` → 3 passed
3. `cd backend && pytest -n auto tests/ -x --no-cov 2>&1 | tail -3` → full suite still green
4. `wc -l terraform/adapter_names.txt` → 100-120
5. `cd terraform && terraform fmt -check -diff && terraform validate` → exit 0
6. `grep -c "crawler_parse_failure_composite" terraform/monitoring.tf` → `0`
7. `grep -c "crawler_parse_failure_per_adapter" terraform/monitoring.tf` → `1`
8. Human checkpoint (Task 3) approved — `terraform plan` shows expected diff.
</verification>

<success_criteria>
- Phase 7 success criterion 7 closed: lifespan orphan-job sweep uses `bg_log_context`; `terraform/monitoring.tf:216` TODO resolved via per-adapter `for_each` parse-failure alarm.
</success_criteria>

<output>
After completion, create `.planning/phases/07-v1-residue-cleanup/07-04-SUMMARY.md`. Frontmatter must include `tech_debt_items_closed: [A-01, TODO-02]`. Note in the summary that terraform apply to prod is gated on human review and the 24h staging bake per the existing D-58 operator gate in `02-HUMAN-UAT.md`.
</output>
