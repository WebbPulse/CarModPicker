"""Copy the legacy Postgres data into the DynamoDB tables.

Run from backend/ against the production account, after Terraform has
created the tables and before ``api_target`` is flipped to ``lambda``:

    pip install psycopg2-binary            # not in requirements.txt any more
    export DATABASE_URL=postgresql://user:pass@host:5432/carmodpicker?sslmode=require
    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess
    export APP_ENVIRONMENT=production      # picks the carmodpicker-production-* tables
    python scripts/backfill_from_postgres.py --dry-run
    python scripts/backfill_from_postgres.py
    python scripts/backfill_from_postgres.py --verify

The copy is idempotent: every row becomes a ``PutItem`` keyed by the same UUID
it had in Postgres, so re-running overwrites rather than duplicates.  Besides
the rows themselves the script writes the ``#unique#`` lookup items the
repositories rely on for username / email / slug / GTIN uniqueness, and fills
the denormalised ``Part`` attributes (``car_ids``, ``best_price_cents``,
``net_votes``) that Postgres computed with joins.

Crawler tables (``crawled_pages``, ``crawler_*``, ``background_jobs``) have no
DynamoDB equivalent and are deliberately left behind.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.dependencies.repositories import Repositories, get_repositories  # noqa: E402
from app.db.dynamo.build_logs import BuildLog  # noqa: E402
from app.db.dynamo.catalog import PartCar, UniqueCatalogRepository  # noqa: E402
from app.db.dynamo.models import DynamoModel  # noqa: E402
from app.db.dynamo.moderation import DOWNVOTE, UPVOTE  # noqa: E402
from app.db.dynamo.repository import DynamoRepository  # noqa: E402
from app.db.dynamo.serialization import composite_key, encode_bytes  # noqa: E402
from app.db.dynamo.users import (  # noqa: E402
    CREDENTIAL_ID,
    EMAIL,
    PROVIDER_ACCOUNT,
    USER_PROVIDER,
    USERNAME,
)

logger = logging.getLogger("backfill")

Row = dict[str, Any]
Rows = dict[str, list[Row]]

# (postgres table, Repositories attribute) in the order the tables are copied.
# Order only matters for readability: DynamoDB enforces no foreign keys.
TABLES: tuple[tuple[str, str], ...] = (
    ("users", "users"),
    ("oauth_accounts", "oauth_accounts"),
    ("webauthn_credentials", "webauthn_credentials"),
    ("car_makes", "car_makes"),
    ("car_models", "car_models"),
    ("car_generations", "car_generations"),
    ("categories", "categories"),
    ("retailers", "retailers"),
    ("part_manufacturers", "part_manufacturers"),
    ("parts", "parts"),
    ("part_cars", "part_cars"),
    ("part_listings", "part_listings"),
    ("part_price_history", "part_price_history"),
    ("part_price_alerts", "part_price_alerts"),
    ("build_lists", "build_lists"),
    ("build_list_parts", "build_list_parts"),
    ("build_list_phases", "build_list_phases"),
    ("build_list_labor_estimates", "build_list_labor_estimates"),
    ("build_logs", "build_logs"),
    ("build_log_posts", "build_log_posts"),
    ("votes", "votes"),
    ("reports", "reports"),
    ("bug_reports", "bug_reports"),
    ("image_source_mappings", "image_source_mappings"),
    ("app_settings", "app_settings"),
)
TABLE_NAMES: tuple[str, ...] = tuple(name for name, _ in TABLES)
SKIPPED_TABLES: tuple[str, ...] = (
    "crawled_pages",
    "crawler_adapter_configs",
    "crawler_schedules",
    "crawler_schedule_adapters",
    "background_jobs",
)


class BackfillError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Postgres
# --------------------------------------------------------------------------


def fetch_rows(conn: Any, tables: Sequence[str] = TABLE_NAMES) -> Rows:
    """``SELECT *`` every table into plain dicts (bytea -> bytes)."""
    rows: Rows = {}
    with conn.cursor() as cur:
        for table in tables:
            cur.execute(f'SELECT * FROM "{table}"')  # nosec B608
            columns = [column[0] for column in cur.description]
            rows[table] = [_clean_row(dict(zip(columns, values))) for values in cur.fetchall()]
            logger.info("fetched %-28s %6d rows", table, len(rows[table]))
    return rows


def _clean_row(row: Row) -> Row:
    return {key: bytes(value) if isinstance(value, memoryview) else value for key, value in row.items()}


def connect(database_url: str) -> Any:
    try:
        import psycopg2  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on the operator's environment
        raise BackfillError("psycopg2 is required: pip install psycopg2-binary") from exc
    return psycopg2.connect(database_url)


# --------------------------------------------------------------------------
# Row -> model
# --------------------------------------------------------------------------


@dataclass
class Plan:
    """Everything the writer needs, computed without touching DynamoDB."""

    models: dict[str, list[DynamoModel]] = field(default_factory=dict)
    lookups: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    created_build_logs: int = 0

    def row_count(self, table: str) -> int:
        return len(self.models.get(table, []))


def build_plan(rows: Rows, repos: Repositories) -> Plan:
    plan = Plan()
    parts_extra = _part_derived_attributes(rows)
    for table, attr in TABLES:
        repo: DynamoRepository[Any] = getattr(repos, attr)
        table_rows = rows.get(table, [])
        models: list[DynamoModel]
        if table == "parts":
            models = [repo.model_cls.model_validate({**row, **parts_extra[row["id"]]}) for row in table_rows]
        elif table == "part_cars":
            models = [PartCar(part_id=row["part_id"], car_id=row["car_id"]) for row in table_rows]  # type: ignore[list-item]
        elif table == "build_logs":
            models = [repo.model_cls.model_validate(row) for row in table_rows]
            missing = _missing_build_logs(rows, models)
            plan.created_build_logs = len(missing)
            models.extend(missing)
        else:
            models = [repo.model_cls.model_validate(row) for row in table_rows]
        plan.models[table] = models
        plan.lookups[table] = _lookup_items(table, repo, models)
    return plan


def _part_derived_attributes(rows: Rows) -> dict[UUID, dict[str, Any]]:
    car_ids: dict[UUID, list[UUID]] = defaultdict(list)
    for row in rows.get("part_cars", []):
        car_ids[row["part_id"]].append(row["car_id"])

    part_rows = rows.get("parts", [])
    group_of: dict[UUID, UUID] = {row["id"]: row.get("canonical_part_id") or row["id"] for row in part_rows}
    group_prices: dict[UUID, list[int]] = defaultdict(list)
    for listing in rows.get("part_listings", []):
        price = listing.get("last_known_price_cents")
        group = group_of.get(listing["part_id"])
        if price is not None and price >= 0 and group is not None:
            group_prices[group].append(price)

    net_votes: dict[UUID, int] = defaultdict(int)
    for vote in rows.get("votes", []):
        if vote.get("entity_type") != "part":
            continue
        if vote.get("vote_type") == UPVOTE:
            net_votes[vote["entity_id"]] += 1
        elif vote.get("vote_type") == DOWNVOTE:
            net_votes[vote["entity_id"]] -= 1

    derived: dict[UUID, dict[str, Any]] = {}
    for row in part_rows:
        prices = group_prices.get(group_of[row["id"]], [])
        derived[row["id"]] = {
            "car_ids": car_ids.get(row["id"], []),
            "best_price_cents": min(prices) if prices else None,
            "net_votes": net_votes.get(row["id"], 0),
        }
    return derived


def _missing_build_logs(rows: Rows, existing: Iterable[DynamoModel]) -> list[BuildLog]:
    """Every build list owns exactly one build log; create the ones Postgres lacks."""
    covered = {getattr(log, "build_list_id") for log in existing}
    return [
        BuildLog(build_list_id=row["id"], title=f"Build Log: {row['name']}")
        for row in rows.get("build_lists", [])
        if row["id"] not in covered
    ]


def _lookup_items(table: str, repo: DynamoRepository[Any], models: Sequence[DynamoModel]) -> list[dict[str, Any]]:
    pairs_for = _unique_pairs_function(table, repo)
    if pairs_for is None:
        return []
    items: list[dict[str, Any]] = []
    owners: dict[tuple[str, str], list[str]] = defaultdict(list)
    for model in models:
        owner = str(model.id)
        for attribute, value in pairs_for(model):
            owners[(attribute, value)].append(owner)
            items.append(repo.unique_lookup_item(attribute, value, owner))
    collisions = {pair: ids for pair, ids in owners.items() if len(ids) > 1}
    if collisions:
        detail = "; ".join(f"{attribute}={value!r} -> {ids}" for (attribute, value), ids in sorted(collisions.items()))
        raise BackfillError(f"{table}: rows collide on a unique attribute, fix them in Postgres first: {detail}")
    return items


def _unique_pairs_function(table: str, repo: DynamoRepository[Any]) -> Callable[[Any], list[tuple[str, str]]] | None:
    if table == "users":
        return lambda user: [(USERNAME, user.username.lower()), (EMAIL, user.email.lower())]
    if table == "oauth_accounts":
        return lambda account: [
            (PROVIDER_ACCOUNT, composite_key(account.provider, account.provider_account_id)),
            (USER_PROVIDER, composite_key(account.user_id, account.provider)),
        ]
    if table == "webauthn_credentials":
        return lambda credential: [(CREDENTIAL_ID, encode_bytes(credential.credential_id))]
    if isinstance(repo, UniqueCatalogRepository):
        return repo.unique_pairs
    return None


# --------------------------------------------------------------------------
# DynamoDB
# --------------------------------------------------------------------------


def write_plan(plan: Plan, repos: Repositories, tables: Sequence[str] = TABLE_NAMES) -> None:
    for table, attr in TABLES:
        if table not in tables:
            continue
        repo: DynamoRepository[Any] = getattr(repos, attr)
        models = plan.models.get(table, [])
        lookups = plan.lookups.get(table, [])
        with repo.table.batch_writer() as batch:
            for model in models:
                batch.put_item(Item=repo.to_item(model))
            for item in lookups:
                batch.put_item(Item=item)
        logger.info("wrote   %-28s %6d items + %d lookups", table, len(models), len(lookups))


def verify_counts(plan: Plan, repos: Repositories, tables: Sequence[str] = TABLE_NAMES) -> dict[str, tuple[int, int]]:
    """``table -> (expected, found)``; ``found`` counts real items, not lookups."""
    result: dict[str, tuple[int, int]] = {}
    for table, attr in TABLES:
        if table not in tables:
            continue
        repo: DynamoRepository[Any] = getattr(repos, attr)
        found = len(repo.scan_all())
        result[table] = (plan.row_count(table), found)
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", default=None, help="defaults to $DATABASE_URL")
    parser.add_argument("--tables", default=None, help="comma-separated subset to write (all tables are still read)")
    parser.add_argument("--dry-run", action="store_true", help="read and validate only, write nothing")
    parser.add_argument("--verify", action="store_true", help="compare DynamoDB item counts with Postgres afterwards")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    database_url = args.database_url or os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.error("DATABASE_URL is not set")
        return 2
    tables: Sequence[str] = TABLE_NAMES
    if args.tables:
        tables = tuple(name.strip() for name in args.tables.split(",") if name.strip())
        unknown = sorted(set(tables) - set(TABLE_NAMES))
        if unknown:
            logger.error("unknown tables: %s", ", ".join(unknown))
            return 2

    repos = get_repositories()
    conn = connect(database_url)
    try:
        rows = fetch_rows(conn)
    finally:
        conn.close()

    try:
        plan = build_plan(rows, repos)
    except BackfillError as exc:
        logger.error("%s", exc)
        return 1
    if plan.created_build_logs:
        logger.info("creating %d build logs for build lists that had none", plan.created_build_logs)
    logger.info("skipping %s (no DynamoDB equivalent)", ", ".join(SKIPPED_TABLES))

    if args.dry_run:
        logger.info("dry run: nothing written")
        return 0

    write_plan(plan, repos, tables)
    if args.verify:
        mismatched = False
        for table, (expected, found) in verify_counts(plan, repos, tables).items():
            status = "ok" if expected == found else "MISMATCH"
            mismatched = mismatched or expected != found
            logger.info("verify  %-28s expected %6d found %6d %s", table, expected, found, status)
        if mismatched:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
