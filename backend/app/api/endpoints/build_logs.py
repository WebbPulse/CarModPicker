"""
Build logs endpoint for forum-style build log threads.
Each build list automatically gets a build log thread.
"""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.build_log import BuildLogPost as DBBuildLogPost
from app.api.models.user import User as DBUser
from app.api.schemas.build_log import (
    BuildLogPostCreate,
    BuildLogPostRead,
    BuildLogPostUpdate,
    BuildLogRead,
    BuildLogReadPaginated,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    create_paginated_response,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import crud_responses
from app.api.utils.image_utils import get_presigned_url_from_file_key
from app.api.utils.response_patterns import ResponsePatterns

# Create router
router = APIRouter()


@router.get(
    "/posts/count",
    response_model=Dict[str, int],
    responses={
        200: {"description": "Count of build log posts"},
    },
)
async def count_build_log_posts(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """
    Get total count of build log posts.
    Public access - anyone can view the count.
    """
    db = deps["db"]
    logger = deps["logger"]

    try:
        count = db.scalar(select(func.count()).select_from(DBBuildLogPost)) or 0
        logger.info(f"Retrieved build log posts count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting build log posts: {str(e)}")
        raise


@router.get(
    "/build-list/{build_list_id}",
    response_model=BuildLogReadPaginated,
    responses=crud_responses("build log", "read", allow_public_read=True),
)
async def get_build_log_by_build_list(
    build_list_id: UUID,
    skip: int = Query(0, ge=0, description="Number of posts to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of posts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> BuildLogReadPaginated:
    """
    Get the build log thread for a specific build list.
    Public read access - anyone can view build logs.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify the build list exists (raises 404 if not; post-DATA-08 we no longer
    # reference the returned entity — the eager-create path owns build_log.title).
    get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Get the build log for this build list.
    build_log = db.scalars(select(DBBuildLog).where(DBBuildLog.build_list_id == build_list_id)).first()
    if not build_log:
        # Post-DATA-08 backfill invariant: every build_list has a build_log row.
        # If this branch fires, something broke the invariant — do not silently
        # auto-create (the old fallback hid data-integrity issues).
        logger.error(
            "Orphan build_list %s has no build_log row; DATA-08 invariant violated", build_list_id
        )
        ResponsePatterns.raise_not_found("build log", build_list_id)

    # Validate pagination parameters
    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # Get total count of posts (modern select() form per DATA-06 sweep; Pitfall 5:
    # select(func.count()).select_from(X) preserves COUNT(*) semantics).
    # `db.scalar` returns Optional[int]; COUNT(*) is never NULL in practice (returns 0
    # when no rows match), so coerce to int to satisfy create_paginated_response's
    # non-optional `total` param.
    total_posts = db.scalar(
        select(func.count())
        .select_from(DBBuildLogPost)
        .where(DBBuildLogPost.build_log_id == build_log.id)
    ) or 0

    # DATA-01: Load paginated posts + eager-load authors via selectinload.
    # selectinload emits exactly 1 additional IN-clause SELECT for authors
    # regardless of post count — fixes the old 1+N query pattern.
    posts = db.scalars(
        select(DBBuildLogPost)
        .where(DBBuildLogPost.build_log_id == build_log.id)
        .order_by(DBBuildLogPost.created_at)
        .options(selectinload(DBBuildLogPost.author))
        .offset(skip)
        .limit(limit)
    ).all()

    # Create response with author usernames and profile pictures
    posts_with_authors: List[BuildLogPostRead] = []
    for post in posts:
        author = post.author  # eager-loaded via selectinload; zero additional queries
        post_data = BuildLogPostRead.model_validate(post)
        post_data.author_username = author.username if author else None
        # Convert file key to presigned URL for profile picture
        post_data.author_image_url = (
            get_presigned_url_from_file_key((author.image_urls or [None])[0]) if author and author.image_urls else None
        )
        posts_with_authors.append(post_data)

    # Create paginated response
    paginated_response = create_paginated_response(
        data=posts_with_authors,
        total=total_posts,
        skip=skip,
        limit=limit,
        message="Build log retrieved successfully",
    )

    build_log_data = BuildLogRead.model_validate(build_log)

    # Map pagination response to match frontend expectations
    pagination_data = paginated_response["pagination"]
    pagination_mapped = {
        "current_page": pagination_data["current_page"],
        "total_pages": pagination_data["total_pages"],
        "total_items": pagination_data["total"],  # Map 'total' to 'total_items'
        "items_per_page": pagination_data["limit"],  # Map 'limit' to 'items_per_page'
        "has_next": pagination_data["has_next"],
        "has_previous": pagination_data["has_previous"],
    }

    # Create paginated build log response
    build_log_paginated = BuildLogReadPaginated(
        id=build_log_data.id,
        build_list_id=build_log_data.build_list_id,
        title=build_log_data.title,
        created_at=build_log_data.created_at,
        updated_at=build_log_data.updated_at,
        posts=paginated_response["data"],
        pagination=pagination_mapped,
    )

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(
        f"{user_info}: Retrieved build log {build_log.id} for build list {build_list_id} (skip: {skip}, limit: {limit})"
    )

    return build_log_paginated


@router.post(
    "/build-list/{build_list_id}/posts",
    response_model=BuildLogPostRead,
    responses=crud_responses("build log post", "create"),
    status_code=status.HTTP_201_CREATED,
)
async def create_build_log_post(
    build_list_id: UUID,
    post_data: BuildLogPostCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildLogPostRead:
    """
    Create a new post in a build log thread.
    Requires authentication.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify the build list exists (raises 404 if not; post-DATA-08 we no longer
    # reference the returned entity — the eager-create path owns build_log.title).
    get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Get the build log for this build list.
    build_log = db.scalars(select(DBBuildLog).where(DBBuildLog.build_list_id == build_list_id)).first()
    if not build_log:
        # Post-DATA-08 backfill invariant: every build_list has a build_log row.
        # If this branch fires, something broke the invariant — do not silently
        # auto-create (the old fallback hid data-integrity issues).
        logger.error(
            "Orphan build_list %s has no build_log row; DATA-08 invariant violated", build_list_id
        )
        ResponsePatterns.raise_not_found("build log", build_list_id)

    # Create the post
    post = DBBuildLogPost(
        build_log_id=build_log.id,
        user_id=current_user.id,
        content=post_data.content,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Load author information
    author = db.scalars(select(DBUser).where(DBUser.id == post.user_id)).first()
    post_response = BuildLogPostRead.model_validate(post)
    post_response.author_username = author.username if author else None
    # Convert file key to presigned URL for profile picture
    post_response.author_image_url = (
        get_presigned_url_from_file_key((author.image_urls or [None])[0]) if author and author.image_urls else None
    )

    logger.info(f"User {current_user.id} created post {post.id} in build log {build_log.id}")

    return post_response


@router.put(
    "/posts/{post_id}",
    response_model=BuildLogPostRead,
    responses=crud_responses("build log post", "update"),
)
async def update_build_log_post(
    post_id: UUID,
    post_data: BuildLogPostUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildLogPostRead:
    """
    Update a build log post.
    Users can update their own posts, build list owners can update any post in their build log,
    or admins can update any post.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Get the post
    post = get_entity_or_404(db, DBBuildLogPost, post_id, "build log post")

    # Get the build log and build list to check ownership
    build_log = db.scalars(select(DBBuildLog).where(DBBuildLog.id == post.build_log_id)).first()
    if not build_log:
        ResponsePatterns.raise_not_found("build log", post.build_log_id)

    build_list = db.scalars(select(DBBuildList).where(DBBuildList.id == build_log.build_list_id)).first()
    if not build_list:
        ResponsePatterns.raise_not_found("build list", build_log.build_list_id)

    # Check authorization:
    # 1. User owns the post
    # 2. User owns the build list
    # 3. User is admin/superuser
    can_update = (
        post.user_id == current_user.id
        or build_list.user_id == current_user.id
        or current_user.is_admin
        or current_user.is_superuser
    )

    if not can_update:
        if logger:
            logger.warning(f"Access denied: User {current_user.id} attempted to update build log post {post_id}")
        ResponsePatterns.raise_forbidden("Not authorized to update this build log post")

    # Update the post
    if post_data.content is not None:
        post.content = post_data.content

    db.commit()
    db.refresh(post)

    # Load author information
    author = db.scalars(select(DBUser).where(DBUser.id == post.user_id)).first()
    post_response = BuildLogPostRead.model_validate(post)
    post_response.author_username = author.username if author else None
    # Convert file key to presigned URL for profile picture
    post_response.author_image_url = (
        get_presigned_url_from_file_key((author.image_urls or [None])[0]) if author and author.image_urls else None
    )

    logger.info(f"User {current_user.id} updated post {post.id}")

    return post_response


@router.delete(
    "/posts/{post_id}",
    responses=crud_responses("build log post", "delete"),
)
async def delete_build_log_post(
    post_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Delete a build log post.
    Users can delete their own posts, build list owners can delete any post in their build log,
    or admins can delete any post.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Get the post
    post = get_entity_or_404(db, DBBuildLogPost, post_id, "build log post")

    # Get the build log and build list to check ownership
    build_log = db.scalars(select(DBBuildLog).where(DBBuildLog.id == post.build_log_id)).first()
    if not build_log:
        ResponsePatterns.raise_not_found("build log", post.build_log_id)

    build_list = db.scalars(select(DBBuildList).where(DBBuildList.id == build_log.build_list_id)).first()
    if not build_list:
        ResponsePatterns.raise_not_found("build list", build_log.build_list_id)

    # Check authorization:
    # 1. User owns the post
    # 2. User owns the build list
    # 3. User is admin/superuser
    can_delete = (
        post.user_id == current_user.id
        or build_list.user_id == current_user.id
        or current_user.is_admin
        or current_user.is_superuser
    )

    if not can_delete:
        if logger:
            logger.warning(f"Access denied: User {current_user.id} attempted to delete build log post {post_id}")
        ResponsePatterns.raise_forbidden("Not authorized to delete this build log post")

    # Delete the post
    db.delete(post)
    db.commit()

    logger.info(f"User {current_user.id} deleted post {post_id}")

    return {"message": "Build log post deleted successfully"}
