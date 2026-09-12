"""Fixtures for the identity migration script tests.

The scripts reach DynamoDB through webbpulse.dynamodb.Repository, so this module pins
AWS_DEFAULT_REGION to match the moto tables and resets the package's cached resource
around every test.
"""

from __future__ import annotations

from typing import Any, Generator

import pytest

PREFIX = "test"

REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _package_repository_region(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Point `webbpulse.dynamodb.Repository` at moto, and never at a cached one."""
    from webbpulse.dynamodb import reset_resource_cache

    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_REGION", REGION)
    reset_resource_cache()
    try:
        yield
    finally:
        reset_resource_cache()


@pytest.fixture
def credentials_table(dynamo_tables: Any) -> Any:
    """The identity `credentials` table: hash `user_id`, range `credential_type`, no TTL."""
    resource = dynamo_tables
    resource.create_table(
        TableName=f"{PREFIX}-credentials",
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "credential_type", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "credential_type", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return resource


@pytest.fixture
def totp_factors_table(dynamo_tables: Any) -> Any:
    """The identity totp-factors table: hash user_id, no range key, and deliberately no TTL.

    A TTL here would silently drop a user's second factor.
    """
    resource = dynamo_tables
    resource.create_table(
        TableName=f"{PREFIX}-totp-factors",
        KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    return resource
