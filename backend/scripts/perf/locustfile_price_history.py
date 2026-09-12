"""Locust scenario for the price-history perf gate (M002/S05/T05).

Simulates the frontend's sparkline access pattern against two read endpoints:

- ``GET  /api/parts/{id}/price-history?window=90d`` (weight=4, dominant call)
- ``POST /api/parts/price-history``                  (weight=1, batch summary)

The POST is authenticated: it takes ``require_api_key_or_admin``, so it wants
either ``X-API-Key`` matching the environment's ``EXTENSION_API_KEY`` or a bearer
token belonging to an **admin** user. Export ``PERF_API_KEY`` (preferred) or
``PERF_BEARER_TOKEN`` before running, or the POST rows come back 401/403 and the
gate reports a 100% error rate. The GET is still public and needs no credential.

Part IDs are loaded from ``backend/.perf-runs/part-id-pool.json`` — the runner
script (run_price_history_loadtest.sh) generates that pool from the DB before
spawning users so every locust process sees the same pool without needing a
DB connection.

Budget enforced by the wrapper script (NOT here):
- GET p95 < 200 ms
- POST p95 < 500 ms
- error rate == 0

If the budget is missed the wrapper opens R036 (materialized part_price_summary)
per D004 - see backend/scripts/perf/README.md.

The pool path is overridable via the PART_ID_POOL_PATH env var so a contributor
can point locust at a custom pool without editing this file. Credentials are
supplied out of band and never committed here.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import List

from locust import HttpUser, between, events, task
from locust.env import Environment

_DEFAULT_POOL_PATH = Path(__file__).resolve().parent.parent.parent / ".perf-runs" / "part-id-pool.json"
PART_ID_POOL_PATH = Path(os.environ.get("PART_ID_POOL_PATH", str(_DEFAULT_POOL_PATH)))

WINDOW = os.environ.get("PERF_WINDOW", "90d")
BATCH_SIZE = int(os.environ.get("PERF_BATCH_SIZE", "50"))

API_KEY = os.environ.get("PERF_API_KEY", "")
BEARER_TOKEN = os.environ.get("PERF_BEARER_TOKEN", "")

_PART_ID_POOL: List[str] = []


def _load_pool() -> List[str]:
    """Read the part-id pool JSON array, raising RuntimeError if it is missing or empty.

    Called from the test_start listener so a bad pool fails fast with a clear
    message instead of a FileNotFoundError inside the first user task.
    """
    if not PART_ID_POOL_PATH.exists():
        raise RuntimeError(
            f"Part ID pool not found at {PART_ID_POOL_PATH}. "
            "Run backend/scripts/perf/run_price_history_loadtest.sh — it generates "
            "the pool before spawning locust."
        )
    with PART_ID_POOL_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list) or not data:
        raise RuntimeError(
            f"Part ID pool at {PART_ID_POOL_PATH} is empty or not a JSON array. "
            "Reseed sample data and rerun the runner."
        )
    return [str(part_id) for part_id in data]


@events.test_start.add_listener
def _on_test_start(environment: Environment, **_: object) -> None:
    """Load the part-id pool exactly once before any user spawns."""
    global _PART_ID_POOL
    _PART_ID_POOL = _load_pool()
    print(
        f"[perf-gate] loaded {len(_PART_ID_POOL)} part IDs from {PART_ID_POOL_PATH} "
        f"(window={WINDOW}, batch_size={BATCH_SIZE})"
    )
    if not API_KEY and not BEARER_TOKEN:
        print(
            "[perf-gate] WARNING: neither PERF_API_KEY nor PERF_BEARER_TOKEN is set. "
            "POST /api/parts/price-history requires an API key or an admin token and "
            "will return 401 for every sample, so the POST budget cannot be measured."
        )


def _auth_headers() -> dict[str, str]:
    """Credential headers for the authenticated POST.

    Prefers the API key, falls back to a bearer token (which must belong to an
    admin user), and returns nothing when neither is configured.
    """
    if API_KEY:
        return {"X-API-Key": API_KEY}
    if BEARER_TOKEN:
        return {"Authorization": f"Bearer {BEARER_TOKEN}"}
    return {}


class PriceHistoryUser(HttpUser):
    """Simulated frontend user hitting the two price-history endpoints.

    1–2 s wait between tasks gives ~1 request/sec/user. With ``--users 50``
    that lands around 25–50 RPS aggregate (well above the 10× = 10 RPS gate
    target). Locust still measures p95 per-endpoint so the scaling is fine.
    """

    wait_time = between(1.0, 2.0)

    @task(4)
    def get_single_price_history(self) -> None:
        """GET one part's price history, reported under a stable stats label.

        The fixed `name` groups every per-id request into one stats row so the
        wrapper script can read the GET percentile without the sample being
        split across one row per UUID.
        """
        if not _PART_ID_POOL:
            return
        part_id = random.choice(_PART_ID_POOL)  # noqa: S311
        self.client.get(
            f"/api/parts/{part_id}/price-history?window={WINDOW}",
            name="GET /api/parts/{id}/price-history",
        )

    @task(1)
    def post_batch_price_history(self) -> None:
        """POST a batch price-history summary for distinct parts.

        Samples without replacement so the batch matches the frontend, where
        each visible card is a distinct part.
        """
        if not _PART_ID_POOL:
            return
        sample_size = min(BATCH_SIZE, len(_PART_ID_POOL))
        part_ids = random.sample(_PART_ID_POOL, sample_size)  # noqa: S311
        self.client.post(
            "/api/parts/price-history",
            json={"part_ids": part_ids, "window": WINDOW},
            name="POST /api/parts/price-history",
            headers=_auth_headers(),
        )
