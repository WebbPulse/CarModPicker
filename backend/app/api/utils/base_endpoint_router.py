"""
Base endpoint router with common patterns to reduce redundancy.
"""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, cast

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.user import User as DBUser
from app.api.protocols import BaseModel, HasModelDump
from app.api.services.base_crud_service import BaseCRUDService
from app.core.logging import get_logger
from app.db.session import get_db

# Generic types - ModelType must have an 'id' attribute at minimum
ModelType = TypeVar("ModelType", bound=BaseModel)
CreateSchema = TypeVar("CreateSchema", bound=HasModelDump)
ReadSchema = TypeVar("ReadSchema")
UpdateSchema = TypeVar("UpdateSchema", bound=HasModelDump)


class BaseEndpointRouter(Generic[ModelType, CreateSchema, ReadSchema, UpdateSchema]):
    """
    Base endpoint router that provides common CRUD endpoint patterns.

    This class eliminates redundancy by providing standardized implementations
    for common operations like create, read, update, delete, and list.
    """

    def __init__(
        self,
        service: BaseCRUDService[ModelType, CreateSchema, ReadSchema, UpdateSchema],
        router: APIRouter,
        entity_name: str = "entity",
        allow_public_read: bool = False,
        additional_create_data: Optional[Dict[str, Any]] = None,
        disable_endpoints: Optional[List[str]] = None,
        create_schema: Optional[Type[CreateSchema]] = None,
        read_schema: Optional[Type[ReadSchema]] = None,
        update_schema: Optional[Type[UpdateSchema]] = None,
        search_fields: Optional[List[str]] = None,
    ):
        """
        Initialize the base endpoint router.

        Args:
            service: CRUD service instance
            router: FastAPI router instance
            entity_name: Human-readable name of the entity type
            allow_public_read: Whether to allow public read access
            additional_create_data: Additional data to include when creating entities
            disable_endpoints: List of endpoint names to disable (e.g., ["list", "create"])
            create_schema: Concrete CreateSchema type (required for proper FastAPI validation)
            read_schema: Concrete ReadSchema type (required for proper FastAPI validation)
            update_schema: Concrete UpdateSchema type (required for proper FastAPI validation)
            search_fields: Fields to search in for the list endpoint (defaults to ["name", "description"])
        """
        self.service = service
        self.router = router
        self.entity_name = entity_name
        self.allow_public_read = allow_public_read
        self.additional_create_data = additional_create_data or {}
        self.disable_endpoints = disable_endpoints or []
        self._search_fields = search_fields or ["name", "description"]

        # Store concrete schema types for proper FastAPI validation
        self.create_schema = create_schema
        self.read_schema = read_schema
        self.update_schema = update_schema

        # Register common endpoints
        self._register_common_endpoints()

    def _register_common_endpoints(self) -> None:
        """Register common CRUD endpoints."""
        # Define schema types once for reuse
        # Use object as fallback since Any is not a type class
        # Cast to Type[Any] to satisfy type checkers
        _read_schema: Type[Any] = cast(Type[Any], self.read_schema if self.read_schema else object)

        # Count endpoint - register FIRST before /{entity_id} to avoid route conflicts
        # This is registered here so it's always available, but can be overridden if needed
        @self.router.get(
            "/count",
            response_model=Dict[str, int],
            responses={
                200: {"description": f"Count of {self.entity_name}s"},
            },
        )
        async def count_entities(  # pyright: ignore[reportUnusedFunction]
            db: Session = Depends(get_db),
            logger: logging.Logger = Depends(get_logger),
        ) -> Dict[str, int]:
            """Get total count of entities."""
            count = self.service.count_all(db=db, logger=logger)
            return {"count": count}

        # Create endpoint
        if "create" not in self.disable_endpoints:
            # Use object as fallback since Any is not a type class
            # Cast to Type[Any] to satisfy type checkers
            _create_schema: Type[Any] = cast(Type[Any], self.create_schema if self.create_schema else object)

            @self.router.post(
                "/",
                response_model=_read_schema,
                responses={
                    400: {"description": f"Invalid {self.entity_name} data"},
                    403: {"description": f"Not authorized to create {self.entity_name}"},
                    402: {"description": "Subscription limit reached"},
                },
            )
            async def create_entity(  # pyright: ignore[reportUnusedFunction]
                data: _create_schema,  # type: ignore[valid-type]  # Use the actual schema type for FastAPI validation
                db: Session = Depends(get_db),
                logger: logging.Logger = Depends(get_logger),
                current_user: DBUser = Depends(get_current_user),
            ) -> ModelType:
                """Create a new entity."""
                # At runtime, data is validated by FastAPI as the correct CreateSchema type
                # We cast to Any to satisfy the type checker since CreateSchema is a TypeVar
                return self.service.create(
                    db=db,
                    data=cast(Any, data),  # type: ignore[arg-type]
                    current_user=current_user,
                    logger=logger,
                    additional_data=self.additional_create_data,
                )

        # Get by ID endpoint
        if "get" not in self.disable_endpoints:
            if self.allow_public_read:

                @self.router.get(
                    "/{entity_id}",
                    response_model=_read_schema,
                    responses={
                        404: {"description": f"{self.entity_name.title()} not found"},
                    },
                )
                async def get_entity_public(  # pyright: ignore[reportUnusedFunction]
                    entity_id: int,
                    db: Session = Depends(get_db),
                    logger: logging.Logger = Depends(get_logger),
                ) -> ModelType:
                    """Get an entity by ID (public access)."""
                    return self.service.get_by_id(
                        db=db,
                        entity_id=entity_id,
                        current_user=None,
                        allow_public=True,
                        logger=logger,
                    )

            else:

                @self.router.get(
                    "/{entity_id}",
                    response_model=_read_schema,
                    responses={
                        404: {"description": f"{self.entity_name.title()} not found"},
                        403: {"description": f"Not authorized to access this {self.entity_name}"},
                    },
                )
                async def get_entity_private(  # pyright: ignore[reportUnusedFunction]
                    entity_id: int,
                    db: Session = Depends(get_db),
                    logger: logging.Logger = Depends(get_logger),
                    current_user: DBUser = Depends(get_current_user),
                ) -> ModelType:
                    """Get an entity by ID (private access)."""
                    return self.service.get_by_id(
                        db=db,
                        entity_id=entity_id,
                        current_user=current_user,
                        allow_public=False,
                        logger=logger,
                    )

        # List all endpoint
        if "list" not in self.disable_endpoints:

            @self.router.get(
                "/",
                response_model=List[_read_schema],  # type: ignore[valid-type]
                responses={
                    200: {"description": f"List of {self.entity_name}s retrieved successfully"},
                },
            )
            async def list_entities(  # pyright: ignore[reportUnusedFunction]
                skip: int = Query(0, ge=0, description=f"Number of {self.entity_name}s to skip"),
                limit: int = Query(
                    100,
                    ge=1,
                    le=1000,
                    description=f"Maximum number of {self.entity_name}s to return",
                ),
                search: Optional[str] = Query(
                    None,
                    description=f"Search in {self.entity_name} names and descriptions",
                ),
                db: Session = Depends(get_db),
                logger: logging.Logger = Depends(get_logger),
            ) -> List[ModelType]:
                """List all entities with pagination and search."""
                return self.service.list_all(
                    db=db,
                    skip=skip,
                    limit=limit,
                    search=search,
                    search_fields=self.get_search_fields(),
                    logger=logger,
                )

        # Update endpoint
        if "update" not in self.disable_endpoints:
            # Use object as fallback since Any is not a type class
            # Cast to Type[Any] to satisfy type checkers
            _update_schema: Type[Any] = cast(Type[Any], self.update_schema if self.update_schema else object)

            @self.router.put(
                "/{entity_id}",
                response_model=_read_schema,
                responses={
                    404: {"description": f"{self.entity_name.title()} not found"},
                    403: {"description": f"Not authorized to update this {self.entity_name}"},
                },
            )
            async def update_entity(  # pyright: ignore[reportUnusedFunction]
                entity_id: int,
                data: _update_schema,  # type: ignore[valid-type]
                db: Session = Depends(get_db),
                logger: logging.Logger = Depends(get_logger),
                current_user: DBUser = Depends(get_current_user),
            ) -> ModelType:
                """Update an existing entity."""
                # At runtime, data is validated by FastAPI as the correct UpdateSchema type
                # We cast to Any to satisfy the type checker since UpdateSchema is a TypeVar
                return self.service.update(
                    db=db,
                    entity_id=entity_id,
                    data=cast(Any, data),  # type: ignore[arg-type]
                    current_user=current_user,
                    logger=logger,
                )

        # Delete endpoint
        if "delete" not in self.disable_endpoints:

            @self.router.delete(
                "/{entity_id}",
                response_model=_read_schema,
                responses={
                    404: {"description": f"{self.entity_name.title()} not found"},
                    403: {"description": f"Not authorized to delete this {self.entity_name}"},
                },
            )
            async def delete_entity(  # pyright: ignore[reportUnusedFunction]
                entity_id: int,
                db: Session = Depends(get_db),
                logger: logging.Logger = Depends(get_logger),
                current_user: DBUser = Depends(get_current_user),
            ) -> ModelType:
                """Delete an entity and return the deleted data."""
                # Get the entity before deletion to return it
                entity = self.service.get_by_id(
                    db=db,
                    entity_id=entity_id,
                    current_user=current_user,
                    allow_public=False,
                    logger=logger,
                )

                # Now delete it
                self.service.delete(
                    db=db,
                    entity_id=entity_id,
                    current_user=current_user,
                    logger=logger,
                )

                # Return the entity data that was deleted
                return entity

    def get_search_fields(self) -> List[str]:
        """Get search fields for the entity."""
        return self._search_fields

    def add_filter_endpoint(self, filter_name: str, filter_field: str) -> None:
        """
        Add a filter endpoint for a specific field.

        Args:
            filter_name: Name of the filter (used in URL)
            filter_field: Database field name to filter on
        """

        @self.router.get(
            f"/{filter_name}/{{{filter_name}_id}}",
            response_model=List[ReadSchema],
            responses={
                200: {"description": f"List of {self.entity_name}s filtered by {filter_name} retrieved successfully"},
            },
        )
        async def filter_entities(  # pyright: ignore[reportUnusedFunction]
            filter_id: int,
            skip: int = Query(0, ge=0, description=f"Number of {self.entity_name}s to skip"),
            limit: int = Query(
                100,
                ge=1,
                le=1000,
                description=f"Maximum number of {self.entity_name}s to return",
            ),
            db: Session = Depends(get_db),
            logger: logging.Logger = Depends(get_logger),
        ) -> List[ModelType]:
            """Filter entities by a specific field."""
            return self.service.filter_by_field(  # type: ignore[no-any-return, attr-defined]
                db=db,
                field_name=filter_field,
                field_value=filter_id,
                skip=skip,
                limit=limit,
                logger=logger,
            )

    def add_count_endpoint(self) -> None:
        """
        Add a count endpoint for the entity.

        Note: The count endpoint is now automatically registered in _register_common_endpoints()
        to ensure it's registered before /{entity_id} routes. This method is kept for
        backward compatibility but is now a no-op.
        """
        # Count endpoint is now registered in _register_common_endpoints() to ensure
        # proper route ordering (before /{entity_id} routes)
        pass
