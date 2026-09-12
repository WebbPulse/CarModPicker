"""Tests for loading the application's JSON secret from Secrets Manager.

Covers env precedence, caching, error types, and that importing a module fetches nothing.
"""

import importlib.util
import json
import logging
import os
import subprocess  # nosec B404
import sys
import warnings
from pathlib import Path
from types import ModuleType

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws
from webbpulse.config import SecretNotJsonObjectError

from app.composition.domains import ENTRYPOINT_MODULES
from app.core import config as config_module
from app.core.config import Settings
from app.core.secrets import apply_app_secrets, fetch_app_secrets, load_app_secrets, reset_cache

MISSING_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:123456789012:secret:carmodpicker-test/missing-AbCdEf"

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the secret-backed variables, set fake AWS credentials, and reset the cache."""
    for name in ("APP_SECRETS_ARN", "SECRET_KEY", "SENTRY_DSN", "NOT_A_SETTING", "ACCESS_TOKEN_EXPIRE_MINUTES"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    reset_cache()


def create_app_secret(payload: dict[str, object]) -> tuple[object, str]:
    """Create the app secret in moto and return the client and its ARN."""
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(Name="carmodpicker-test/app", SecretString=json.dumps(payload))["ARN"]
    return client, arn


def import_fresh_config() -> ModuleType:
    """Import the config module under a fresh name so module level work runs again."""
    spec = importlib.util.spec_from_file_location("config_under_test", Path(config_module.__file__))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@mock_aws
def test_load_app_secrets_populates_env_before_settings_are_built(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Loading the secret puts its keys in the environment before settings are constructed."""
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
    """An unreadable secret is logged and re-raised rather than swallowed."""
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)

    with caplog.at_level(logging.ERROR, logger="app.core.secrets"):
        with pytest.raises(ClientError):
            load_app_secrets()

    assert "Failed to load application secrets" in caplog.text
    assert "SECRET_KEY" not in os.environ


@mock_aws
def test_load_app_secrets_rejects_non_object_payload(clean_env: None) -> None:
    """A payload that is not a JSON object is rejected."""
    client = boto3.client("secretsmanager", region_name="us-west-2")
    arn = client.create_secret(Name="carmodpicker-test/app", SecretString=json.dumps(["not", "a", "dict"]))["ARN"]

    with pytest.raises(ValueError):
        load_app_secrets(secret_arn=arn, client=client)


def test_load_app_secrets_is_noop_without_arn(clean_env: None) -> None:
    """With no ARN configured the loader does nothing."""
    assert load_app_secrets() == {}
    assert "SECRET_KEY" not in os.environ


@mock_aws
def test_config_module_overlays_secrets_before_constructing_settings(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config module overlays secret values before it constructs Settings."""
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
def test_config_module_imports_without_reading_the_secret(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing config makes no Secrets Manager call, even with an unreadable ARN set."""
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)

    fresh = import_fresh_config()

    assert fresh.settings.APP_SECRETS_ARN == MISSING_SECRET_ARN


@mock_aws
def test_reading_a_secret_fails_loudly_when_the_secret_is_unreadable(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The loud failure is preserved, just deferred to the point of use."""
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)
    fresh = import_fresh_config()

    with caplog.at_level(logging.ERROR, logger="app.core.secrets"):
        with pytest.raises(ClientError):
            _ = fresh.settings.SECRET_KEY

    assert "Failed to load application secrets" in caplog.text


@mock_aws
def test_require_secrets_raises_when_a_secret_is_absent(clean_env: None) -> None:
    """Requiring an absent secret raises naming the field."""
    from app.core.config import Settings

    settings = Settings()

    with pytest.raises(ValueError, match="SECRET_KEY"):
        settings.require_secrets("SECRET_KEY")


@mock_aws
def test_require_secrets_passes_when_the_secret_resolves(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Requiring a secret that resolves passes and exposes the value."""
    from app.core.config import Settings

    _, arn = create_app_secret({"SECRET_KEY": "from-secret"})
    monkeypatch.setenv("APP_SECRETS_ARN", arn)

    settings = Settings()

    settings.require_secrets("SECRET_KEY")
    assert settings.SECRET_KEY == "from-secret"


def test_require_secrets_rejects_an_unknown_name(clean_env: None) -> None:
    """Requiring a name that is not a known secret raises."""
    from app.core.config import Settings

    with pytest.raises(ValueError, match="Unknown secret"):
        Settings().require_secrets("NOT_A_SECRET")


def test_env_var_wins_over_the_secret(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """An environment variable short circuits the fetch entirely, which is what
    keeps local development and the test suite free of AWS."""
    from app.core.config import Settings

    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)
    monkeypatch.setenv("SECRET_KEY", "from-env")

    assert Settings().SECRET_KEY == "from-env"


@mock_aws
def test_apply_app_secrets_sets_env_and_settings(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Applying the secret sets both the settings fields and the environment."""
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
    """Null values are skipped and unknown keys reach the environment only."""
    client, arn = create_app_secret({"SECRET_KEY": None, "NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": 42})

    settings = Settings(SECRET_KEY="")
    applied = apply_app_secrets(settings, secret_arn=arn, client=client)

    assert applied == {"NOT_A_SETTING": "x", "ACCESS_TOKEN_EXPIRE_MINUTES": "42"}
    assert settings.SECRET_KEY == ""
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 42
    assert os.environ["NOT_A_SETTING"] == "x"
    assert "SECRET_KEY" not in os.environ


def test_apply_app_secrets_is_noop_without_arn(clean_env: None) -> None:
    """With no ARN configured applying the secret changes nothing."""
    settings = Settings(SECRET_KEY="unchanged")

    assert apply_app_secrets(settings) == {}
    assert settings.SECRET_KEY == "unchanged"
    assert "SECRET_KEY" not in os.environ


def test_config_imports_with_no_aws_credentials_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config imports with every AWS variable stripped and makes no call."""
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
        "SECRET_KEY",
        "SENTRY_DSN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_SECRETS_ARN", MISSING_SECRET_ARN)
    reset_cache()

    fresh = import_fresh_config()

    assert fresh.settings.APP_SECRETS_ARN == MISSING_SECRET_ARN


class CallCountingSecretsClient:
    """A stand-in for the shared loader's boto3 client that counts its calls."""

    def __init__(self, payload: object) -> None:
        """Hold the payload to return and start the call count at zero."""
        self.payload = payload
        self.calls = 0

    def get_secret_value(self, SecretId: str) -> dict[str, str]:  # noqa: N803
        """Count the call and return the payload as a secret string."""
        self.calls += 1
        return {"SecretString": json.dumps(self.payload)}


@pytest.fixture
def counting_client(monkeypatch: pytest.MonkeyPatch):
    """Install a call-counting client under the shared loader and hand back the installer."""

    def install(payload: object) -> CallCountingSecretsClient:
        """Patch in a counting client for this payload and return it."""
        client = CallCountingSecretsClient(payload)
        monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: client)
        reset_cache()
        return client

    yield install
    reset_cache()


ENTRYPOINT_IMPORT_TARGETS = [
    "app.core.config",
    "app.composition.app",
    "app.composition.domains",
    "app.composition.wiring",
] + [f"app.entrypoints.{module}" for module in sorted(ENTRYPOINT_MODULES.values())]

NO_FETCH_PROBE = """
import json, boto3


def _forbidden(*args, **kwargs):
    raise AssertionError("boto3.client was called during import")


boto3.client = _forbidden
import {module}  # noqa: E402
print(json.dumps({{"imported": "{module}"}}))
"""


def run_probe(code: str, env: dict[str, str] | None = None) -> dict[str, object]:
    """Run one snippet in a fresh interpreter with an all but empty environment."""
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    environment.update(env or {})
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", code],
        cwd=str(BACKEND),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("module_name", ENTRYPOINT_IMPORT_TARGETS)
def test_importing_a_module_makes_no_secrets_manager_call(module_name: str) -> None:
    """Importing settings, composition or any entrypoint fetches no secret."""
    probe = run_probe(
        NO_FETCH_PROBE.format(module=module_name),
        env={"APP_SECRETS_ARN": MISSING_SECRET_ARN},
    )

    assert probe["imported"] == module_name


def test_first_read_fetches_once_and_later_reads_do_not(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, counting_client
) -> None:
    """The blob is fetched once per execution environment however many fields are read."""
    client = counting_client(
        {"SECRET_KEY": "from-secret", "SENTRY_DSN": "https://k@sentry.example/1", "EXTENSION_API_KEY": "ext-key"}
    )
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf")

    settings = Settings()
    assert client.calls == 0

    assert settings.SECRET_KEY == "from-secret"
    assert client.calls == 1

    assert settings.SECRET_KEY == "from-secret"
    assert settings.SENTRY_DSN == "https://k@sentry.example/1"
    assert settings.EXTENSION_API_KEY == "ext-key"
    assert Settings().SECRET_KEY == "from-secret"
    assert client.calls == 1


def test_reset_cache_forces_a_refetch(clean_env: None, monkeypatch: pytest.MonkeyPatch, counting_client) -> None:
    """Resetting the cache clears the shared loader's parse as well as the local map."""
    client = counting_client({"SECRET_KEY": "first"})
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf")

    assert Settings().SECRET_KEY == "first"
    assert client.calls == 1

    client.payload = {"SECRET_KEY": "second"}
    assert Settings().SECRET_KEY == "first"
    assert client.calls == 1

    reset_cache()

    assert Settings().SECRET_KEY == "second"
    assert client.calls == 2


def test_malformed_secret_raises_a_value_error(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, counting_client
) -> None:
    """A JSON array payload raises a ValueError subclass when a field is read."""
    counting_client(["not", "a", "dict"])
    monkeypatch.setenv("APP_SECRETS_ARN", "arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf")

    with pytest.raises(ValueError):
        _ = Settings().SECRET_KEY

    assert issubclass(SecretNotJsonObjectError, ValueError)


def test_malformed_secret_through_an_injected_client_raises_the_same_error(clean_env: None) -> None:
    """The injected-client path raises the same error type as the shared loader."""
    client = CallCountingSecretsClient(["not", "a", "dict"])

    with pytest.raises(ValueError):
        fetch_app_secrets(
            secret_arn="arn:aws:secretsmanager:us-west-2:123456789012:secret:cmp/app-AbCdEf", client=client
        )


def test_no_arn_makes_no_call_at_all(clean_env: None, counting_client) -> None:
    """With no ARN the environment path short circuits and no client is built."""
    client = counting_client({"SECRET_KEY": "from-secret"})

    assert Settings().SECRET_KEY == ""
    assert fetch_app_secrets() == {}
    assert client.calls == 0
