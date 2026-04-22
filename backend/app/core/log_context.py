import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Generator

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        record.user_id = user_id_var.get()  # type: ignore[attr-defined]
        return True


@contextmanager
def bg_log_context(task_name: str, job_id: str | None = None) -> Generator[None, None, None]:
    """Set request_id + user_id ContextVars for a background task scope.

    On enter: request_id = "bg:{task_name}:{job_id or '-'}", user_id = "bg".
    On exit: ContextVars are reset via token (re-entrant-safe).

    Use this to wrap crawler runner, orphan-job sweep, EventBridge callback
    handlers — any code that logs outside a request scope. Ensures
    CloudWatch grep `filter @message like /req=bg:crawler/` works.
    """
    rid_token = request_id_var.set(f"bg:{task_name}:{job_id or '-'}")
    uid_token = user_id_var.set("bg")
    try:
        yield
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)
