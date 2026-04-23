import logging
import sys
from copy import copy

import click
from pythonjsonlogger.json import JsonFormatter  # type: ignore[import-untyped]

from app.core.log_context import RequestContextFilter

# Human-readable format for TTY (local dev)
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - [req=%(request_id)s user=%(user_id)s] - %(message)s"

# JSON format for non-TTY (production): fields become top-level JSON keys
JSON_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(request_id)s %(user_id)s %(message)s"

# Level name colors (matches uvicorn default)
TRACE_LOG_LEVEL = 5
LEVEL_NAME_COLORS = {
    TRACE_LOG_LEVEL: lambda name: click.style(str(name), fg="blue"),
    logging.DEBUG: lambda name: click.style(str(name), fg="cyan"),
    logging.INFO: lambda name: click.style(str(name), fg="green"),
    logging.WARNING: lambda name: click.style(str(name), fg="yellow"),
    logging.ERROR: lambda name: click.style(str(name), fg="red"),
    logging.CRITICAL: lambda name: click.style(str(name), fg="bright_red"),
}


class ColorizedFormatter(logging.Formatter):
    """
    Formatter that colorizes the log level name (like uvicorn).
    Only enables colors when stdout is a TTY.
    """

    def __init__(
        self,
        fmt: str | None = None,
        datefmt: str | None = None,
        use_colors: bool | None = None,
    ) -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_colors = use_colors if use_colors is not None else sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy(record)
        if self.use_colors:
            color_fn = LEVEL_NAME_COLORS.get(record_copy.levelno, lambda name: str(record_copy.levelname))
            record_copy.levelname = color_fn(record_copy.levelname)
        return super().format(record_copy)


def make_formatter() -> logging.Formatter:
    """Return JSON formatter in production (non-TTY), colorized text formatter locally."""
    if sys.stdout.isatty():
        return ColorizedFormatter(LOG_FORMAT)
    return JsonFormatter(
        JSON_LOG_FORMAT, rename_fields={"levelname": "level", "name": "logger", "asctime": "timestamp"}
    )


def configure_root_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with the app's formatter + RequestContextFilter.

    IN-04: previously the three entry points (``main.py``, ``runner.py``,
    ``ecs_runner.py``, ``ecs_rescrape_runner.py``) each called their own
    ``logging.basicConfig(...)`` at import. ``main.py`` (App Runner) then
    layered ``RequestContextFilter`` + ``make_formatter()`` on top, but
    the crawler entry points did not — so their log records missed the
    ``request_id`` / ``user_id`` attributes even after IN-03 set the
    underlying ContextVars. This helper centralizes the setup so every
    entry point gets the same filter + formatter in one call.

    Safe to call multiple times: ``logging.basicConfig`` short-circuits
    when the root logger already has handlers, so later calls only
    re-attach the filter + formatter to whatever handlers exist.
    """
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )
    formatter = make_formatter()
    ctx_filter = RequestContextFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.setFormatter(formatter)
        # Avoid stacking the same filter instance if called repeatedly
        # in the same process (tests, re-import pathways).
        if not any(isinstance(f, RequestContextFilter) for f in handler.filters):
            handler.addFilter(ctx_filter)


# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(make_formatter())
console_handler.addFilter(RequestContextFilter())
logger.addHandler(console_handler)


# Define the dependency function
def get_logger() -> logging.Logger:
    return logger
