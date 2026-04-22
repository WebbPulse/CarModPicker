"""OBS-02 unit coverage for CloudWatch EMF emission.

Decision refs: 02-CONTEXT.md D-16..D-22, D-50. Landmine refs: 02-RESEARCH.md
§5 Landmine 3 (emit BEFORE summary — issue #109 drops trailing EMF lines),
§5 Landmine 4 (AWS_EMF_ENVIRONMENT=Local required on ECS/App Runner — plan
02-02 terraform sets this), §5 Landmine 5 (async flush handled by
@metric_scope auto-flush decorator).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest


def _invoke_emit(capsys, **kwargs):
    """Run emit_crawler_run_metrics + return parsed EMF line (or None if silent)."""
    from app.core.cloudwatch_emf import emit_crawler_run_metrics

    emit_crawler_run_metrics(**kwargs)
    out = capsys.readouterr().out
    emf_lines = [l for l in out.splitlines() if l.startswith("{") and '"_aws"' in l]
    if not emf_lines:
        return None
    assert len(emf_lines) == 1, f"expected 1 EMF line, got {len(emf_lines)}: {emf_lines}"
    return json.loads(emf_lines[0])


def _emit_args(**overrides):
    base = dict(
        adapter_name="summit_racing",
        run_type="live",
        ingested=147,
        parse_failures=3,
        elapsed_seconds=42.7,
    )
    base.update(overrides)
    return base


class TestEnvGate:
    def test_no_op_when_testing_true(self, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
        """TESTING=true must force a no-op even when APP_ENVIRONMENT is staging
        (T-02-TEST-POLLUTION). Conftest already sets TESTING=true at import time
        — we only need to confirm APP_ENVIRONMENT=staging doesn't override it."""
        monkeypatch.setenv("TESTING", "true")
        monkeypatch.setattr("app.core.cloudwatch_emf.settings.APP_ENVIRONMENT", "staging")
        record = _invoke_emit(capsys, **_emit_args())
        assert record is None

    def test_no_op_when_development(self, capsys, monkeypatch: pytest.MonkeyPatch) -> None:
        """APP_ENVIRONMENT=development gates emission even if TESTING is cleared."""
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setattr("app.core.cloudwatch_emf.settings.APP_ENVIRONMENT", "development")
        monkeypatch.setenv("AWS_EMF_ENVIRONMENT", "Local")
        record = _invoke_emit(capsys, **_emit_args())
        assert record is None


class TestEMFShape:
    @pytest.fixture(autouse=True)
    def _active_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setattr("app.core.cloudwatch_emf.settings.APP_ENVIRONMENT", "staging")
        # Landmine 4 — force stdout sink. In real staging/prod, terraform sets
        # AWS_EMF_ENVIRONMENT=Local at process start so the library's config
        # module (which reads os.environ ONCE at import time) picks it up.
        # In tests we can't rely on that — the config + EnvironmentCache are
        # already initialized. Patch both directly so the next EMF call routes
        # through the Local (stdout) sink instead of the DefaultEnvironment
        # agent-TCP sink (which otherwise fails on Errno 61 / drops the line).
        monkeypatch.setenv("AWS_EMF_ENVIRONMENT", "Local")
        from aws_embedded_metrics.config import get_config
        from aws_embedded_metrics.environment.environment_detector import EnvironmentCache

        monkeypatch.setattr(get_config(), "environment", "Local")
        monkeypatch.setattr(EnvironmentCache, "environment", None)

    def test_envelope_namespace(self, capsys) -> None:
        record = _invoke_emit(capsys, **_emit_args())
        assert record is not None, "expected EMF line on stdout"
        assert record["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "CarModPicker/Crawlers"

    def test_dimension_set(self, capsys) -> None:
        record = _invoke_emit(capsys, **_emit_args())
        dims = record["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]
        assert set(dims) == {"AdapterName", "Environment", "RunType"}

    def test_top_level_dimension_values(self, capsys) -> None:
        record = _invoke_emit(capsys, **_emit_args(adapter_name="summit_racing", run_type="live"))
        assert record["AdapterName"] == "summit_racing"
        assert record["Environment"] == "staging"
        assert record["RunType"] == "live"

    def test_metric_names_and_units(self, capsys) -> None:
        record = _invoke_emit(capsys, **_emit_args())
        metrics = record["_aws"]["CloudWatchMetrics"][0]["Metrics"]
        by_name = {m["Name"]: m["Unit"] for m in metrics}
        assert by_name == {
            "Ingested": "Count",
            "ParseFailures": "Count",
            "ElapsedSeconds": "Seconds",
        }

    def test_metric_values(self, capsys) -> None:
        record = _invoke_emit(capsys, **_emit_args(ingested=147, parse_failures=3, elapsed_seconds=42.7))
        assert record["Ingested"] == 147
        assert record["ParseFailures"] == 3
        assert record["ElapsedSeconds"] == 42.7

    def test_rescrape_run_type(self, capsys) -> None:
        """D-21: rescrape path emits RunType=rescrape so plan 02-05 alarm can
        filter on RunType=live without rescrape noise triggering it."""
        record = _invoke_emit(capsys, **_emit_args(run_type="rescrape"))
        assert record["RunType"] == "rescrape"


class TestFailureIsolation:
    def test_exception_does_not_propagate(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Emission failure must NOT crash run_crawler (email.py analog — T-02-EMF-CRASH)."""
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setattr("app.core.cloudwatch_emf.settings.APP_ENVIRONMENT", "staging")

        def boom(*args, **kwargs):
            raise RuntimeError("simulated library failure")

        monkeypatch.setattr("app.core.cloudwatch_emf._emit_scoped", boom)
        caplog.set_level(logging.ERROR, logger="app.core.cloudwatch_emf")

        from app.core.cloudwatch_emf import emit_crawler_run_metrics

        # Must return without raising
        emit_crawler_run_metrics(**_emit_args())

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert any("summit_racing" in r.getMessage() for r in error_records), (
            "expected error log naming the adapter on emission failure; got: "
            f"{[r.getMessage() for r in error_records]}"
        )


class TestEmissionPosition:
    """Static code check: EMF emission MUST appear BEFORE the summary log line
    (RESEARCH Landmine 3 — aws-embedded-metrics issue #109 drops trailing EMF)."""

    def test_runner_emits_before_summary(self) -> None:
        runner_path = Path(__file__).resolve().parents[1] / "app" / "crawlers" / "runner.py"
        assert runner_path.exists(), f"runner.py not found at {runner_path}"
        lines = runner_path.read_text().splitlines()

        emit_line = next(
            (i for i, l in enumerate(lines) if "emit_crawler_run_metrics(" in l and "import" not in l),
            None,
        )
        summary_line = next(
            (
                i
                for i, l in enumerate(lines)
                if "logger.log(summary_level" in l
                or '"Adapter %s done' in l
                or "'Adapter %s done" in l
            ),
            None,
        )
        assert emit_line is not None, "emit_crawler_run_metrics call not found in runner.py"
        assert summary_line is not None, "summary log line not found in runner.py"
        assert emit_line < summary_line, (
            f"EMF emission (line {emit_line + 1}) must precede summary log "
            f"(line {summary_line + 1}) — Landmine 3 / aws-embedded-metrics issue #109"
        )
