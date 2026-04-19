#!/usr/bin/env python3
"""
Bootstrap prod with locally-crawled archive: S3 HTML + crawled_pages rows.

What this does:
    For every local crawled_pages row with html_s3_key set that is NOT already
    in the prod DB (by url), copy the HTML object from the local MinIO bucket
    to the prod S3 bucket and insert the matching row into the prod DB.

Rows that already exist in the prod DB (by url) are fully skipped — neither
the S3 object nor the DB row is touched. This makes the script idempotent
and cheap to re-run. It is one-way: local -> prod.

Columns copied into prod:

    id, url, source, html_s3_key, html_sha256, crawled_at

Columns reset on the prod side (intentionally not copied):

    html_local_path  -> NULL        (local-only concept)
    last_parsed_at   -> NULL        (prod will re-parse via archive_rescrape)
    parse_status     -> 'pending'   (prod will re-parse)
    part_id          -> NULL        (local part UUIDs don't exist in prod)

Usage (run from backend/):
    python scripts/sync_crawl_archive_to_prod.py [--dry-run] [--source ADAPTER]
                                                  [--limit N] [--batch-size N]

Required env vars:
    DATABASE_URL                local Postgres url        (from .env)
    AWS_ENDPOINT_URL            local MinIO endpoint      (from .env)
    AWS_ACCESS_KEY_ID           local MinIO access key    (from .env)
    AWS_SECRET_ACCESS_KEY       local MinIO secret key    (from .env)
    AWS_DEFAULT_REGION          local MinIO region        (from .env)
    CRAWL_BUCKET                local crawl bucket name   (from .env)

    PROD_DATABASE_URL           prod Postgres url
    PROD_CRAWL_BUCKET           prod crawl bucket name (e.g. carmodpicker-production-crawl-data)
    PROD_AWS_REGION             prod AWS region (e.g. us-west-2)

Optional — if omitted, boto3 uses the default credential chain (AWS CLI profile,
env vars, instance role, etc.):
    PROD_AWS_ACCESS_KEY_ID      prod AWS access key
    PROD_AWS_SECRET_ACCESS_KEY  prod AWS secret key

Flags:
    --dry-run         List what would be copied without writing anything
    --source ADAPTER  Only sync rows with source = ADAPTER (e.g. "a90shop")
    --limit N         Cap rows considered (0 = no cap)
    --batch-size N    DB insert batch size (default 500)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

_backend_dir = Path(__file__).resolve().parent.parent
_env_file = _backend_dir / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        os.environ.setdefault(_k.strip(), _v.strip())


import boto3  # noqa: E402 — after env load
from botocore.exceptions import ClientError  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

SELECT_LOCAL_SQL = text("""
    SELECT id, url, source, html_s3_key, html_sha256, crawled_at
    FROM crawled_pages
    WHERE html_s3_key IS NOT NULL
      AND (:source IS NULL OR source = :source)
    ORDER BY crawled_at
    """)

SELECT_PROD_URLS_SQL = text("SELECT url FROM crawled_pages")

INSERT_SQL = text("""
    INSERT INTO crawled_pages
        (id, url, source, html_s3_key, html_local_path, html_sha256,
         crawled_at, last_parsed_at, parse_status, part_id)
    VALUES
        (:id, :url, :source, :html_s3_key, NULL, :html_sha256,
         :crawled_at, NULL, 'pending', NULL)
    ON CONFLICT (url) DO NOTHING
    """)


def _make_s3_client(
    *,
    endpoint_url: str | None,
    access_key: str | None,
    secret_key: str | None,
    region: str | None,
    session_token: str | None = None,
) -> Any:
    kwargs: dict = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key
    if session_token:
        kwargs["aws_session_token"] = session_token
    if region:
        kwargs["region_name"] = region
    return boto3.client("s3", **kwargs)


def _make_engine(url: str, label: str) -> Engine:
    if not url:
        print(f"ERROR: missing DB url for {label}")
        sys.exit(1)
    try:
        return create_engine(url, future=True)
    except Exception as exc:
        print(f"ERROR: failed to create engine for {label}: {exc}")
        sys.exit(1)


def _object_exists(client: Any, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = (e.response.get("Error") or {}).get("Code")
        if code in ("404", "NoSuchKey"):
            return False
        raise


def _copy_object(src_client: Any, dest_client: Any, *, src_bucket: str, dest_bucket: str, key: str) -> None:
    obj = src_client.get_object(Bucket=src_bucket, Key=key)
    body: bytes = obj["Body"].read()
    content_type: str = obj.get("ContentType", "text/html; charset=utf-8")
    dest_client.put_object(Bucket=dest_bucket, Key=key, Body=body, ContentType=content_type)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="List transfers without writing")
    parser.add_argument("--source", default=None, help="Only sync rows with this source adapter")
    parser.add_argument("--limit", type=int, default=0, help="Cap rows considered (0 = no cap)")
    parser.add_argument("--batch-size", type=int, default=500, help="DB insert batch size")
    args = parser.parse_args()

    src_db_url = os.environ.get("DATABASE_URL", "")
    dest_db_url = os.environ.get("PROD_DATABASE_URL", "")

    src_endpoint = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT_URL") or ""
    src_s3_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    src_s3_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    src_s3_region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or ""
    src_bucket = os.environ.get("CRAWL_BUCKET", "")

    # boto3 silently honors AWS_ENDPOINT_URL from env. If .env points it at local
    # MinIO, the dest (real AWS) client would inherit it too and every call would
    # hit localhost:9000. Pop it now that we've captured it for the source client.
    os.environ.pop("AWS_ENDPOINT_URL", None)
    os.environ.pop("S3_ENDPOINT_URL", None)

    dest_s3_key = os.environ.get("PROD_AWS_ACCESS_KEY_ID", "")
    dest_s3_secret = os.environ.get("PROD_AWS_SECRET_ACCESS_KEY", "")
    dest_s3_token = os.environ.get("PROD_AWS_SESSION_TOKEN", "")
    dest_s3_region = os.environ.get("PROD_AWS_REGION", "")
    dest_bucket = os.environ.get("PROD_CRAWL_BUCKET", "")

    missing: list[str] = []
    if not src_db_url:
        missing.append("DATABASE_URL (source)")
    if not dest_db_url:
        missing.append("PROD_DATABASE_URL (destination)")
    if not src_bucket:
        missing.append("CRAWL_BUCKET (source)")
    if not dest_bucket:
        missing.append("PROD_CRAWL_BUCKET (destination)")
    # PROD_AWS_ACCESS_KEY_ID / SECRET are optional: if absent, boto3 uses the
    # default credential chain (AWS CLI profile, IMDS, etc.).
    if missing:
        print("ERROR: missing required env vars:")
        for m in missing:
            print(f"  {m}")
        sys.exit(1)

    if dest_db_url == src_db_url:
        print("ERROR: PROD_DATABASE_URL equals DATABASE_URL. Refusing to run.")
        sys.exit(1)

    print(f"Source DB  : {src_db_url.split('@', 1)[-1]}")
    print(f"Dest DB    : {dest_db_url.split('@', 1)[-1]}")
    print(f"Source S3  : {src_endpoint or 'AWS S3'} / {src_bucket}")
    print(f"Dest S3    : AWS S3 ({dest_s3_region or 'default region'}) / {dest_bucket}")
    if args.source:
        print(f"Filter     : source = {args.source!r}")
    print("Mode       : " + ("DRY RUN — no writes" if args.dry_run else "LIVE"))
    print()

    src_db = _make_engine(src_db_url, "source (DATABASE_URL)")
    dest_db = _make_engine(dest_db_url, "destination (PROD_DATABASE_URL)")
    src_s3 = _make_s3_client(
        endpoint_url=src_endpoint, access_key=src_s3_key, secret_key=src_s3_secret, region=src_s3_region
    )
    dest_s3 = _make_s3_client(
        endpoint_url=None,
        access_key=dest_s3_key or None,
        secret_key=dest_s3_secret or None,
        session_token=dest_s3_token or None,
        region=dest_s3_region or None,
    )

    with dest_db.connect() as conn:
        has_table = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'crawled_pages'"
            )
        ).scalar()
        if not has_table:
            print("ERROR: prod DB has no 'crawled_pages' table. Run migrations on prod first.")
            sys.exit(1)

    with src_db.connect() as conn:
        local_rows = conn.execute(SELECT_LOCAL_SQL, {"source": args.source}).mappings().all()
    print(f"Local rows with html_s3_key set: {len(local_rows)}")

    with dest_db.connect() as conn:
        existing_urls = {row[0] for row in conn.execute(SELECT_PROD_URLS_SQL).all()}
    print(f"Rows already present in prod DB: {len(existing_urls)}")

    todo = [r for r in local_rows if r["url"] not in existing_urls]
    if args.limit:
        todo = todo[: args.limit]
    print(f"Rows to bootstrap into prod    : {len(todo)}\n")

    if not todo:
        print("Nothing to do.")
        return

    copied_obj = skipped_obj = obj_errors = 0
    pending_rows: list[dict] = []

    for i, r in enumerate(todo, 1):
        key = r["html_s3_key"]
        url = r["url"]
        if args.dry_run:
            print(f"  [{i}/{len(todo)}] WOULD COPY  {key}  <-  {url}")
            pending_rows.append(dict(r))
            continue

        try:
            if _object_exists(dest_s3, dest_bucket, key):
                skipped_obj += 1
                print(f"  [{i}/{len(todo)}] skip S3 (exists)  {key}")
            else:
                _copy_object(src_s3, dest_s3, src_bucket=src_bucket, dest_bucket=dest_bucket, key=key)
                copied_obj += 1
                print(f"  [{i}/{len(todo)}] copied S3         {key}")
            pending_rows.append(dict(r))
        except Exception as exc:
            obj_errors += 1
            print(f"  [{i}/{len(todo)}] S3 ERROR          {key}: {exc}")

    if args.dry_run:
        print(
            f"\nDry run complete. Would copy {len(pending_rows)} object(s) and insert "
            f"{len(pending_rows)} row(s) into prod."
        )
        return

    inserted_rows = 0
    insert_errors = 0
    print(f"\nInserting {len(pending_rows)} row(s) into prod crawled_pages ...")
    with dest_db.begin() as conn:
        for start in range(0, len(pending_rows), args.batch_size):
            chunk = pending_rows[start : start + args.batch_size]
            try:
                result = conn.execute(INSERT_SQL, chunk)
                rc = result.rowcount if result.rowcount is not None else 0
                inserted_rows += max(rc, 0)
                print(f"  batch {start // args.batch_size + 1}: submitted={len(chunk)} inserted={rc}")
            except Exception as exc:
                insert_errors += len(chunk)
                print(f"  batch {start // args.batch_size + 1} ERROR: {exc}")

    print(
        f"\nDone.  s3_copied={copied_obj}  s3_skipped_existing={skipped_obj}  "
        f"s3_errors={obj_errors}  rows_inserted={inserted_rows}  row_errors={insert_errors}"
    )
    if obj_errors or insert_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
