"""
Sync static UI assets from a local directory to the storage bucket.
Runs on startup: for each expected asset, if it is not already in the bucket,
upload from the local static_assets dir (if the file exists).
"""

import logging
import os

from app.core.asset_keys import (
    ASSET_EXTENSIONS,
    CONTENT_TYPES,
    category_name_to_slug,
    get_category_asset_key,
    get_manufacturer_asset_key,
    manufacturer_name_to_slug,
)
from app.core.config import settings
from app.core.part_categories_data import get_all_part_categories

logger = logging.getLogger(__name__)


def _get_static_assets_dir() -> str:
    """Return the path to the static_assets directory."""
    if settings.STATIC_ASSETS_DIR and os.path.isdir(settings.STATIC_ASSETS_DIR):
        return settings.STATIC_ASSETS_DIR
    # Default: backend/static_assets (app lives in backend/app)
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(backend_root, "static_assets")


def _read_local_file(path: str) -> bytes | None:
    """Read file bytes if it exists."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        logger.warning(f"Could not read {path}: {e}")
        return None


def sync_static_assets_to_bucket() -> None:
    """
    For each expected manufacturer and part category asset, if the object is not
    in the bucket, upload it from the local static_assets dir (if the file exists).
    Skips if bucket is not configured or in test environment.
    """
    from app.api.services.storage_service import storage_service
    from app.core.car_generations_data import CAR_GENERATIONS

    if not storage_service.s3_client or not storage_service.bucket_name:
        logger.info("Storage bucket not configured; skipping static assets sync.")
        return

    static_dir = _get_static_assets_dir()
    if not os.path.isdir(static_dir):
        logger.info("Static assets dir not found (%s); skipping sync.", static_dir)
        return

    uploaded = 0

    # Manufacturers: keys from CAR_GENERATIONS
    manufacturers_dir = os.path.join(static_dir, "manufacturers")
    if os.path.isdir(manufacturers_dir):
        for make in CAR_GENERATIONS.keys():
            slug = manufacturer_name_to_slug(make)
            synced = False
            for ext in ASSET_EXTENSIONS:
                key = get_manufacturer_asset_key(slug, ext)
                if storage_service.object_exists(key):
                    synced = True
                    break
                local_path = os.path.join(manufacturers_dir, f"{slug}{ext}")
                body = _read_local_file(local_path)
                if body:
                    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
                    storage_service.validate_asset_key(key)
                    storage_service.upload_bytes(key, body, content_type)
                    uploaded += 1
                    logger.info("Uploaded manufacturer asset: %s", key)
                    synced = True
                    break
            if not synced:
                logger.debug("No local file for manufacturer %s (tried %s)", make, ASSET_EXTENSIONS)

    # Part categories: from part_categories_data
    categories_dir = os.path.join(static_dir, "categories")
    if os.path.isdir(categories_dir):
        for cat in get_all_part_categories():
            name = cat.get("name")
            if not name or not isinstance(name, str):
                continue
            slug = category_name_to_slug(name)
            synced = False
            for ext in ASSET_EXTENSIONS:
                key = get_category_asset_key(slug, ext)
                if storage_service.object_exists(key):
                    synced = True
                    break
                local_path = os.path.join(categories_dir, f"{slug}{ext}")
                body = _read_local_file(local_path)
                if body:
                    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
                    storage_service.validate_asset_key(key)
                    storage_service.upload_bytes(key, body, content_type)
                    uploaded += 1
                    logger.info("Uploaded category asset: %s", key)
                    synced = True
                    break
            if not synced:
                logger.debug("No local file for category %s (tried %s)", name, ASSET_EXTENSIONS)

    if uploaded > 0:
        logger.info("Static assets sync: uploaded %s file(s) to bucket.", uploaded)
    else:
        logger.debug("Static assets sync: nothing to upload (all already in bucket or missing locally).")
