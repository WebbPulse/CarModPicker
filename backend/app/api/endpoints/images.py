"""
Image upload endpoint for S3.
Handles secure image uploads with validation and authentication.
Supports source URL tracking for deduplication (avoid re-downloading same images).
"""

import logging
from io import BytesIO
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.api.dependencies.auth import (
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
)
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.services.storage_service import storage_service
from app.api.utils.bucket_orphan_utils import get_all_referenced_file_keys
from app.api.utils.image_url_utils import get_canonical_image_url, get_high_res_image_url
from app.api.utils.remote_image_fetch import assert_url_is_fetchable, fetch_remote_image
from app.db.dynamo.users import User as DBUser

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/by-source-url")
async def get_image_by_source_url(
    source_url: str = Query(..., description="Original URL the image was downloaded from"),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """
    Check if we've already stored an image from this source URL (deduplication).
    Returns the existing file_key if found, so clients can skip re-uploading.
    """
    canonical = get_canonical_image_url(source_url)
    mapping = repos.image_source_mappings.get_by_source_url(canonical)
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cached image for this source URL")
    return {"file_key": mapping.file_key}


ALLOWED_ENTITY_TYPES = ["build_list", "part", "user", "car_generation", "build_log_post"]


def _authorize_image_target(
    entity_type: str,
    entity_id: Optional[UUID],
    current_user: DBUser,
    repos: Repositories,
) -> None:
    """Validate the entity type and the caller's right to attach an image to it.

    Shared by the byte upload and the server side fetch so the two routes cannot
    drift apart on who may write an image where.
    """
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type. Allowed types: {', '.join(ALLOWED_ENTITY_TYPES)}",
        )

    if not entity_id:
        return

    entity_owned = False
    if entity_type == "build_list":
        entity = repos.build_lists.get(entity_id)
        if entity and entity.user_id == current_user.id:
            entity_owned = True
    elif entity_type == "part":
        part = repos.parts.get(str(entity_id))
        if part and part.user_id == current_user.id:
            entity_owned = True
    elif entity_type == "user":
        if entity_id == current_user.id:
            entity_owned = True
    elif entity_type == "car_generation":
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can upload images for cars",
            )
        entity_owned = True
    elif entity_type == "build_log_post":
        build_list = repos.build_lists.get(entity_id)
        if build_list:
            entity_owned = True
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Build list not found",
            )

    if not entity_owned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Not authorized to upload images for this {entity_type}",
        )

    if entity_type == "part":
        from app.api.schemas.part import MAX_IMAGES_PER_PART

        part = repos.parts.get(str(entity_id))
        if part and len(part.image_urls or []) >= MAX_IMAGES_PER_PART:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Part already has the maximum number of images ({MAX_IMAGES_PER_PART}).",
            )


@router.post("/upload")
async def upload_image(
    entity_type: str,
    entity_id: Optional[UUID] = None,
    source_url: Optional[str] = Form(
        None, description="Original URL (for deduplication; skips upload if already stored)"
    ),
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """Upload an image file to S3 bucket.

    The file is validated for security (type, size, content) and stored
    in S3 bucket. Returns the file key which should be stored
    """
    _authorize_image_target(entity_type, entity_id, current_user, repos)

    try:
        if source_url and source_url.strip():
            canonical = get_canonical_image_url(source_url)
            existing = repos.image_source_mappings.get_by_source_url(canonical)
            if existing:
                presigned_url = storage_service.get_presigned_url(existing.file_key)
                logger.info(f"User {current_user.id} reused cached image for source URL (file_key={existing.file_key})")
                return {
                    "file_key": existing.file_key,
                    "presigned_url": presigned_url,
                    "message": "Image already cached; reused existing",
                }

        force_square = entity_type == "user"
        file_key = storage_service.upload_image(
            file=file,
            entity_type=entity_type,
            user_id=current_user.id,
            entity_id=entity_id,
            force_square=force_square,
        )

        presigned_url = storage_service.get_presigned_url(file_key)

        logger.info(f"User {current_user.id} uploaded image: {file_key}")

        if source_url and source_url.strip() and entity_type == "part":
            try:
                canonical = get_canonical_image_url(source_url)
                repos.image_source_mappings.record(canonical, file_key)
            except Exception as e:
                logger.warning(f"Failed to store image source mapping: {e}")

        return {
            "file_key": file_key,
            "presigned_url": presigned_url,
            "message": "Image uploaded successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during image upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during image upload",
        )


class FetchFromUrlRequest(BaseModel):
    """The source image URL the server should fetch, and what it is attached to."""

    source_url: str = Field(..., description="https URL of the image to fetch and store")
    entity_type: str = Field(..., description="Type of entity the image belongs to")
    entity_id: Optional[UUID] = Field(None, description="Optional id of the entity being updated")


@router.post("/fetch-from-url")
async def fetch_image_from_url(
    body: FetchFromUrlRequest,
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> dict[str, str]:
    """Fetch an image from a public https URL server side and store it.

    The extension cannot read these bytes itself, so the server fetches them
    behind the same auth, authorization and validation as `/upload`.
    """
    _authorize_image_target(body.entity_type, body.entity_id, current_user, repos)

    source_url = body.source_url.strip()
    if not source_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_url is required")

    canonical = get_canonical_image_url(source_url)
    existing = repos.image_source_mappings.get_by_source_url(canonical)
    if existing:
        presigned_url = storage_service.get_presigned_url(existing.file_key)
        logger.info(f"User {current_user.id} reused cached image for source URL (file_key={existing.file_key})")
        return {
            "file_key": existing.file_key,
            "presigned_url": presigned_url,
            "message": "Image already cached; reused existing",
        }

    assert_url_is_fetchable(source_url)
    content, extension = fetch_remote_image(get_high_res_image_url(source_url))

    upload = UploadFile(filename=f"image.{extension}", file=BytesIO(content))

    try:
        file_key = storage_service.upload_image(
            file=upload,
            entity_type=body.entity_type,
            user_id=current_user.id,
            entity_id=body.entity_id,
            force_square=body.entity_type == "user",
        )
        presigned_url = storage_service.get_presigned_url(file_key)
        logger.info(f"User {current_user.id} stored image fetched from source URL: {file_key}")

        if body.entity_type == "part":
            try:
                repos.image_source_mappings.record(canonical, file_key)
            except Exception as e:
                logger.warning(f"Failed to store image source mapping: {e}")

        return {
            "file_key": file_key,
            "presigned_url": presigned_url,
            "message": "Image fetched and stored successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error storing fetched image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while storing the image",
        )


@router.get("/presigned-url")
async def get_presigned_url(
    file_key: str,
    expiration: Optional[int] = None,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> dict[str, str]:
    """Generate a presigned URL for accessing an image in S3 bucket.

    The S3 bucket is private; presigned URLs are required to access images.
    These URLs are temporary and expire after the specified time (default: 24 hours).
    """
    storage_service.validate_file_key(file_key)

    if current_user:
        if not storage_service.verify_file_key_ownership(file_key, current_user.id):
            logger.warning(f"User {current_user.id} attempted to access file_key they don't own: {file_key}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this image",
            )

    try:
        presigned_url = storage_service.get_presigned_url(file_key, expiration=expiration)

        return {
            "presigned_url": presigned_url,
            "file_key": file_key,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate image URL",
        )


@router.delete("/delete")
async def delete_image(
    file_key: str,
    current_user: DBUser = Depends(get_current_user),
) -> dict[str, str]:
    """Delete an image from S3 bucket.

    Only the owner of the image can delete it. Ownership is verified by checking
    the user_hash embedded in the file_key.
    """
    storage_service.validate_file_key(file_key)

    is_owner = storage_service.verify_file_key_ownership(file_key, current_user.id)
    if not is_owner and not current_user.is_admin:
        logger.warning(f"User {current_user.id} attempted to delete file_key they don't own: {file_key}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this image",
        )

    try:
        success = storage_service.delete_image(file_key)

        if success:
            actor = "Admin" if current_user.is_admin and not is_owner else "User"
            logger.info(f"{actor} {current_user.id} deleted image: {file_key}")
            return {"message": "Image deleted successfully", "file_key": file_key}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete image",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during image deletion",
        )


@router.get("/admin/count")
async def get_bucket_object_count(
    current_user: DBUser = Depends(get_current_admin_user),
) -> dict[str, int]:
    """Get the total count of objects in the S3 bucket (admin only)."""
    try:
        count = storage_service.count_bucket_objects()
        logger.info(f"Admin {current_user.id} retrieved bucket object count: {count}")
        return {"count": count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bucket object count: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while counting bucket objects",
        )


@router.get("/admin/count-by-entity-type")
async def get_bucket_object_count_by_entity_type(
    current_user: DBUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """
    Admin-only: one S3 list pass returning total keys, counts by standard upload prefix
    (entity_type segment), and keys that do not match the expected layout under ``other``.
    """
    try:
        summary = storage_service.count_bucket_objects_by_entity_prefix()
        logger.info(f"Admin {current_user.id} retrieved bucket object counts by entity prefix")
        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get bucket object counts by entity type: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while summarizing bucket objects",
        )


@router.get("/admin/orphaned")
async def list_orphaned_bucket_objects(
    current_user: DBUser = Depends(get_current_admin_user),
) -> dict[str, int | list[str]]:
    """
    List bucket object keys that are not referenced by any entity (dry run).
    Admin only. Use this to preview what would be deleted by purge-orphaned.
    No objects are deleted.
    """
    try:
        referenced = get_all_referenced_file_keys()
        bucket_keys = storage_service.list_bucket_object_keys()
        orphaned = [k for k in bucket_keys if k not in referenced]
        logger.info(
            f"Admin {current_user.id} orphan dry run: {len(orphaned)} orphaned of {len(bucket_keys)} total "
            f"({len(referenced)} referenced)"
        )
        return {
            "orphaned_keys": orphaned,
            "count": len(orphaned),
            "total_bucket": len(bucket_keys),
            "total_referenced": len(referenced),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list orphaned bucket objects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while listing orphaned objects",
        )


@router.post("/admin/purge-orphaned")
async def purge_orphaned_bucket_objects(
    current_user: DBUser = Depends(get_current_admin_user),
) -> dict[str, int | list[str]]:
    """Delete bucket objects that are not referenced by any entity (orphans).

    Admin only. Non-destructive: only objects with no DB reference are removed.
    Referenced keys come from: part (image_urls), user (image_urls),
    """
    try:
        referenced = get_all_referenced_file_keys()
        bucket_keys = storage_service.list_bucket_object_keys()
        orphaned = [k for k in bucket_keys if k not in referenced]

        deleted_keys: list[str] = []
        for key in orphaned:
            if storage_service.delete_image(key):
                deleted_keys.append(key)

        logger.info(f"Admin {current_user.id} purged {len(deleted_keys)} orphaned bucket objects")
        return {
            "deleted": len(deleted_keys),
            "deleted_keys": deleted_keys,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to purge orphaned bucket objects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while purging orphaned objects",
        )
