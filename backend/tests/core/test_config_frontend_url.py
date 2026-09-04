import pytest

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, SECRET_KEY="x", **overrides)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    ("app_environment", "debug", "base_url", "rp_id", "origins"),
    [
        ("development", True, "http://localhost:4000", "localhost", ["http://localhost:4000", "http://localhost:8000"]),
        (
            "development",
            False,
            "http://localhost:4000",
            "localhost",
            ["http://localhost:4000", "http://localhost:8000"],
        ),
        (
            "staging",
            False,
            "https://staging.carmodpicker.com",
            "staging.carmodpicker.com",
            ["https://staging.carmodpicker.com"],
        ),
        (
            "production",
            False,
            "https://www.carmodpicker.com",
            "carmodpicker.com",
            ["https://carmodpicker.com", "https://www.carmodpicker.com"],
        ),
    ],
)
def test_defaults_when_frontend_url_unset(
    app_environment: str, debug: bool, base_url: str, rp_id: str, origins: list[str]
) -> None:
    s = _settings(APP_ENVIRONMENT=app_environment, DEBUG=debug, FRONTEND_URL="")
    assert s.frontend_base_url == base_url
    assert s.webauthn_rp_id == rp_id
    assert s.webauthn_origins_list == origins


@pytest.mark.parametrize(
    ("frontend_url", "app_environment", "base_url", "rp_id", "origins"),
    [
        (
            "https://d123.cloudfront.net",
            "staging",
            "https://d123.cloudfront.net",
            "d123.cloudfront.net",
            ["https://d123.cloudfront.net"],
        ),
        (
            "https://d123.cloudfront.net/",
            "staging",
            "https://d123.cloudfront.net",
            "d123.cloudfront.net",
            ["https://d123.cloudfront.net"],
        ),
        (
            "https://staging.carmodpicker.com",
            "staging",
            "https://staging.carmodpicker.com",
            "staging.carmodpicker.com",
            ["https://staging.carmodpicker.com"],
        ),
        (
            "https://carmodpicker.com",
            "production",
            "https://carmodpicker.com",
            "carmodpicker.com",
            ["https://carmodpicker.com", "https://www.carmodpicker.com"],
        ),
        (
            "https://www.carmodpicker.com",
            "production",
            "https://www.carmodpicker.com",
            "www.carmodpicker.com",
            ["https://www.carmodpicker.com", "https://carmodpicker.com"],
        ),
        (
            "http://localhost:4000",
            "development",
            "http://localhost:4000",
            "localhost",
            ["http://localhost:4000"],
        ),
        (
            "https://app.example.com/base/",
            "production",
            "https://app.example.com/base",
            "app.example.com",
            ["https://app.example.com"],
        ),
    ],
)
def test_frontend_url_drives_base_url_rp_id_and_origins(
    frontend_url: str, app_environment: str, base_url: str, rp_id: str, origins: list[str]
) -> None:
    s = _settings(APP_ENVIRONMENT=app_environment, DEBUG=False, FRONTEND_URL=frontend_url)
    assert s.frontend_base_url == base_url
    assert s.webauthn_rp_id == rp_id
    assert s.webauthn_origins_list == origins


def test_frontend_url_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://d456.cloudfront.net")
    s = Settings(_env_file=None, SECRET_KEY="x", APP_ENVIRONMENT="staging", DEBUG=False)  # type: ignore[call-arg]
    assert s.frontend_base_url == "https://d456.cloudfront.net"
    assert s.webauthn_rp_id == "d456.cloudfront.net"
    assert s.webauthn_origins_list == ["https://d456.cloudfront.net"]
