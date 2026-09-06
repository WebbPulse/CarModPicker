"""
Unified vote service for all entity types.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, List, Optional, Union
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Float, and_, case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.models.report import Report as DBReport
from app.api.models.vote import Vote as DBVote
from app.api.schemas.vote import (
    EntityType,
    FlaggedEntitySummary,
    VoteCreate,
    VoteSummary,
)
from app.db.dynamo.build_lists import BuildList as DBBuildList
from app.db.dynamo.catalog import CarGeneration, Part
from app.db.dynamo.repository import ItemNotFound

VotableEntity = Union[CarGeneration, DBBuildList, Part]


class VoteService:
    """
    Unified vote service for all entity types.

    This service handles voting operations for cars, build lists, and global parts
    using the unified Vote model.
    """

    def __init__(self, repos: Optional[Repositories] = None) -> None:
        """Initialize the unified vote service."""
        self.repos = repos or get_repositories()

    def vote_on_entity(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: UUID,
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
            HTTPException: If entity doesn't exist
        """
        self._get_entity_or_404(db, entity_type, entity_id)

        existing_vote = db.scalars(
            select(DBVote).where(
                DBVote.user_id == user_id,
                DBVote.entity_type == entity_type.value,
                DBVote.entity_id == entity_id,
            )
        ).first()

        if existing_vote:
            existing_vote.vote_type = vote_data.vote_type.value
            existing_vote.updated_at = datetime.now(UTC)
            db.commit()
            db.refresh(existing_vote)
            self._sync_part_net_votes(db, entity_type, entity_id)

            logger.info(f"Vote updated: {existing_vote.id} by user {user_id} on {entity_type.value} {entity_id}")
            return existing_vote

        db_vote = DBVote(
            user_id=user_id,
            entity_type=entity_type.value,
            entity_id=entity_id,
            vote_type=vote_data.vote_type.value,
        )
        db.add(db_vote)
        db.commit()
        db.refresh(db_vote)
        self._sync_part_net_votes(db, entity_type, entity_id)

        logger.info(f"Vote created: {db_vote.id} by user {user_id} on {entity_type.value} {entity_id}")
        return db_vote

    def remove_vote(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: UUID,
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
        vote = db.scalars(
            select(DBVote).where(
                DBVote.user_id == user_id,
                DBVote.entity_type == entity_type.value,
                DBVote.entity_id == entity_id,
            )
        ).first()

        if vote:
            db.delete(vote)
            db.commit()
            self._sync_part_net_votes(db, entity_type, entity_id)
            logger.info(f"Vote removed: {vote.id} by user {user_id} on {entity_type.value} {entity_id}")
            return True

        return False

    def get_vote_summary(
        self,
        db: Session,
        entity_type: EntityType,
        entity_id: UUID,
        user_id: Optional[UUID] = None,
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

        Raises:
            HTTPException: If entity not found
        """
        self._get_entity_or_404(db, entity_type, entity_id)

        upvotes, downvotes = self._vote_counts(db, entity_type, entity_id)
        total_votes = upvotes + downvotes
        vote_score = upvotes - downvotes

        user_vote = None
        if user_id:
            user_vote_obj = db.scalars(
                select(DBVote).where(
                    DBVote.user_id == user_id,
                    DBVote.entity_type == entity_type.value,
                    DBVote.entity_id == entity_id,
                )
            ).first()
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
        vote_stats = (
            select(
                DBVote.entity_id,
                func.sum(case((DBVote.vote_type == "upvote", 1), else_=0)).label("upvotes"),
                func.sum(case((DBVote.vote_type == "downvote", 1), else_=0)).label("downvotes"),
                func.count(DBVote.id).label("total_votes"),
                func.sum(
                    case(
                        (
                            and_(
                                DBVote.vote_type == "downvote",
                                DBVote.created_at >= datetime.now(UTC) - timedelta(days=7),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("recent_downvotes"),
            )
            .where(DBVote.entity_type == entity_type.value)
            .group_by(DBVote.entity_id)
            .having(func.count(DBVote.id) >= 5)
            .subquery()
        )
        downvote_ratio = case(
            (
                vote_stats.c.total_votes > 0,
                vote_stats.c.downvotes.cast(Float) / vote_stats.c.total_votes,
            ),
            else_=0.0,
        )

        rows = db.execute(
            select(
                vote_stats.c.entity_id,
                vote_stats.c.upvotes,
                vote_stats.c.downvotes,
                vote_stats.c.total_votes,
                vote_stats.c.recent_downvotes,
                downvote_ratio.label("downvote_ratio"),
                exists(
                    select(1)
                    .select_from(DBReport)
                    .where(
                        and_(
                            DBReport.entity_type == entity_type.value,
                            DBReport.entity_id == vote_stats.c.entity_id,
                        )
                    )
                ).label("has_reports"),
            )
            .where(or_(downvote_ratio >= 0.3, vote_stats.c.recent_downvotes >= 3))
            .order_by(downvote_ratio.desc(), vote_stats.c.recent_downvotes.desc())
            .limit(limit)
        ).all()

        entities = self._get_entities(db, entity_type, [row[0] for row in rows])
        flagged: List[FlaggedEntitySummary] = []
        for entity_id, upvotes, downvotes, total_votes, recent_downvotes, ratio, has_reports in rows:
            entity = entities.get(entity_id)
            if entity is None:
                continue
            flagged.append(
                FlaggedEntitySummary(
                    entity_id=entity.id,
                    entity_type=entity_type.value,
                    entity_name=self._get_entity_name(entity, entity_type),
                    entity_description=getattr(entity, "description", None),
                    upvotes=upvotes or 0,
                    downvotes=downvotes or 0,
                    total_votes=total_votes or 0,
                    vote_score=(upvotes or 0) - (downvotes or 0),
                    downvote_ratio=ratio or 0.0,
                    recent_downvotes=recent_downvotes or 0,
                    has_reports=bool(has_reports),
                    created_at=entity.created_at,
                    flagged_at=datetime.now(UTC),
                )
            )
        return flagged

    def _vote_counts(self, db: Session, entity_type: EntityType, entity_id: UUID) -> tuple[int, int]:
        vote_counts = db.execute(
            select(DBVote.vote_type, func.count(DBVote.id).label("count"))
            .where(
                DBVote.entity_type == entity_type.value,
                DBVote.entity_id == entity_id,
            )
            .group_by(DBVote.vote_type)
        ).all()
        upvotes = sum(int(count[1]) for count in vote_counts if count[0] == "upvote")
        downvotes = sum(int(count[1]) for count in vote_counts if count[0] == "downvote")
        return upvotes, downvotes

    def _sync_part_net_votes(self, db: Session, entity_type: EntityType, entity_id: UUID) -> None:
        if entity_type != EntityType.PART:
            return
        upvotes, downvotes = self._vote_counts(db, entity_type, entity_id)
        try:
            self.repos.parts.update(str(entity_id), net_votes=upvotes - downvotes)
        except ItemNotFound:
            return

    def _get_entities(self, db: Session, entity_type: EntityType, ids: List[Any]) -> dict[UUID, VotableEntity]:
        if not ids:
            return {}
        if entity_type == EntityType.BUILD_LIST:
            return dict(self.repos.build_lists.get_many(ids))
        if entity_type == EntityType.CAR_GENERATION:
            return dict(self.repos.car_generations.get_many(ids))
        if entity_type == EntityType.PART:
            return dict(self.repos.parts.get_many(ids))
        raise ValueError(f"Unknown entity type: {entity_type}")

    def _get_entity_or_404(self, db: Session, entity_type: EntityType, entity_id: UUID) -> VotableEntity:
        entity = self._get_entities(db, entity_type, [entity_id]).get(entity_id)
        if entity is None:
            raise HTTPException(status_code=404, detail=f"{entity_type.value.title()} not found")
        return entity

    def _get_entity_name(self, entity: VotableEntity, entity_type: EntityType) -> str:
        """Get the display name for an entity."""
        if isinstance(entity, CarGeneration):
            from app.api.services.car_generation_service import CarGenerationService

            read = CarGenerationService(self.repos).hydrate_one(entity)
            return (
                f"{read.car_make_name} {read.car_model_name} {read.generation_name} ({read.start_year}-{read.end_year})"
            )
        return str(entity.name)
