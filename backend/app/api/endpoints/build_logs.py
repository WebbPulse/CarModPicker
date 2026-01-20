"""
Build logs endpoint for forum-style build log threads.
Each build list automatically gets a build log thread.
"""

from typing import Optional

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_log import BuildLog as DBBuildLog, BuildLogPost as DBBuildLogPost
from app.api.models.user import User as DBUser
from app.api.schemas.build_log import (
    BuildLogPostCreate,
    BuildLogPostRead,
    BuildLogPostUpdate,
    BuildLogRead,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import crud_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger

# Create router
router = APIRouter()


@router.get(
    "/build-list/{build_list_id}",
    response_model=BuildLogRead,
    responses=crud_responses("build log", "read", allow_public_read=True),
)
async def get_build_log_by_build_list(
    build_list_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> BuildLogRead:
    """
    Get the build log thread for a specific build list.
    Public read access - anyone can view build logs.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify the build list exists
    build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Get or create the build log for this build list
    build_log = db.query(DBBuildLog).filter(DBBuildLog.build_list_id == build_list_id).first()

    if not build_log:
        # Auto-create if it doesn't exist (for backward compatibility with existing build lists)
        build_log = DBBuildLog(
            build_list_id=build_list_id,
            title=f"Build Log: {build_list.name}",
        )
        db.add(build_log)
        db.commit()
        db.refresh(build_log)
        logger.info(f"Auto-created build log thread {build_log.id} for build list {build_list_id}")

    # Load posts with author information
    posts = (
        db.query(DBBuildLogPost)
        .filter(DBBuildLogPost.build_log_id == build_log.id)
        .order_by(DBBuildLogPost.created_at)
        .all()
    )

    # Create response with author usernames
    posts_with_authors = []
    for post in posts:
        author = db.query(DBUser).filter(DBUser.id == post.user_id).first()
        post_data = BuildLogPostRead.model_validate(post)
        post_data.author_username = author.username if author else None
        posts_with_authors.append(post_data)

    build_log_data = BuildLogRead.model_validate(build_log)
    build_log_data.posts = posts_with_authors

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved build log {build_log.id} for build list {build_list_id}")

    return build_log_data


@router.post(
    "/build-list/{build_list_id}/posts",
    response_model=BuildLogPostRead,
    responses=crud_responses("build log post", "create"),
    status_code=status.HTTP_201_CREATED,
)
async def create_build_log_post(
    build_list_id: int,
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

    # Verify the build list exists
    build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Get or create the build log for this build list
    build_log = db.query(DBBuildLog).filter(DBBuildLog.build_list_id == build_list_id).first()

    if not build_log:
        # Auto-create if it doesn't exist
        build_log = DBBuildLog(
            build_list_id=build_list_id,
            title=f"Build Log: {build_list.name}",
        )
        db.add(build_log)
        db.flush()

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
    author = db.query(DBUser).filter(DBUser.id == post.user_id).first()
    post_response = BuildLogPostRead.model_validate(post)
    post_response.author_username = author.username if author else None

    logger.info(f"User {current_user.id} created post {post.id} in build log {build_log.id}")

    return post_response


@router.put(
    "/posts/{post_id}",
    response_model=BuildLogPostRead,
    responses=crud_responses("build log post", "update"),
)
async def update_build_log_post(
    post_id: int,
    post_data: BuildLogPostUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildLogPostRead:
    """
    Update a build log post.
    Users can only update their own posts, or admins can update any post.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Get the post
    post = get_entity_or_404(db, DBBuildLogPost, post_id, "build log post")

    # Check authorization - users can only update their own posts, or admins can update any
    verify_user_access_or_admin(current_user, post.user_id, "update this build log post", logger)

    # Update the post
    if post_data.content is not None:
        post.content = post_data.content

    db.commit()
    db.refresh(post)

    # Load author information
    author = db.query(DBUser).filter(DBUser.id == post.user_id).first()
    post_response = BuildLogPostRead.model_validate(post)
    post_response.author_username = author.username if author else None

    logger.info(f"User {current_user.id} updated post {post.id}")

    return post_response


@router.delete(
    "/posts/{post_id}",
    responses=crud_responses("build log post", "delete"),
)
async def delete_build_log_post(
    post_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> dict:
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
    build_log = db.query(DBBuildLog).filter(DBBuildLog.id == post.build_log_id).first()
    if not build_log:
        ResponsePatterns.raise_not_found("build log", post.build_log_id)

    build_list = db.query(DBBuildList).filter(DBBuildList.id == build_log.build_list_id).first()
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
