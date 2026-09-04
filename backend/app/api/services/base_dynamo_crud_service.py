from typing import Any, Dict, Generic, Optional, TypeVar
from uuid import UUID

from fastapi import HTTPException, status

from app.api.protocols import HasModelDump
from app.db.dynamo.errors import ItemNotFound
from app.db.dynamo.models import DynamoModel
from app.db.dynamo.repository import DynamoRepository, Page
from app.db.dynamo.users import User as DBUser

TModel = TypeVar("TModel", bound=DynamoModel)
TCreate = TypeVar("TCreate", bound=HasModelDump)
TUpdate = TypeVar("TUpdate", bound=HasModelDump)


class BaseDynamoCRUDService(Generic[TModel, TCreate, TUpdate]):
    def __init__(self, repository: DynamoRepository[TModel], entity_name: str) -> None:
        self.repository = repository
        self.entity_name = entity_name

    def not_found(self) -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{self.entity_name.title()} not found")

    def forbidden(self, action: str = "access") -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorized to {action} this {self.entity_name}"
        )

    def owner_id(self, entity: TModel) -> Optional[UUID]:
        owner = getattr(entity, "user_id", None)
        return owner if isinstance(owner, UUID) else None

    def can_modify(self, entity: TModel, current_user: DBUser) -> bool:
        owner = self.owner_id(entity)
        return owner is None or owner == current_user.id or current_user.is_admin or current_user.is_superuser

    def get_by_id(
        self,
        entity_id: UUID,
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
    ) -> TModel:
        try:
            entity = self.repository.get_or_raise(entity_id)
        except ItemNotFound:
            raise self.not_found()
        if not allow_public:
            if current_user is None or not self.can_modify(entity, current_user):
                raise self.forbidden()
        return entity

    def build_entity(self, data: TCreate, current_user: DBUser, additional_data: Optional[Dict[str, Any]]) -> TModel:
        payload = data.model_dump()
        if additional_data:
            payload.update(additional_data)
        if "user_id" in self.repository.model_cls.model_fields:
            payload["user_id"] = current_user.id
        return self.repository.model_cls.model_validate(payload)

    def create(self, data: TCreate, current_user: DBUser, additional_data: Optional[Dict[str, Any]] = None) -> TModel:
        return self.repository.create(self.build_entity(data, current_user, additional_data))

    def apply_update(self, entity: TModel, changes: Dict[str, Any]) -> TModel:
        return self.repository.put(entity.model_copy(update=changes))

    def update(self, entity_id: UUID, data: TUpdate, current_user: DBUser) -> TModel:
        entity = self.get_by_id(entity_id, allow_public=True)
        if not self.can_modify(entity, current_user):
            raise self.forbidden("update")
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return entity
        if "updated_at" in self.repository.model_cls.model_fields:
            from app.db.dynamo.models import utc_now

            changes["updated_at"] = utc_now()
        return self.apply_update(entity, changes)

    def delete(self, entity_id: UUID, current_user: DBUser) -> TModel:
        entity = self.get_by_id(entity_id, allow_public=True)
        if not self.can_modify(entity, current_user):
            raise self.forbidden("delete")
        self.repository.delete(entity_id)
        return entity

    def list_page(self, *, limit: int, cursor: Optional[str]) -> Page[TModel]:
        return self.repository.scan(limit=limit, cursor=cursor)

    def list_by_parent(
        self,
        index: str,
        key_value: Any,
        *,
        limit: int,
        cursor: Optional[str],
        scan_forward: bool = True,
    ) -> Page[TModel]:
        return self.repository.query(index, key_value, limit=limit, cursor=cursor, scan_forward=scan_forward)

    def count(self) -> int:
        return len(self.repository.scan_all())
