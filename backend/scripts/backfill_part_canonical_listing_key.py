"""Write the canonical index key onto canonical part rows that predate it.

The sitemap and GTIN dedupe read canonical parts from the sparse
`canonical_listing-created_at-index`, whose hash key is the `canonical_listing`
attribute every write now derives for a part without `canonical_part_id`
(CAR-36). Canonical rows written before that change lack it and stay out of
those reads until this runs.

Idempotent: the scan only returns canonical rows missing the attribute, and each
write is conditioned on the row still existing, still being canonical and still
lacking it, so a rerun, or a part deleted, linked or rewritten mid-run, changes
nothing. Linked duplicates and `#unique#` sentinel rows are skipped. Dry run
unless `--apply` is passed.

Usage, from backend/, with credentials for the target account:
    python scripts/backfill_part_canonical_listing_key.py --prefix carmodpicker-staging
    python scripts/backfill_part_canonical_listing_key.py --prefix carmodpicker-staging --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

for _name, _placeholder in (
    ("SECRET_KEY", "migration"),
    ("EMAIL_FROM", "migration@example.com"),
):
    os.environ.setdefault(_name, _placeholder)

from app.common.db.dynamo.serialization import UNIQUE_KEY_PREFIX  # noqa: E402
from app.common.db.dynamo.tables import (  # noqa: E402
    PART_CANONICAL_LISTING_ATTRIBUTE,
    PART_CANONICAL_LISTING_PARTITION,
    PARTS,
)

CANONICAL_PART_ID = "canonical_part_id"

CONDITIONAL_CHECK_FAILED = "ConditionalCheckFailedException"


def build_table(prefix: str, endpoint_url: str | None = None, region_name: str | None = None) -> Any:
    """The boto3 Table for this environment's parts."""
    from webbpulse.dynamodb import Repository

    return Repository(
        PARTS.suffix,
        prefix=prefix,
        endpoint_url=endpoint_url or None,
        region_name=region_name or None,
    ).table


def iter_missing_ids(table: Any) -> Iterator[str]:
    """The ids of canonical part rows without the canonical index attribute, sentinels excluded."""
    from boto3.dynamodb.conditions import Attr

    id_name = PARTS.partition_key.name
    missing = (
        Attr(PART_CANONICAL_LISTING_ATTRIBUTE).not_exists()
        & Attr(CANONICAL_PART_ID).not_exists()
        & ~Attr(id_name).begins_with(UNIQUE_KEY_PREFIX)
    )
    start_key: dict[str, Any] | None = None
    while True:
        kwargs: dict[str, Any] = {
            "FilterExpression": missing,
            "ProjectionExpression": "#id",
            "ExpressionAttributeNames": {"#id": id_name},
        }
        if start_key is not None:
            kwargs["ExclusiveStartKey"] = start_key
        response = table.scan(**kwargs)
        for item in response.get("Items", []):
            yield str(item[id_name])
        start_key = response.get("LastEvaluatedKey")
        if not start_key:
            return


def backfill(table: Any, *, apply: bool) -> dict[str, int]:
    """Set the canonical index attribute on every canonical row missing it, counting each outcome."""
    from botocore.exceptions import ClientError

    summary = {"missing": 0, "written": 0, "skipped": 0}
    for part_id in iter_missing_ids(table):
        summary["missing"] += 1
        if not apply:
            continue
        try:
            table.update_item(
                Key={PARTS.partition_key.name: part_id},
                UpdateExpression="SET #listing = :listing",
                ConditionExpression=(
                    "attribute_exists(#id) AND attribute_not_exists(#canonical) AND attribute_not_exists(#listing)"
                ),
                ExpressionAttributeNames={
                    "#id": PARTS.partition_key.name,
                    "#canonical": CANONICAL_PART_ID,
                    "#listing": PART_CANONICAL_LISTING_ATTRIBUTE,
                },
                ExpressionAttributeValues={":listing": PART_CANONICAL_LISTING_PARTITION},
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != CONDITIONAL_CHECK_FAILED:
                raise
            summary["skipped"] += 1
            continue
        summary["written"] += 1
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line; the run is a dry run unless --apply is passed."""
    parser = argparse.ArgumentParser(
        description="Backfill the canonical index key on canonical part rows. Dry run unless --apply is passed."
    )
    parser.add_argument(
        "--prefix",
        default=os.environ.get("DYNAMODB_TABLE_PREFIX"),
        help="DynamoDB table prefix (default: $DYNAMODB_TABLE_PREFIX)",
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("DYNAMODB_ENDPOINT_URL"),
        help="DynamoDB endpoint (default: $DYNAMODB_ENDPOINT_URL, else AWS)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
        help="AWS region (default: $AWS_REGION, then $AWS_DEFAULT_REGION, else boto3's)",
    )
    parser.add_argument("--apply", action="store_true", help="actually write; without it only count")
    args = parser.parse_args(argv)
    if not args.prefix:
        parser.error("--prefix is required when DYNAMODB_TABLE_PREFIX is not set")
    return args


def main(argv: list[str] | None = None) -> int:
    """Run the backfill and print its summary."""
    args = parse_args(argv)
    summary = backfill(build_table(args.prefix, args.endpoint_url, args.region), apply=args.apply)
    mode = "applied" if args.apply else "dry run"
    print(f"{mode}: {summary['missing']} missing, {summary['written']} written, {summary['skipped']} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
