#!/usr/bin/env python3
"""
Transfer crawl HTML archive from local MinIO to production S3.

Usage:
    python scripts/transfer_crawl_archive.py [--dry-run] [--skip-existing] [--prefix crawl_html/]

Source:  local MinIO (reads from .env or env vars)
Dest:    production S3 (reads from separate env vars below, or CLI flags)

Required env vars for destination (prod):
    PROD_AWS_ACCESS_KEY_ID       AWS access key for prod
    PROD_AWS_SECRET_ACCESS_KEY   AWS secret key for prod
    PROD_AWS_REGION              e.g. us-west-2
    PROD_CRAWL_BUCKET            prod crawl bucket name (e.g. carmodpicker-prod-crawl)

Source is read from the standard .env vars (AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID, etc.)
and CRAWL_BUCKET.  Run from the backend/ directory or set cwd explicitly.

Flags:
    --dry-run        List what would be transferred without writing anything
    --skip-existing  Skip objects that already exist in dest (default: True)
    --no-skip        Overwrite existing objects in dest
    --prefix TEXT    Only transfer keys with this prefix (default: transfer everything)
    --batch-size N   Max objects to transfer in one run (default: unlimited)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env from backend/ so local dev vars are available when running directly
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(
    *,
    endpoint_url: str | None,
    access_key: str | None,
    secret_key: str | None,
    region: str | None,
) -> "boto3.client":
    kwargs: dict = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key
    if region:
        kwargs["region_name"] = region
    return boto3.client("s3", **kwargs)


def _list_all_objects(client, bucket: str, prefix: str = "") -> list[dict]:
    """Return all objects (with Key, Size, ETag) in bucket, optionally filtered by prefix."""
    objects: list[dict] = []
    kwargs: dict = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix
    while True:
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents") or []:
            objects.append(
                {
                    "Key": obj["Key"],
                    "Size": obj.get("Size", 0),
                    "ETag": obj.get("ETag", "").strip('"'),
                }
            )
        if resp.get("IsTruncated"):
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]
        else:
            break
    return objects


def _dest_etag(client, bucket: str, key: str) -> str | None:
    """Return ETag of an existing object in dest, or None if absent."""
    try:
        head = client.head_object(Bucket=bucket, Key=key)
        return head.get("ETag", "").strip('"')
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise


def _transfer_object(
    src_client,
    dest_client,
    *,
    src_bucket: str,
    dest_bucket: str,
    key: str,
) -> None:
    """Download from src and upload to dest (streaming via Body bytes)."""
    obj = src_client.get_object(Bucket=src_bucket, Key=key)
    body: bytes = obj["Body"].read()
    content_type: str = obj.get("ContentType", "text/html; charset=utf-8")
    dest_client.put_object(
        Bucket=dest_bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="List transfers without writing")
    parser.add_argument(
        "--skip-existing", action="store_true", default=True, help="Skip objects already in dest (default: True)"
    )
    parser.add_argument(
        "--no-skip", dest="skip_existing", action="store_false", help="Overwrite objects that already exist in dest"
    )
    parser.add_argument("--prefix", default="", metavar="PREFIX", help="Only transfer keys with this prefix")
    parser.add_argument(
        "--batch-size", type=int, default=0, metavar="N", help="Stop after transferring N objects (0 = unlimited)"
    )
    args = parser.parse_args()

    # ---- source (MinIO / local dev) ----------------------------------------
    src_endpoint = os.environ.get("AWS_ENDPOINT_URL") or os.environ.get("S3_ENDPOINT_URL") or ""
    src_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    src_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    src_region = os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or ""
    src_bucket = os.environ.get("CRAWL_BUCKET", "")

    # ---- destination (prod AWS S3) -----------------------------------------
    dest_key = os.environ.get("PROD_AWS_ACCESS_KEY_ID", "")
    dest_secret = os.environ.get("PROD_AWS_SECRET_ACCESS_KEY", "")
    dest_region = os.environ.get("PROD_AWS_REGION", "")
    dest_bucket = os.environ.get("PROD_CRAWL_BUCKET", "")

    # Validate
    missing: list[str] = []
    if not src_bucket:
        missing.append("CRAWL_BUCKET (source)")
    if not dest_bucket:
        missing.append("PROD_CRAWL_BUCKET (destination)")
    if not dest_key:
        missing.append("PROD_AWS_ACCESS_KEY_ID")
    if not dest_secret:
        missing.append("PROD_AWS_SECRET_ACCESS_KEY")
    if missing:
        print("ERROR: missing required env vars:")
        for m in missing:
            print(f"  {m}")
        sys.exit(1)

    print(f"Source      : {src_endpoint or 'AWS S3'} / {src_bucket}")
    print(f"Destination : AWS S3 ({dest_region or 'default region'}) / {dest_bucket}")
    if args.prefix:
        print(f"Prefix      : {args.prefix!r}")
    if args.dry_run:
        print("Mode        : DRY RUN — no writes\n")
    else:
        skip_label = "skip existing" if args.skip_existing else "overwrite existing"
        print(f"Mode        : LIVE ({skip_label})\n")

    src_client = _make_client(endpoint_url=src_endpoint, access_key=src_key, secret_key=src_secret, region=src_region)
    dest_client = _make_client(endpoint_url=None, access_key=dest_key, secret_key=dest_secret, region=dest_region)

    print(f"Listing source objects in s3://{src_bucket}/{args.prefix} ...")
    src_objects = _list_all_objects(src_client, src_bucket, prefix=args.prefix)
    print(f"Found {len(src_objects)} object(s) in source.\n")

    if not src_objects:
        print("Nothing to transfer.")
        return

    transferred = skipped = errors = 0

    for i, obj in enumerate(src_objects, 1):
        key = obj["Key"]
        size = obj["Size"]
        src_etag = obj["ETag"]

        if args.batch_size and transferred >= args.batch_size:
            print(f"\nBatch size limit ({args.batch_size}) reached — stopping early.")
            break

        # Check dest
        if args.skip_existing and not args.dry_run:
            dest_etag = _dest_etag(dest_client, dest_bucket, key)
            if dest_etag is not None:
                # MinIO ETags for small objects match md5; for large ones they differ.
                # We treat any existing object as "already there" and skip unless --no-skip.
                print(f"  [{i}/{len(src_objects)}] SKIP  {key} ({size:,} B) — already in dest")
                skipped += 1
                continue

        size_kb = size / 1024
        if args.dry_run:
            print(f"  [{i}/{len(src_objects)}] WOULD COPY  {key}  ({size_kb:.1f} KB)")
            transferred += 1
            continue

        try:
            _transfer_object(src_client, dest_client, src_bucket=src_bucket, dest_bucket=dest_bucket, key=key)
            print(f"  [{i}/{len(src_objects)}] OK     {key}  ({size_kb:.1f} KB)")
            transferred += 1
        except Exception as exc:
            print(f"  [{i}/{len(src_objects)}] ERROR  {key}: {exc}")
            errors += 1

    print(f"\nDone.  transferred={transferred}  skipped={skipped}  errors={errors}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
