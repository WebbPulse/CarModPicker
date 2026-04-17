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


def _make_formatter() -> logging.Formatter:
    """Return JSON formatter in production (non-TTY), colorized text formatter locally."""
    if sys.stdout.isatty():
        return ColorizedFormatter(LOG_FORMAT)
    return JsonFormatter(
        JSON_LOG_FORMAT, rename_fields={"levelname": "level", "name": "logger", "asctime": "timestamp"}
    )


# Logger setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(_make_formatter())
console_handler.addFilter(RequestContextFilter())
logger.addHandler(console_handler)


# Define the dependency function
def get_logger() -> logging.Logger:
    return logger
