"""OBS-04 regression guard — every log record during a request scope MUST have
non-default request_id + user_id. Fails CI if a future dev adds a handler that
drops RequestContextFilter coverage or uses print() instead of logger.

Decision refs: 02-CONTEXT.md D-44 (audit, not redesign), D-45 (regression guard),
D-46 (bg_log_context), D-47 (CLI context), D-48 (sqlalchemy propagation).

Landmine: pytest caplog does NOT inherit root-logger filters — the
`caplog_with_context` fixture (conftest.py) attaches RequestContextFilter
to caplog.handler so records carry request_id + user_id attributes.
Without this fixture, every assertion below AttributeErrors.
"""

from __future__ import annotations

import logging

import pytest

from app.core.log_context import (
    RequestContextFilter,
    bg_log_context,
    request_id_var,
    user_id_var,
)


@pytest.fixture
def caplog_with_context(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Local fixture for Task 1 — augments caplog with RequestContextFilter on the
    handler so LogRecords carry request_id + user_id attrs.

    Task 2 (02-01-02) promotes this fixture to backend/tests/conftest.py so it is
    available to the broader test suite.  See Landmine 15 in 02-RESEARCH.md:
    pytest's caplog does NOT inherit root-logger filters, so we must attach the
    filter to caplog.handler explicitly or record.request_id raises AttributeError.
    """
    caplog.handler.addFilter(RequestContextFilter())
    return caplog


def test_bg_log_context(caplog_with_context) -> None:
    """bg_log_context sets request_id=bg:{task}:{job} + user_id=bg."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.bg")
    with bg_log_context("crawler", "job-1"):
        logger.info("running bg task")
    matches = [r for r in caplog_with_context.records if "running bg task" in r.getMessage()]
    assert len(matches) == 1
    rec = matches[0]
    assert rec.request_id == "bg:crawler:job-1"
    assert rec.user_id == "bg"


def test_bg_log_context_job_id_none(caplog_with_context) -> None:
    """bg_log_context with no job_id renders 'bg:{task}:-'."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.bg")
    with bg_log_context("sweep"):
        logger.info("sweep running")
    rec = next(r for r in caplog_with_context.records if "sweep running" in r.getMessage())
    assert rec.request_id == "bg:sweep:-"


def test_bg_log_context_resets(caplog_with_context) -> None:
    """Token-based reset leaves ContextVars at default after exit."""
    with bg_log_context("scope", "1"):
        assert request_id_var.get() == "bg:scope:1"
    assert request_id_var.get() == "-"
    assert user_id_var.get() == "-"
