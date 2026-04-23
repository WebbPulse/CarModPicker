"""
Image upload endpoint for S3.
Handles secure image uploads with validation and authentication.
Supports source URL tracking for deduplication (avoid re-downloading same images).
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
)
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.user import User as DBUser
from app.api.services.storage_service import storage_service
from app.api.utils.bucket_orphan_utils import get_all_referenced_file_keys
from app.api.utils.image_url_utils import get_canonical_image_url
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/by-source-url")
async def get_image_by_source_url(
    source_url: str = Query(..., description="Original URL the image was downloaded from"),
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Check if we've already stored an image from this source URL (deduplication).
    Returns the existing file_key if found, so clients can skip re-uploading.
    """
    canonical = get_canonical_image_url(source_url)
    mapping = db.scalars(select(DBImageSourceMapping).where(DBImageSourceMapping.source_url == canonical)).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cached image for this source URL")
    return {"file_key": mapping.file_key}


@router.post("/upload")
async def upload_image(
    entity_type: str,
    entity_id: Optional[UUID] = None,
    source_url: Optional[str] = Form(
        None, description="Original URL (for deduplication; skips upload if already stored)"
    ),
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Upload an image file to S3 bucket.

    The file is validated for security (type, size, content) and stored
    in S3 bucket. Returns the file key which should be stored
    in your database. Use the /presigned-url endpoint to get a URL for displaying.

    Args:
        entity_type: Type of entity (e.g., 'build_list', 'part', 'user', 'car')
        entity_id: Optional ID of the entity (for updates)
        file: Image file to upload
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        dict: Contains 'file_key' (store this in your database) and 'presigned_url' (for immediate use)

    Raises:
        HTTPException: If upload fails, validation fails, or user is not authenticated
    """
    # Validate entity_type
    allowed_entity_types = ["build_list", "part", "user", "car_generation", "build_log_post"]
    if entity_type not in allowed_entity_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type. Allowed types: {', '.join(allowed_entity_types)}",
        )

    # If entity_id is provided, verify the user owns the entity
    if entity_id:
        from app.api.models.build_list import BuildList as DBBuildList
        from app.api.models.part import Part as DBPart

        entity_owned = False
        if entity_type == "build_list":
            entity = db.scalars(select(DBBuildList).where(DBBuildList.id == entity_id)).first()
            if entity and entity.user_id == current_user.id:
                entity_owned = True
        elif entity_type == "part":
            entity = db.scalars(select(DBPart).where(DBPart.id == entity_id)).first()
            if entity and entity.user_id == current_user.id:
                entity_owned = True
        elif entity_type == "user":
            # Users can only upload images for themselves
            if entity_id == current_user.id:
                entity_owned = True
        elif entity_type == "car_generation":
            # Cars are centrally managed - only admins can upload images
            if not current_user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can upload images for cars",
                )
            entity_owned = True
        elif entity_type == "build_log_post":
            # For build log posts, verify the user has access to the build list
            # If entity_id is provided, it should be the build_list_id
            if entity_id:
                from app.api.models.build_list import BuildList as DBBuildList

                build_list = db.scalars(select(DBBuildList).where(DBBuildList.id == entity_id)).first()
                if build_list:
                    # Any authenticated user can upload images for build log posts
                    # (build logs are public-readable, so images should be too)
                    entity_owned = True
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Build list not found",
                    )
            else:
                # If no entity_id provided, allow upload (for new posts)
                entity_owned = True

        if not entity_owned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized to upload images for this {entity_type}",
            )

        # For part: reject upload if part already has max images (avoid expensive bucket uploads)
        if entity_type == "part":
            from app.api.schemas.part import MAX_IMAGES_PER_PART

            part = db.scalars(select(DBPart).where(DBPart.id == entity_id)).first()
            if part:
                current_count = len(part.image_urls or [])
                if current_count >= MAX_IMAGES_PER_PART:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Part already has the maximum number of images ({MAX_IMAGES_PER_PART}).",
                    )

    try:
        # Deduplication: if source_url provided and we already have it, return existing file_key
        if source_url and source_url.strip():
            canonical = get_canonical_image_url(source_url)
            existing = db.scalars(select(DBImageSourceMapping).where(DBImageSourceMapping.source_url == canonical)).first()
            if existing:
                presigned_url = storage_service.get_presigned_url(existing.file_key)
                logger.info(f"User {current_user.id} reused cached image for source URL (file_key={existing.file_key})")
                return {
                    "file_key": existing.file_key,
                    "presigned_url": presigned_url,
                    "message": "Image already cached; reused existing",
                }

        # Upload image to S3 bucket
        # Force square aspect ratio for user profile pictures
        force_square = entity_type == "user"
        file_key = storage_service.upload_image(
            file=file,
            entity_type=entity_type,
            user_id=current_user.id,
            entity_id=entity_id,
            force_square=force_square,
        )

        # Generate presigned URL for immediate use
        presigned_url = storage_service.get_presigned_url(file_key)

        logger.info(f"User {current_user.id} uploaded image: {file_key}")

        # Store source_url mapping for future deduplication (part only for now)
        if source_url and source_url.strip() and entity_type == "part":
            try:
                canonical = get_canonical_image_url(source_url)
                mapping = DBImageSourceMapping(
                    source_url=canonical,
                    file_key=file_key,
                )
                db.add(mapping)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Failed to store image source mapping: {e}")

        return {
            "file_key": file_key,
            "presigned_url": presigned_url,
            "message": "Image uploaded successfully",
        }

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during image upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during image upload",
        )


@router.get("/presigned-url")
async def get_presigned_url(
    file_key: str,
    expiration: Optional[int] = None,
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Generate a presigned URL for accessing an image in S3 bucket.

    The S3 bucket is private; presigned URLs are required to access images.
    These URLs are temporary and expire after the specified time (default: 24 hours).

    For security, if a user is authenticated, we verify they own the image.
    Public access is allowed for images that may be shared (e.g., public build lists).

    Args:
        file_key: The file key stored in your database (from upload endpoint)
        expiration: Optional expiration time in seconds (default: 24 hours, max: 90 days)
        current_user: Optional authenticated user (for private images)
        db: Database session

    Returns:
        dict: Contains 'presigned_url' for accessing the image

    Raises:
        HTTPException: If URL generation fails or user doesn't own the image
    """
    # Validate file key format and security
    storage_service.validate_file_key(file_key)

    # If user is authenticated, verify ownership
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
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Delete an image from S3 bucket.

    Only the owner of the image can delete it. Ownership is verified by checking
    the user_hash embedded in the file_key.

    Args:
        file_key: The file key to delete
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If deletion fails, user is not authenticated, or user doesn't own the image
    """
    # Validate file key format and security
    storage_service.validate_file_key(file_key)

    # Verify ownership before allowing deletion
    if not storage_service.verify_file_key_ownership(file_key, current_user.id):
        logger.warning(f"User {current_user.id} attempted to delete file_key they don't own: {file_key}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this image",
        )

    try:
        success = storage_service.delete_image(file_key)

        if success:
            logger.info(f"User {current_user.id} deleted image: {file_key}")
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
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """
    Get the total count of objects in the S3 bucket (admin only).

    Args:
        current_user: Authenticated admin user (from JWT token)
        db: Database session

    Returns:
        dict: Contains 'count' with the total number of bucket objects

    Raises:
        HTTPException: If counting fails or user is not an admin
    """
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
    db: Session = Depends(get_db),
) -> dict[str, int | list[str]]:
    """
    List bucket object keys that are not referenced by any entity (dry run).
    Admin only. Use this to preview what would be deleted by purge-orphaned.
    No objects are deleted.
    """
    try:
        referenced = get_all_referenced_file_keys(db)
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
    db: Session = Depends(get_db),
) -> dict[str, int | list[str]]:
    """
    Delete bucket objects that are not referenced by any entity (orphans).
    Admin only. Non-destructive: only objects with no DB reference are removed.
    Referenced keys come from: part (image_urls), user (image_urls),
    car (image_urls), build_list (image_urls), image_source_mapping (file_key).
    """
    try:
        referenced = get_all_referenced_file_keys(db)
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
