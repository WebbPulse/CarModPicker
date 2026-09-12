"""Pins that every log record emitted inside a request or task scope carries a real request_id and user_id.

caplog does not inherit root logger filters, so these tests take the caplog_with_context fixture rather than caplog.
"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.testclient import TestClient
from webbpulse.log_context import (
    request_id_var,
    task_context,
    user_id_var,
)

from app.db.dynamo.users import User
from tests.conftest import auth_headers, login_user

_IN_SCOPE_LOGGER_ROOTS = (
    "app",
    "webbpulse",
)


def _in_request_scope(rec: logging.LogRecord) -> bool:
    """True if the record comes from code that should be inside a request scope."""
    return any(rec.name == n or rec.name.startswith(f"{n}.") for n in _IN_SCOPE_LOGGER_ROOTS)


def test_log_propagation_request_scope(
    client: TestClient,
    test_user: User,
    caplog_with_context,
) -> None:
    """Every in-scope record in an authenticated request carries a real request_id and user_id."""
    from fastapi import Depends

    from app.api.dependencies.auth import get_current_user, oauth2_scheme
    from app.api.dependencies.repositories import Repositories, get_repositories
    from app.main import app as fastapi_app

    emitted_request_ids: list[str] = []
    emitted_user_ids: list[str] = []

    async def logging_current_user(
        request: Request,
        token: str = Depends(oauth2_scheme),
        repos: Repositories = Depends(get_repositories),
    ) -> User:
        """Resolve the real dependency, then emit a record from inside the request scope."""
        result = await get_current_user(request=request, token=token, repos=repos)
        test_logger = logging.getLogger("app.tests.log_propagation")
        test_logger.info("post-auth request scope log emit")
        emitted_request_ids.append(request_id_var.get())
        emitted_user_ids.append(user_id_var.get())
        return result

    credential = login_user(client, test_user.username)

    caplog_with_context.set_level(logging.DEBUG)
    caplog_with_context.clear()

    fastapi_app.dependency_overrides[get_current_user] = logging_current_user
    try:
        response = client.get("/api/users/me", headers=auth_headers(credential))
    finally:
        fastapi_app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200, response.text

    assert len(emitted_request_ids) == 1, "override did not run exactly once"
    assert emitted_request_ids[0] != "-", "request_id_var not set inside request scope"
    assert emitted_user_ids[0] != "-", "user_id_var not set after get_current_user ran"

    in_scope = [r for r in caplog_with_context.records if _in_request_scope(r)]
    assert len(in_scope) > 0, "no in-scope log records captured during request"
    for rec in in_scope:
        assert getattr(rec, "request_id", "-") != "-", f"missing request_id on '{rec.getMessage()}' (logger={rec.name})"
        assert getattr(rec, "user_id", "-") != "-", f"missing user_id on '{rec.getMessage()}' (logger={rec.name})"


def test_task_context(caplog_with_context) -> None:
    """task_context sets request_id=bg:{task}:{job} + user_id=bg."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.bg")
    with task_context("crawler", "job-1"):
        logger.info("running bg task")
    matches = [r for r in caplog_with_context.records if "running bg task" in r.getMessage()]
    assert len(matches) == 1
    rec = matches[0]
    assert rec.request_id == "bg:crawler:job-1"
    assert rec.user_id == "bg"


def test_task_context_job_id_none(caplog_with_context) -> None:
    """task_context with no job_id renders 'bg:{task}:-'."""
    caplog_with_context.set_level(logging.DEBUG)
    logger = logging.getLogger("app.test.bg")
    with task_context("sweep"):
        logger.info("sweep running")
    rec = next(r for r in caplog_with_context.records if "sweep running" in r.getMessage())
    assert rec.request_id == "bg:sweep:-"


def test_task_context_resets(caplog_with_context) -> None:
    """Leaving a task context restores the previous values by token.

    The module defaults are not used, so xdist ordering cannot affect it.
    """
    rid_token = request_id_var.set("before-rid")
    uid_token = user_id_var.set("before-uid")
    try:
        with task_context("scope", "1"):
            assert request_id_var.get() == "bg:scope:1"
            assert user_id_var.get() == "bg"
        assert request_id_var.get() == "before-rid"
        assert user_id_var.get() == "before-uid"
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)


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
