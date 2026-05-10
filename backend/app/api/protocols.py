"""
Protocol definitions for type checking generic services.

These protocols define the expected interfaces for models used in generic services,
allowing proper type checking without circular dependencies.
"""

from typing import Any, Dict, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class HasId(Protocol):
    """Protocol for models with an id attribute."""

    id: UUID


@runtime_checkable
class HasUserId(Protocol):
    """Protocol for models with a user_id attribute."""

    user_id: UUID


@runtime_checkable
class HasVoteType(Protocol):
    """Protocol for vote models with a vote_type attribute."""

    vote_type: str


@runtime_checkable
class HasStatus(Protocol):
    """Protocol for models with a status attribute."""

    status: str


@runtime_checkable
class HasResolutionNotes(Protocol):
    """Protocol for models with resolution_notes attribute."""

    resolution_notes: str | None


@runtime_checkable
class BaseModel(HasId, Protocol):
    """Protocol for base SQLAlchemy models with id."""

    pass


@runtime_checkable
class UserOwnedModel(HasId, HasUserId, Protocol):
    """Protocol for models that are owned by a user."""

    pass


@runtime_checkable
class VoteModel(HasId, HasUserId, HasVoteType, Protocol):
    """Protocol for vote models."""

    pass


@runtime_checkable
class ReportModel(HasId, HasUserId, HasStatus, HasResolutionNotes, Protocol):
    """Protocol for report models."""

    pass


@runtime_checkable
class HasModelDump(Protocol):
    """Protocol for Pydantic models that have a model_dump method."""

    def model_dump(
        self,
        *,
        mode: str = "python",
        include: Any = None,
        exclude: Any = None,
        context: Any = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> Dict[str, Any]:
        """Dump model to dictionary."""
        ...
