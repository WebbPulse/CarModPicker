"""Create every DynamoDB table the app expects, skipping ones that already exist.

Meant for local development against DynamoDB Local (``docker compose up -d``
then ``DYNAMODB_ENDPOINT_URL=http://localhost:8001``). In AWS the tables are
managed by Terraform from ``terraform/dynamodb_tables.json``.

The ten identity tables come from ``webbpulse.identity.storage.TABLES``, which carries
the specs ``platform-modules/aws//modules/identity`` provisions, rather than being
described again here. Without them a local stack serves the whole ``/api/auth`` surface
against tables that do not exist, so no sign-in can succeed.

Usage (from backend/):
    python scripts/create_dynamo_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.common.core.config import settings  # noqa: E402
from app.common.db.dynamo.client import get_client, table_name  # noqa: E402
from app.common.db.dynamo.tables import TABLES  # noqa: E402


def create_identity_tables(client: Any, existing: set[str]) -> None:
    """Create the identity package's own tables, and set the TTL each one declares.

    TTL is not part of ``CreateTable``, so it is applied separately; DynamoDB Local
    accepts the call and a refresh token row then expires the way a deployed one does.
    """
    from webbpulse.identity.storage import TABLES as IDENTITY_TABLES

    prefix = settings.dynamodb_table_prefix
    for spec in IDENTITY_TABLES:
        name = spec.table_name(prefix)
        if name in existing:
            print(f"exists  {name}")
            continue
        client.create_table(**spec.create_table_request(prefix))
        print(f"created {name}")
        if spec.ttl_attribute:
            client.update_time_to_live(
                TableName=name,
                TimeToLiveSpecification={"Enabled": True, "AttributeName": spec.ttl_attribute},
            )


def main() -> int:
    """Create any missing table and return 0, or 1 if DYNAMODB_ENDPOINT_URL is unset."""
    if not settings.DYNAMODB_ENDPOINT_URL:
        print(
            "DYNAMODB_ENDPOINT_URL is not set; refusing to create tables against a real AWS account.",
            file=sys.stderr,
        )
        return 1
    client = get_client()
    existing = set(client.list_tables()["TableNames"])
    for spec in TABLES:
        name = table_name(spec)
        if name in existing:
            print(f"exists  {name}")
            continue
        client.create_table(**spec.create_table_request(name))
        print(f"created {name}")
    create_identity_tables(client, existing)
    return 0


if __name__ == "__main__":
    sys.exit(main())
