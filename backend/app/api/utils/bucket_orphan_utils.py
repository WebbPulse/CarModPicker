"""
Utilities for admin bucket orphan cleanup.
Collects all file keys referenced by entities so we can safely delete only unreferenced objects.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car_generation import CarGeneration as DBCar
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
    for image_urls in db.scalars(select(DBPart.image_urls)).all():
        _collect_image_urls(image_urls)

    # Users: image_urls
    for image_urls in db.scalars(
        select(DBUser.image_urls).where(DBUser.image_urls.isnot(None))
    ).all():
        _collect_image_urls(image_urls)

    # Cars: image_urls
    for image_urls in db.scalars(
        select(DBCar.image_urls).where(DBCar.image_urls.isnot(None))
    ).all():
        _collect_image_urls(image_urls)

    # Build lists: image_urls
    for image_urls in db.scalars(
        select(DBBuildList.image_urls).where(DBBuildList.image_urls.isnot(None))
    ).all():
        _collect_image_urls(image_urls)

    # Image source mappings (dedup cache)
    for file_key in db.scalars(select(DBImageSourceMapping.file_key)).all():
        if file_key and is_file_key(file_key):
            referenced.add(file_key)

    return referenced
