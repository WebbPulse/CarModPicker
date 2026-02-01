"""
Static UI asset URLs (manufacturer logos, part category icons).
Assets are stored in the storage bucket; presigned URLs are returned for display.
"""

from fastapi import APIRouter, Query

from app.api.services.storage_service import storage_service
from app.core.asset_keys import (
    ASSET_EXTENSIONS,
    category_name_to_slug,
    get_category_asset_key,
    get_manufacturer_asset_key,
    manufacturer_name_to_slug,
)

router = APIRouter()

# Use long expiration for static assets (7 days) so frontend can cache
ASSET_PRESIGNED_EXPIRATION = 7 * 24 * 3600


def _first_existing_key(keys: list[str]) -> str | None:
    """Return the first key that exists in the bucket."""
    for key in keys:
        if storage_service.object_exists(key):
            return key
    return None


@router.get("/urls")
async def get_asset_urls(
    manufacturers: str | None = Query(
        None,
        description="Comma-separated manufacturer names (e.g. Honda,BMW,Audi)",
    ),
    categories: str | None = Query(
        None,
        description="Comma-separated category names (e.g. exhaust,suspension)",
    ),
) -> dict[str, dict[str, str]]:
    """
    Return presigned URLs for static assets (manufacturer logos, category icons).
    Only includes assets that exist in the bucket. No auth required (public read).
    """
    result: dict[str, dict[str, str]] = {"manufacturers": {}, "categories": {}}

    if not storage_service.s3_client or not storage_service.bucket_name:
        return result

    if manufacturers:
        for make in (m.strip() for m in manufacturers.split(",") if m.strip()):
            slug = manufacturer_name_to_slug(make)
            keys = [get_manufacturer_asset_key(slug, ext) for ext in ASSET_EXTENSIONS]
            key = _first_existing_key(keys)
            if key:
                try:
                    storage_service.validate_asset_key(key)
                    url = storage_service.get_presigned_url(key, expiration=ASSET_PRESIGNED_EXPIRATION)
                    result["manufacturers"][make] = url
                except Exception:
                    pass

    if categories:
        for name in (c.strip() for c in categories.split(",") if c.strip()):
            slug = category_name_to_slug(name)
            keys = [get_category_asset_key(slug, ext) for ext in ASSET_EXTENSIONS]
            key = _first_existing_key(keys)
            if key:
                try:
                    storage_service.validate_asset_key(key)
                    url = storage_service.get_presigned_url(key, expiration=ASSET_PRESIGNED_EXPIRATION)
                    result["categories"][name] = url
                except Exception:
                    pass

    return result
