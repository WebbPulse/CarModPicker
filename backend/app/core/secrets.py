from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

import boto3
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)


def load_app_secrets(secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    arn = secret_arn if secret_arn is not None else os.getenv("APP_SECRETS_ARN", "")
    if not arn:
        return {}

    try:
        secrets_client = client if client is not None else boto3.client("secretsmanager")
        response = secrets_client.get_secret_value(SecretId=arn)
        payload = json.loads(response["SecretString"])
    except Exception:
        logger.exception("Failed to load application secrets from %s", arn)
        raise
    if not isinstance(payload, dict):
        logger.error("Secret %s is not a JSON object", arn)
        raise ValueError("APP_SECRETS_ARN secret must be a JSON object")

    applied: dict[str, str] = {}
    for name, raw_value in payload.items():
        if raw_value is None:
            continue
        value = raw_value if isinstance(raw_value, str) else json.dumps(raw_value)
        os.environ[name] = value
        applied[name] = value
    logger.info("Loaded %d application secrets from %s: %s", len(applied), arn, ", ".join(sorted(applied)))
    return applied


def apply_app_secrets(settings: Settings, secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    applied = load_app_secrets(secret_arn, client)
    for name, value in applied.items():
        field = type(settings).model_fields.get(name)
        if field is not None:
            setattr(settings, name, TypeAdapter(field.annotation).validate_python(value))
    return applied
