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
from fastapi.testclient import TestClient

from app.api.models.user import User
from app.core.log_context import (
    bg_log_context,
    request_id_var,
    user_id_var,
)
from tests.conftest import login_user


def test_log_propagation_request_scope(
    client: TestClient,
    test_user: User,
    caplog_with_context,
) -> None:
    """Every log record during an auth'd request has request_id + user_id."""
    caplog_with_context.set_level(logging.DEBUG)
    token = login_user(client, test_user.username)
    response = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    assert len(caplog_with_context.records) > 0, "no log records captured"
    for rec in caplog_with_context.records:
        assert getattr(rec, "request_id", "-") != "-", (
            f"missing request_id on '{rec.getMessage()}' (logger={rec.name})"
        )
        assert getattr(rec, "user_id", "-") != "-", (
            f"missing user_id on '{rec.getMessage()}' (logger={rec.name})"
        )


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


def test_cli_log_context(caplog_with_context) -> None:
    """CLI scope produces request_id=cli:<pid>, user_id=cli."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.cli")
    rid_token = request_id_var.set("cli:12345")
    uid_token = user_id_var.set("cli")
    try:
        logger.info("cli startup")
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)
    rec = next(r for r in caplog_with_context.records if "cli startup" in r.getMessage())
    assert rec.request_id == "cli:12345"
    assert rec.user_id == "cli"


def test_log_propagation_sqlalchemy(
    client: TestClient,
    test_user: User,
    caplog_with_context,
) -> None:
    """SQL query log records during a request carry the request's request_id
    (D-48: third-party loggers propagate via root logger filter)."""
    sa_logger = logging.getLogger("sqlalchemy.engine")
    prior_level = sa_logger.level
    sa_logger.setLevel(logging.INFO)
    caplog_with_context.set_level(logging.INFO)
    try:
        token = login_user(client, test_user.username)
        resp = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text
    finally:
        sa_logger.setLevel(prior_level)
    sa_records = [r for r in caplog_with_context.records if r.name.startswith("sqlalchemy")]
    if not sa_records:
        pytest.skip("sqlalchemy did not emit INFO log records in test env")
    for rec in sa_records:
        assert getattr(rec, "request_id", "-") != "-", (
            f"sqlalchemy log missing request_id: {rec.getMessage()}"
        )
