from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import boto3
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from app.core.config import Settings


def apply_app_secrets(settings: Settings, secret_arn: str | None = None, client: Any = None) -> dict[str, str]:
    arn = secret_arn if secret_arn is not None else os.getenv("APP_SECRETS_ARN", "")
    if not arn:
        return {}

    secrets_client = client if client is not None else boto3.client("secretsmanager")
    response = secrets_client.get_secret_value(SecretId=arn)
    payload = json.loads(response["SecretString"])
    if not isinstance(payload, dict):
        raise ValueError("APP_SECRETS_ARN secret must be a JSON object")

    applied: dict[str, str] = {}
    for name, raw_value in payload.items():
        if raw_value is None:
            continue
        value = raw_value if isinstance(raw_value, str) else json.dumps(raw_value)
        os.environ[name] = value
        field = type(settings).model_fields.get(name)
        if field is not None:
            setattr(settings, name, TypeAdapter(field.annotation).validate_python(value))
        applied[name] = value
    return applied
