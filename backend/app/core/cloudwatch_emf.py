"""CloudWatch Embedded Metric Format (EMF) emitter for crawler runs (OBS-02).

Per-adapter CloudWatch metrics (``Ingested``, ``ParseFailures``, ``ElapsedSeconds``) are
emitted as single stdout JSON lines in the ``CarModPicker/Crawlers`` namespace so plan
02-05's alarm and future CloudWatch dashboards have data to work with.

Decision references (02-CONTEXT.md):
  - D-16: EMF via aws-embedded-metrics 3.x; rides the existing awslogs CloudWatch Logs
    path — no extra IAM, no cloudwatch agent, no PutMetricData API calls.
  - D-17: Emission point is inside ``run_crawler`` just BEFORE the existing summary
    ``logger.log(summary_level, ...)`` line (runner.py ~L680). See Landmine 3 below.
  - D-18: Exactly three metrics, fixed names/units:
      * ``Ingested``       — Count
      * ``ParseFailures``  — Count  (== ``skipped_not_product`` per D-22)
      * ``ElapsedSeconds`` — Seconds (wall-clock around the URL loop)
  - D-19: Dimensions are ``AdapterName × Environment × RunType`` — bounded cardinality
    (114 adapters × 2 envs × 2 RunTypes = 456 time series).
  - D-20: Dev/test env gate — silent unless ``TESTING != "true"`` AND
    ``APP_ENVIRONMENT.lower() in {"staging", "production"}``.
  - D-21: Rescrape path emits ``RunType=rescrape`` from ecs_rescrape_runner.py; live
    path (runner.py → run_crawler) emits ``RunType=live``. Plan 02-05's alarm filters
    on ``RunType=live`` so rescrape noise doesn't trigger the parse-failure alarm.
  - D-22: ``parse_failures == skipped_not_product`` (same field, two names expressing
    intent distinctly from transport/HTTP ``errors``).

RESEARCH landmine references:
  - Landmine 3 (aws-embedded-metrics issue #109): the library can drop the TRAILING
    EMF stdout line if it is the last thing a process emits. The existing
    ``logger.log(summary_level, "Adapter %s done...")`` summary line at runner.py:~680
    acts as the non-EMF flush trigger. NEVER reorder — EMF emission MUST precede the
    summary log. Pinned by ``test_runner_emits_before_summary`` static code check.
  - Landmine 4: On ECS Fargate / App Runner, aws-embedded-metrics' auto-detect falls
    back to a CloudWatch Agent sink that doesn't exist in those runtimes and silently
    drops metrics. The env var ``AWS_EMF_ENVIRONMENT=Local`` forces the stdout sink.
    Plan 02-02's terraform (apprunner.tf + ecs.tf) already sets this; this module
    does NOT set the env var itself — it just requires the ambient env be correct.
  - Landmine 5: ``metrics.flush()`` is async; using ``@metric_scope`` makes the
    decorator handle the async dance so the caller stays sync. This module uses the
    auto-flush decorator pattern, no asyncio.run() needed at call sites.

Failure isolation:
  Follows backend/app/core/email.py L36-L57 analog — any unexpected exception from
  the aws-embedded-metrics library is caught and logged via logger.error(...) but
  NEVER raised. Crawler uptime > signal reliability.
"""

from __future__ import annotations

import logging
import os

from aws_embedded_metrics import metric_scope
from aws_embedded_metrics.logger.metrics_logger import MetricsLogger

from app.core.config import settings

logger = logging.getLogger(__name__)


def emit_crawler_run_metrics(
    *,
    adapter_name: str,
    run_type: str,
    ingested: int,
    parse_failures: int,
    elapsed_seconds: float,
) -> None:
    """Emit one EMF record per crawler run. No-op outside staging/production.

    Args:
        adapter_name: ``AdapterName`` dimension value. Code-controlled — never user
            input. For aggregate rescrape runs, pass ``"aggregate"`` per ecs_rescrape_runner.py.
        run_type: ``RunType`` dimension value. Either ``"live"`` (from runner.py) or
            ``"rescrape"`` (from ecs_rescrape_runner.py). Plan 02-05 filters on ``live``.
        ingested: ``Ingested`` metric value (Count). From runner.py's ``ingested`` local.
        parse_failures: ``ParseFailures`` metric value (Count). From runner.py's
            ``skipped_not_product`` local (D-22).
        elapsed_seconds: ``ElapsedSeconds`` metric value (Seconds). Monotonic wall-clock
            around the URL loop.

    Env gates (D-20):
        - ``TESTING == "true"`` → return (no emission; test pollution guard)
        - ``settings.APP_ENVIRONMENT.lower() not in {"staging", "production"}`` → return
    """
    if os.environ.get("TESTING") == "true":
        return
    env = (settings.APP_ENVIRONMENT or "").lower()
    if env not in {"staging", "production"}:
        return

    try:
        _emit_scoped(
            adapter_name=adapter_name,
            env=env,
            run_type=run_type,
            ingested=ingested,
            parse_failures=parse_failures,
            elapsed_seconds=elapsed_seconds,
        )
    except Exception as exc:  # email.py analog: log + continue, never crash run_crawler
        logger.error(
            "emit_crawler_run_metrics failed for adapter=%s run_type=%s: %s",
            adapter_name,
            run_type,
            exc,
        )


@metric_scope  # auto-flush on function exit — handles sync/async dance (Landmine 5)
def _emit_scoped(
    metrics: MetricsLogger,  # injected by @metric_scope as first positional arg
    *,
    adapter_name: str,
    env: str,
    run_type: str,
    ingested: int,
    parse_failures: int,
    elapsed_seconds: float,
) -> None:
    """Internal helper: set namespace + dimensions + three metrics, then let
    ``@metric_scope`` flush on return. Raises are caught by the public wrapper."""
    metrics.set_namespace("CarModPicker/Crawlers")
    metrics.set_dimensions(
        {
            "AdapterName": adapter_name,
            "Environment": env,
            "RunType": run_type,
        }
    )
    metrics.put_metric("Ingested", ingested, "Count")
    metrics.put_metric("ParseFailures", parse_failures, "Count")
    metrics.put_metric("ElapsedSeconds", elapsed_seconds, "Seconds")
