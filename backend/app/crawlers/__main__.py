"""Entry point for running crawlers: python -m app.crawlers --adapter <name>

Sets CLI-scope log context (request_id=cli:<pid>, user_id=cli) at startup so
every log line produced by the crawler CLI is grep-distinguishable from HTTP
requests + background tasks in CloudWatch Logs (OBS-04 per D-47).

Sentry init lives in 02-02-PLAN.md; this file stays Sentry-free until then.
"""

import os

from app.core.log_context import request_id_var, user_id_var
from app.crawlers.runner import main

if __name__ == "__main__":
    request_id_var.set(f"cli:{os.getpid()}")
    user_id_var.set("cli")
    main()
