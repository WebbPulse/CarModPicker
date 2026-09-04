"""
Utilities for admin bucket orphan cleanup.
Collects all file keys referenced by entities so we can safely delete only unreferenced objects.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.repositories import get_repositories
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.utils.image_utils import is_file_key


def get_all_referenced_file_keys(db: Session) -> set[str]:
    """
    Collect all file keys that are referenced by any entity in the database.
    Used to identify bucket objects that are safe to delete (orphans).

    Includes: part (image_urls), user (image_urls), car (image_urls),
    build_list (image_urls), image_source_mapping (file_key).
    """
    referenced: set[str] = set()
    repos = get_repositories()

    def _collect_image_urls(image_urls: list[str] | None) -> None:
        if image_urls:
            for k in image_urls:
                if k and is_file_key(k):
                    referenced.add(k)

    for part in repos.parts.list_all():
        _collect_image_urls(part.image_urls)

    for user in repos.users.list_all():
        _collect_image_urls(user.image_urls)

    for car in repos.car_generations.list_all():
        _collect_image_urls(car.image_urls)

    # Build lists: image_urls
    for image_urls in db.scalars(select(DBBuildList.image_urls).where(DBBuildList.image_urls.isnot(None))).all():
        _collect_image_urls(image_urls)

    # Image source mappings (dedup cache)
    for file_key in db.scalars(select(DBImageSourceMapping.file_key)).all():
        if file_key and is_file_key(file_key):
            referenced.add(file_key)

    return referenced
