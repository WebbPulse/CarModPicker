"""
Canonical asset key generation for static UI assets (manufacturers, categories).
Keys are deterministic so we can check bucket and sync from local dir.
"""

# Extensions to try when resolving an asset (check bucket or local file)
ASSET_EXTENSIONS = (".svg", ".png", ".webp")

# MIME types for upload
CONTENT_TYPES = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".webp": "image/webp",
}


def manufacturer_name_to_slug(make: str) -> str:
    """Convert make to slug, e.g. 'Aston Martin' -> 'aston-martin'."""
    return make.strip().lower().replace(" ", "-").replace("_", "-")


def category_name_to_slug(name: str) -> str:
    """Convert category name to slug (already lowercase in backend)."""
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def get_manufacturer_asset_key(slug: str, ext: str) -> str:
    """Return bucket key for a manufacturer logo, e.g. assets/manufacturers/honda.svg."""
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"assets/manufacturers/{slug}{ext}"


def get_category_asset_key(slug: str, ext: str) -> str:
    """Return bucket key for a category icon, e.g. assets/categories/exhaust.svg."""
    if not ext.startswith("."):
        ext = f".{ext}"
    return f"assets/categories/{slug}{ext}"
