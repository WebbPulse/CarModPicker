"""
Unified vote service for all entity types.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, Float, exists, select
from datetime import datetime, UTC, timedelta

from app.api.models.vote import Vote as DBVote
from app.api.models.user import User as DBUser
from app.api.models.car import Car as DBCar
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.schemas.vote import (
    VoteCreate,
    VoteRead,
    VoteSummary,
    FlaggedEntitySummary,
    EntityType,
)
from app.api.utils.common_operations import verify_entity_exists
from fastapi import HTTPException


class VoteService:
    """
    Unified vote service for all entity types.

    This service handles voting operations for cars, build lists, and global parts
    using the unified Vote model.
    """

    def __init__(self):
        """Initialize the unified vote service."""
        pass

    def vote_on_entity(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: int,
        user_id: int,
        vote_data: VoteCreate,
        logger: logging.Logger,
    ) -> DBVote:
        """
        Vote on an entity (car, build list, or global part).

        Args:
            db: Database session
            entity_type: Type of entity being voted on
            entity_id: ID of the entity
            user_id: ID of the user voting
            vote_data: Vote data
            logger: Logger instance

        Returns:
            The created or updated vote

        Raises:
            HTTPException: If entity doesn't exist or user tries to vote on their own entity
        """
        # Verify entity exists
        entity_model = self._get_entity_model(entity_type)
        entity = verify_entity_exists(db, entity_model, entity_id, entity_type.value)

        # Check if user is trying to vote on their own entity
        if entity.user_id == user_id:
            raise HTTPException(
                status_code=400,
                detail=f"You cannot vote on your own {entity_type.value}",
            )

        # Check for existing vote
        existing_vote = (
            db.query(DBVote)
            .filter(
                DBVote.user_id == user_id,
                DBVote.entity_type == entity_type.value,
                DBVote.entity_id == entity_id,
            )
            .first()
        )

        if existing_vote:
            # Update existing vote
            existing_vote.vote_type = vote_data.vote_type.value
            existing_vote.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(existing_vote)

            logger.info(
                f"Vote updated: {existing_vote.id} by user {user_id} on {entity_type.value} {entity_id}"
            )
            return existing_vote
        else:
            # Create new vote
            db_vote = DBVote(
                user_id=user_id,
                entity_type=entity_type.value,
                entity_id=entity_id,
                vote_type=vote_data.vote_type.value,
            )
            db.add(db_vote)
            db.commit()
            db.refresh(db_vote)

            logger.info(
                f"Vote created: {db_vote.id} by user {user_id} on {entity_type.value} {entity_id}"
            )
            return db_vote

    def remove_vote(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: int,
        user_id: int,
        logger: logging.Logger,
    ) -> bool:
        """
        Remove a vote from an entity.

        Args:
            db: Database session
            entity_type: Type of entity
            entity_id: ID of the entity
            user_id: ID of the user
            logger: Logger instance

        Returns:
            True if vote was removed, False if no vote existed
        """
        vote = (
            db.query(DBVote)
            .filter(
                DBVote.user_id == user_id,
                DBVote.entity_type == entity_type.value,
                DBVote.entity_id == entity_id,
            )
            .first()
        )

        if vote:
            db.delete(vote)
            db.commit()
            logger.info(
                f"Vote removed: {vote.id} by user {user_id} on {entity_type.value} {entity_id}"
            )
            return True

        return False

    def get_vote_summary(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: int,
        user_id: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
    ) -> VoteSummary:
        """
        Get vote summary for an entity.

        Args:
            db: Database session
            entity_type: Type of entity
            entity_id: ID of the entity
            user_id: Optional user ID to get their vote
            logger: Optional logger instance

        Returns:
            Vote summary
        """
        # Get vote counts
        vote_counts = (
            db.query(DBVote.vote_type, func.count(DBVote.id).label("count"))
            .filter(
                DBVote.entity_type == entity_type.value,
                DBVote.entity_id == entity_id,
            )
            .group_by(DBVote.vote_type)
            .all()
        )

        upvotes = sum(
            count.count for count in vote_counts if count.vote_type == "upvote"
        )
        downvotes = sum(
            count.count for count in vote_counts if count.vote_type == "downvote"
        )
        total_votes = upvotes + downvotes
        vote_score = upvotes - downvotes

        # Get user's vote if user_id provided
        user_vote = None
        if user_id:
            user_vote_obj = (
                db.query(DBVote)
                .filter(
                    DBVote.user_id == user_id,
                    DBVote.entity_type == entity_type.value,
                    DBVote.entity_id == entity_id,
                )
                .first()
            )
            user_vote = user_vote_obj.vote_type if user_vote_obj else None

        return VoteSummary(
            entity_id=entity_id,
            entity_type=entity_type.value,
            upvotes=upvotes,
            downvotes=downvotes,
            total_votes=total_votes,
            vote_score=vote_score,
            user_vote=user_vote,
        )

    def get_flagged_entities(
        self,
        db: Session,
        entity_type: EntityType,
        limit: int = 50,
        logger: Optional[logging.Logger] = None,
    ) -> List[FlaggedEntitySummary]:
        """
        Get flagged entities (those with high downvote ratios or reports).

        Args:
            db: Database session
            entity_type: Type of entity to get flagged instances of
            limit: Maximum number of entities to return
            logger: Optional logger instance

        Returns:
            List of flagged entity summaries
        """
        entity_model = self._get_entity_model(entity_type)

        # Calculate vote statistics for each entity
        vote_stats = (
            db.query(
                DBVote.entity_id,
                func.sum(case((DBVote.vote_type == "upvote", 1), else_=0)).label(
                    "upvotes"
                ),
                func.sum(case((DBVote.vote_type == "downvote", 1), else_=0)).label(
                    "downvotes"
                ),
                func.count(DBVote.id).label("total_votes"),
                func.sum(
                    case(
                        (
                            and_(
                                DBVote.vote_type == "downvote",
                                DBVote.created_at
                                >= datetime.now(UTC) - timedelta(days=7),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("recent_downvotes"),
            )
            .filter(DBVote.entity_type == entity_type.value)
            .group_by(DBVote.entity_id)
            .having(func.count(DBVote.id) >= 5)  # Only entities with at least 5 votes
            .subquery()
        )

        # Get entities with their vote stats and check for reports
        flagged_entities = (
            db.query(
                entity_model,
                vote_stats.c.upvotes,
                vote_stats.c.downvotes,
                vote_stats.c.total_votes,
                vote_stats.c.recent_downvotes,
                func.coalesce(vote_stats.c.upvotes, 0)
                - func.coalesce(vote_stats.c.downvotes, 0).label("vote_score"),
                case(
                    (
                        vote_stats.c.total_votes > 0,
                        vote_stats.c.downvotes.cast(Float) / vote_stats.c.total_votes,
                    ),
                    else_=0.0,
                ).label("downvote_ratio"),
                exists(
                    select(1)
                    .select_from(DBVote)
                    .where(
                        and_(
                            DBVote.entity_type == entity_type.value,
                            DBVote.entity_id == entity_model.id,
                        )
                    )
                ).label("has_reports"),
            )
            .join(vote_stats, entity_model.id == vote_stats.c.entity_id)
            .filter(
                or_(
                    # High downvote ratio
                    case(
                        (
                            vote_stats.c.total_votes > 0,
                            vote_stats.c.downvotes.cast(Float)
                            / vote_stats.c.total_votes,
                        ),
                        else_=0.0,
                    )
                    >= 0.3,
                    # Many recent downvotes
                    vote_stats.c.recent_downvotes >= 3,
                )
            )
            .order_by(
                case(
                    (
                        vote_stats.c.total_votes > 0,
                        vote_stats.c.downvotes.cast(Float) / vote_stats.c.total_votes,
                    ),
                    else_=0.0,
                ).desc(),
                vote_stats.c.recent_downvotes.desc(),
            )
            .limit(limit)
            .all()
        )

        return [
            FlaggedEntitySummary(
                entity_id=entity.id,
                entity_type=entity_type.value,
                entity_name=self._get_entity_name(entity, entity_type),
                entity_description=getattr(entity, "description", None),
                upvotes=upvotes or 0,
                downvotes=downvotes or 0,
                total_votes=total_votes or 0,
                vote_score=vote_score or 0,
                downvote_ratio=downvote_ratio or 0.0,
                recent_downvotes=recent_downvotes or 0,
                has_reports=has_reports,
                created_at=entity.created_at,
                flagged_at=datetime.now(UTC),
            )
            for entity, upvotes, downvotes, total_votes, recent_downvotes, vote_score, downvote_ratio, has_reports in flagged_entities
        ]

    def _get_entity_model(self, entity_type: EntityType):
        """Get the SQLAlchemy model for the entity type."""
        if entity_type == EntityType.CAR:
            return DBCar
        elif entity_type == EntityType.BUILD_LIST:
            return DBBuildList
        elif entity_type == EntityType.GLOBAL_PART:
            return DBGlobalPart
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def _get_entity_name(self, entity, entity_type: EntityType) -> str:
        """Get the display name for an entity."""
        if entity_type == EntityType.CAR:
            return f"{entity.make} {entity.model} {entity.year}"
        elif entity_type == EntityType.BUILD_LIST:
            return entity.name
        elif entity_type == EntityType.GLOBAL_PART:
            return entity.name
        else:
            return str(entity.id)
