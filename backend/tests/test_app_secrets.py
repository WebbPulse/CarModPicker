import importlib.util
import json
import logging
import os
import warnings
from pathlib import Path
from types import ModuleType

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from app.core import config as config_module
from app.core.config import Settings
from app.core.secrets import apply_app_secrets, load_app_secrets

MISSING_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:123456789012:secret:carmodpicker-test/missing-AbCdEf"


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_SECRETS_ARN", "SECRET_KEY", "SENTRY_DSN", "NOT_A_SETTING", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")


def create_app_secret(payload: dict[str, object]) -> tuple[object, str]:
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(Name="carmodpicker-test/app", SecretString=json.dumps(payload))["ARN"]
    return client, arn


def import_fresh_config() -> ModuleType:
    spec = importlib.util.spec_from_file_location("config_under_test", Path(config_module.__file__))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@mock_aws
def test_load_app_secrets_populates_env_before_settings_are_built(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, arn = create_app_secret({"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")

    applied = load_app_secrets(client=client)

    assert applied == {"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"}
    assert os.environ["SECRET_KEY"] == "from-secret"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        built = Settings()
    assert built.SECRET_KEY == "from-secret"
    assert built.SENTRY_DSN == "https://k@sentry.example/1"
    assert not [w for w in caught if "SECRET_KEY is empty" in str(w.message)]


@mock_aws
def test_load_app_secrets_logs_and_raises_when_secret_unreadable(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)

    with caplog.at_level(logging.ERROR, logger="app.core.secrets"):
        with pytest.raises(ClientError):
            load_app_secrets()

    assert "Failed to load application secrets" in caplog.text
    assert "SECRET_KEY" not in os.environ


@mock_aws
def test_load_app_secrets_rejects_non_object_payload(clean_env: None) -> None:
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(Name="carmodpicker-test/app", SecretString=json.dumps(["not", "a", "dict"]))["ARN"]

    with pytest.raises(ValueError):
        load_app_secrets(secret_arn=arn, client=client)


def test_load_app_secrets_is_noop_without_arn(clean_env: None) -> None:
    assert load_app_secrets() == {}
    assert "SECRET_KEY" not in os.environ


@mock_aws
def test_config_module_overlays_secrets_before_constructing_settings(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, arn = create_app_secret({"SECRET_KEY": "from-secret", "SENTRY_DSN": ""})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fresh = import_fresh_config()

    assert fresh.settings.SECRET_KEY == "from-secret"
    assert fresh.settings.SENTRY_DSN == ""
    assert not [w for w in caught if "SECRET_KEY is empty" in str(w.message)]


@mock_aws
def test_config_module_import_fails_loudly_when_secret_unreadable(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)

    with caplog.at_level(logging.ERROR, logger="app.core.secrets"):
        with pytest.raises(ClientError):
            import_fresh_config()

    assert "Failed to load application secrets" in caplog.text


@mock_aws
def test_apply_app_secrets_sets_env_and_settings(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    client, arn = create_app_secret({"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)

    settings = Settings(SECRET_KEY="", SENTRY_DSN="")
    applied = apply_app_secrets(settings, client=client)

    assert applied == {"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"}
    assert settings.SECRET_KEY == "from-secret"
    assert settings.SENTRY_DSN == "https://k@sentry.example/1"
    assert os.environ["SECRET_KEY"] == "from-secret"
    assert os.environ["SENTRY_DSN"] == "https://k@sentry.example/1"


@mock_aws
def test_apply_app_secrets_skips_null_and_unknown_fields(clean_env: None) -> None:
    client, arn = create_app_secret({"SECRET_KEY": None, "NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": 42})

    settings = Settings(SECRET_KEY="")
    applied = apply_app_secrets(settings, secret_arn=arn, client=client)

    assert applied == {"NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": "42"}
    assert settings.SECRET_KEY == ""
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 42
    assert os.environ["NOT_A_SETTING"] == "x"
    assert "SECRET_KEY" not in os.environ


def test_apply_app_secrets_is_noop_without_arn(clean_env: None) -> None:
    settings = Settings(SECRET_KEY="unchanged")

    assert apply_app_secrets(settings) == {}
    assert settings.SECRET_KEY == "unchanged"
    assert "SECRET_KEY" not in os.environ
