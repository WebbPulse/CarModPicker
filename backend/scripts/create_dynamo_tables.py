"""Create every DynamoDB table the app expects, skipping ones that already exist.

Meant for local development against DynamoDB Local (``docker compose up -d``
then ``DYNAMODB_ENDPOINT_URL=http://localhost:8001``). In AWS the tables are
managed by Terraform from ``terraform/dynamodb_tables.json``.

Usage (from backend/):
    python scripts/create_dynamo_tables.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.dynamo.client import get_client, table_name  # noqa: E402
from app.db.dynamo.tables import TABLES  # noqa: E402


def main() -> int:
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
