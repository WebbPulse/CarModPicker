"""Entry point for running crawlers: python -m app.crawlers --adapter <name>

Sets CLI-scope log context (request_id=cli:<pid>, user_id=cli) at startup so
every log line produced by the crawler CLI is grep-distinguishable from HTTP
requests + background tasks in CloudWatch Logs (OBS-04 per D-47).

Also initializes Sentry with server_name="crawler-cli" so CLI-triggered
exceptions land in Sentry tagged distinctly from App Runner + ECS crawler
runs (OBS-01 per D-11). Both calls sit inside the `__main__` guard so test
collection cannot pollute ContextVars or fire Sentry init.
"""

import os

from app.core.log_context import request_id_var, user_id_var
from app.core.sentry import init_sentry
from app.crawlers.runner import main

if __name__ == "__main__":
    init_sentry(server_name="crawler-cli")
    request_id_var.set(f"cli:{os.getpid()}")
    user_id_var.set("cli")
    main()
