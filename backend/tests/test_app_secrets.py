import json
import os

import boto3
import pytest
from moto import mock_aws

from app.core.config import Settings
from app.core.secrets import apply_app_secrets


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("APP_SECRETS_ARN", "SECRET_KEY", "SENTRY_DSN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")


@mock_aws
def test_apply_app_secrets_sets_env_and_settings(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(
        Name="carmodpicker-test/app",
        SecretString=json.dumps({"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1"}),
    )["ARN"]
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
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(
        Name="carmodpicker-test/app",
        SecretString=json.dumps({"SECRET_KEY": None, "NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": 42}),
    )["ARN"]

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
