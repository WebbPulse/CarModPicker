"""
Base service class for voting operations to eliminate code duplication.
"""

import logging
from typing import Any, Dict, Generic, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.protocols import BaseModel, HasModelDump, VoteModel
from app.api.utils.common_operations import verify_entity_exists

# Generic types for different vote models and schemas
# VoteModelType must have vote_type, user_id, and id attributes
VoteModelType = TypeVar("VoteModelType", bound=VoteModel)
VoteCreateSchema = TypeVar("VoteCreateSchema", bound=HasModelDump)
VoteReadSchema = TypeVar("VoteReadSchema")
EntityModelType = TypeVar("EntityModelType", bound=BaseModel)


class BaseVoteService(Generic[VoteModelType, VoteCreateSchema, VoteReadSchema, EntityModelType]):
    """
    Base service class for voting operations.

    This class provides common voting functionality for all entity types
    to eliminate code duplication across different vote endpoints.
    """

    def __init__(
        self,
        vote_model: Type[VoteModelType],
        entity_model: Type[EntityModelType],
        entity_name: str = "entity",
        vote_entity_id_field: str = "entity_id",
    ):
        """
        Initialize the base vote service.

        Args:
            vote_model: The SQLAlchemy vote model class
            entity_model: The SQLAlchemy entity model class being voted on
            entity_name: Human-readable name of the entity type
            vote_entity_id_field: Field name in vote model that references the entity
        """
        self.vote_model = vote_model
        self.entity_model = entity_model
        self.entity_name = entity_name
        self.vote_entity_id_field = vote_entity_id_field

    def vote_on_entity(
        self,
        db: Session,
        entity_id: UUID,
        user_id: UUID,
        vote_data: VoteCreateSchema,
        logger: logging.Logger,
    ) -> VoteModelType:
        """
        Vote on an entity (upvote or downvote).

        Args:
            db: Database session
            entity_id: ID of the entity being voted on
            user_id: ID of the user voting
            vote_data: Vote data (typically contains vote_type)
            logger: Logger instance

        Returns:
            The created or updated vote

        Raises:
            HTTPException: If entity not found or voting fails
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
        )

        # Check if user has already voted on this entity
        existing_vote = db.scalars(
            select(self.vote_model).where(
                and_(
                    getattr(self.vote_model, "user_id") == user_id,
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                )
            )
        ).first()

        if existing_vote:
            # Update existing vote - Protocol ensures vote_type attribute exists
            # Extract vote_type from vote_data using getattr for type safety
            vote_type_value = getattr(vote_data, "vote_type", None)
            if vote_type_value is not None:
                existing_vote.vote_type = getattr(vote_type_value, "value", vote_type_value)
            db.commit()
            db.refresh(existing_vote)
            logger.info(f"Vote updated: {existing_vote.id} by user {user_id} " f"on {self.entity_name} {entity_id}")
            return existing_vote
        else:
            # Create new vote
            vote_data_dict = vote_data.model_dump()
            vote_data_dict["user_id"] = user_id
            vote_data_dict[self.vote_entity_id_field] = entity_id

            db_vote = self.vote_model(**vote_data_dict)
            db.add(db_vote)
            db.commit()
            db.refresh(db_vote)
            logger.info(f"Vote created: {db_vote.id} by user {user_id} " f"on {self.entity_name} {entity_id}")
            return db_vote

    def remove_vote(
        self,
        db: Session,
        entity_id: UUID,
        user_id: UUID,
        logger: logging.Logger,
    ) -> bool:
        """
        Remove user's vote on an entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            user_id: ID of the user
            logger: Logger instance

        Returns:
            True if vote was removed, False if no vote existed

        Raises:
            HTTPException: If entity not found
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
        )

        # Find and delete the vote
        existing_vote = db.scalars(
            select(self.vote_model).where(
                and_(
                    getattr(self.vote_model, "user_id") == user_id,
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                )
            )
        ).first()

        if existing_vote:
            db.delete(existing_vote)
            db.commit()
            logger.info(f"Vote removed: {existing_vote.id} by user {user_id} " f"on {self.entity_name} {entity_id}")
            return True
        else:
            logger.info(f"No vote found for user {user_id} on {self.entity_name} {entity_id}")
            return False

    def get_vote_summary(
        self,
        db: Session,
        entity_id: UUID,
        logger: logging.Logger,
    ) -> Dict[str, Any]:
        """
        Get vote summary for an entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            logger: Logger instance

        Returns:
            Dictionary with vote counts and summary

        Raises:
            HTTPException: If entity not found
        """
        # Verify entity exists
        verify_entity_exists(
            db=db,
            model=self.entity_model,
            entity_id=entity_id,
            entity_name=self.entity_name,
        )

        # Get vote counts - Protocol ensures id and vote_type attributes exist
        upvotes = db.scalar(
            select(func.count())
            .select_from(self.vote_model)
            .where(
                and_(
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                    self.vote_model.vote_type == "upvote",  # type: ignore[arg-type]
                )
            )
        ) or 0

        downvotes = db.scalar(
            select(func.count())
            .select_from(self.vote_model)
            .where(
                and_(
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                    self.vote_model.vote_type == "downvote",  # type: ignore[arg-type]
                )
            )
        ) or 0

        total_votes = upvotes + downvotes
        score = upvotes - downvotes

        logger.info(
            f"Vote summary for {self.entity_name} {entity_id}: "
            f"upvotes={upvotes}, downvotes={downvotes}, score={score}"
        )

        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "total_votes": total_votes,
            "score": score,
        }

    def get_user_vote(
        self,
        db: Session,
        entity_id: UUID,
        user_id: UUID,
        logger: logging.Logger,
    ) -> Optional[VoteModelType]:
        """
        Get a user's vote on a specific entity.

        Args:
            db: Database session
            entity_id: ID of the entity
            user_id: ID of the user
            logger: Logger instance

        Returns:
            The user's vote or None if no vote exists
        """
        vote = db.scalars(
            select(self.vote_model).where(
                and_(
                    getattr(self.vote_model, "user_id") == user_id,
                    getattr(self.vote_model, self.vote_entity_id_field) == entity_id,
                )
            )
        ).first()

        if vote:
            # VoteModelType is bound to HasVoteType which has vote_type attribute
            logger.debug(f"User {user_id} vote on {self.entity_name} {entity_id}: " f"{vote.vote_type}")
        else:
            logger.debug(f"No vote found for user {user_id} on {self.entity_name} {entity_id}")

        return vote
