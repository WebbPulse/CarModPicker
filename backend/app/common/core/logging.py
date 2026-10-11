"""Log configuration through the shared package.

Deployed processes get the shared JSON lines; a TTY gets the package's text line instead.
Handlers write to stderr either way, since some commands write data on stdout.
"""

import logging
import sys

from webbpulse.log_context import attach_log_context
from webbpulse.logging import configure_logging


def configure_app_logging(level: str = "INFO", service: str | None = None, environment: str | None = None) -> None:
    """Configure the root logger on stderr: shared JSON when deployed, text on a TTY.

    Forced, so calling it from both an import and a `main()` leaves one handler rather
    than duplicating every line or keeping an earlier stdout handler.
    """
    configure_logging(
        level=level,
        service=service,
        environment=environment,
        force=True,
        stream=sys.stderr,
        formatter="text" if sys.stderr.isatty() else "json",
    )
    attach_log_context(logging.getLogger())


logger = logging.getLogger(__name__)


def get_logger() -> logging.Logger:
    """This module's logger."""
    return logger
