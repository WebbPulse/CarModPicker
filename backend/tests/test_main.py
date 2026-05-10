from fastapi.testclient import TestClient


def test_read_root(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CarModPicker API"
    assert data["status"] == "running"


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint for monitoring (liveness)."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CarModPicker API"
    assert "version" in data


def test_readiness_check(client: TestClient) -> None:
    """Test readiness check endpoint (DB reachable)."""
    response = client.get("/ready")
    # With test DB, should return 200 when DB is ready
    assert response.status_code in (200, 503)
    data = response.json()
    if response.status_code == 200:
        assert data["status"] == "ready"
        assert data["database"] == "up"
    else:
        assert "database" in data or "message" in data
