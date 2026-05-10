"""
Identifies the currently-running Python process so we can detect background
jobs whose owning process died before they finished.

``WORKER_INSTANCE_ID`` is generated once at import time. Every app boot — fresh
start, uvicorn --reload auto-restart, SIGKILL recovery, container redeploy —
produces a new value. In-process background jobs stamp this ID on their
BackgroundJob row; on the next boot, any "running" row whose ID doesn't match
the new process is provably orphaned and the startup sweep marks it failed.
"""

from uuid import uuid4

WORKER_INSTANCE_ID: str = uuid4().hex
