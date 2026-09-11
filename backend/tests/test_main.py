"""Covers the root, liveness and readiness endpoints and the lifespan startup switch."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.core.config import settings


def test_read_root(client: TestClient) -> None:
    """The root endpoint names the service and reports it running."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CarModPicker API"
    assert data["status"] == "running"


def test_health_check(client: TestClient) -> None:
    """The liveness probe reports healthy without touching the database."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CarModPicker API"
    assert "version" in data


def test_readiness_check(client: TestClient) -> None:
    """The readiness probe reports database reachability rather than liveness."""
    response = client.get("/ready")
    assert response.status_code in (200, 503)
    data = response.json()
    if response.status_code == 200:
        assert data["status"] == "ready"
        assert data["database"] == "up"
    else:
        assert "database" in data or "message" in data


@pytest.mark.parametrize("run_startup_tasks", [True, False])
def test_lifespan_honors_run_startup_tasks(monkeypatch: pytest.MonkeyPatch, run_startup_tasks: bool) -> None:
    """Startup tasks run on lifespan only when RUN_STARTUP_TASKS is set."""
    monkeypatch.setattr(settings, "RUN_STARTUP_TASKS", run_startup_tasks)
    with patch.object(main_module, "run_startup_tasks") as startup:
        with TestClient(main_module.app):
            pass
    assert startup.called is run_startup_tasks
