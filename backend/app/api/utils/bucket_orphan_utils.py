"""
Utilities for admin bucket orphan cleanup.
Collects all file keys referenced by entities so we can safely delete only unreferenced objects.
"""

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.user import User as DBUser
from app.api.utils.image_utils import is_file_key


def get_all_referenced_file_keys(db: Session) -> set[str]:
    """
    Collect all file keys that are referenced by any entity in the database.
    Used to identify bucket objects that are safe to delete (orphans).

    Includes: global_part (image_url, image_urls), user (image_url), car (image_url),
    build_list (image_url), image_source_mapping (file_key).
    """
    referenced: set[str] = set()

    # Global parts: image_url + image_urls (gallery)
    for row in db.query(DBGlobalPart.image_url, DBGlobalPart.image_urls).all():
        if row.image_url and is_file_key(row.image_url):
            referenced.add(row.image_url)
        if row.image_urls:
            for k in row.image_urls:
                if k and is_file_key(k):
                    referenced.add(k)

    # Users: image_url
    for row in db.query(DBUser.image_url).filter(DBUser.image_url.isnot(None)).all():
        if row.image_url and is_file_key(row.image_url):
            referenced.add(row.image_url)

    # Cars: image_url
    for row in db.query(DBCar.image_url).filter(DBCar.image_url.isnot(None)).all():
        if row.image_url and is_file_key(row.image_url):
            referenced.add(row.image_url)

    # Build lists: image_url
    for row in db.query(DBBuildList.image_url).filter(DBBuildList.image_url.isnot(None)).all():
        if row.image_url and is_file_key(row.image_url):
            referenced.add(row.image_url)

    # Image source mappings (dedup cache)
    for row in db.query(DBImageSourceMapping.file_key).all():
        if row.file_key and is_file_key(row.file_key):
            referenced.add(row.file_key)

    return referenced
