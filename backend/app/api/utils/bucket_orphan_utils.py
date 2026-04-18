"""
Utilities for admin bucket orphan cleanup.
Collects all file keys referenced by entities so we can safely delete only unreferenced objects.
"""

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.api.utils.image_utils import is_file_key


def get_all_referenced_file_keys(db: Session) -> set[str]:
    """
    Collect all file keys that are referenced by any entity in the database.
    Used to identify bucket objects that are safe to delete (orphans).

    Includes: part (image_urls), user (image_urls), car (image_urls),
    build_list (image_urls), image_source_mapping (file_key).
    """
    referenced: set[str] = set()

    def _collect_image_urls(image_urls: list[str] | None) -> None:
        if image_urls:
            for k in image_urls:
                if k and is_file_key(k):
                    referenced.add(k)

    # Parts: image_urls gallery
    for row in db.query(DBPart.image_urls).all():
        _collect_image_urls(row.image_urls)

    # Users: image_urls
    for row in db.query(DBUser.image_urls).filter(DBUser.image_urls.isnot(None)).all():
        _collect_image_urls(row.image_urls)

    # Cars: image_urls
    for row in db.query(DBCar.image_urls).filter(DBCar.image_urls.isnot(None)).all():
        _collect_image_urls(row.image_urls)

    # Build lists: image_urls
    for row in db.query(DBBuildList.image_urls).filter(DBBuildList.image_urls.isnot(None)).all():
        _collect_image_urls(row.image_urls)

    # Image source mappings (dedup cache)
    for row in db.query(DBImageSourceMapping.file_key).all():
        if row.file_key and is_file_key(row.file_key):
            referenced.add(row.file_key)

    return referenced
