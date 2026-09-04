from datetime import datetime
from typing import Callable, Iterable, TypeVar

from app.api.schemas.pagination import CursorPage
from app.api.utils.cursor_pagination import paginate_in_memory
from app.core.config import settings
from app.db.dynamo.models import DynamoModel
from app.db.dynamo.repository import DynamoRepository
from app.db.dynamo.serialization import encode_datetime

TModel = TypeVar("TModel", bound=DynamoModel)
U = TypeVar("U")

NUMERIC_WIDTH = 15
NUMERIC_MAX = 10**NUMERIC_WIDTH - 1


def normalize_term(term: str | None) -> str:
    return (term or "").strip().lower()


def contains(term: str, *values: object) -> bool:
    if not term:
        return True
    for value in values:
        if value is not None and term in str(value).lower():
            return True
    return False


def starts_with(term: str, *values: object) -> bool:
    if not term:
        return True
    for value in values:
        if value is not None and str(value).lower().startswith(term):
            return True
    return False


def scan_matching(
    repository: DynamoRepository[TModel],
    predicate: Callable[[TModel], bool],
    *,
    page_limit: int | None = None,
    page_size: int | None = None,
) -> list[TModel]:
    max_pages = page_limit if page_limit is not None else settings.DYNAMODB_SEARCH_SCAN_PAGE_LIMIT
    matched: list[TModel] = []
    cursor: str | None = None
    for _ in range(max_pages):
        page = repository.scan(limit=page_size, cursor=cursor)
        matched.extend(item for item in page.items if predicate(item))
        cursor = page.next_cursor
        if cursor is None:
            break
    return matched


def _invert_ascii(value: str) -> str:
    return "".join(chr(0x7E - (ord(char) - 0x20)) if 0x20 <= ord(char) <= 0x7E else char for char in value)


def text_key(value: object, *, descending: bool = False, missing_last: bool = True) -> str:
    if value is None or value == "":
        return "~" if missing_last else " "
    text = str(value).lower()
    return _invert_ascii(text) if descending else text


def numeric_key(value: int | float | None, *, descending: bool = False, missing_last: bool = True) -> str:
    if value is None:
        return "~" if missing_last else " "
    clamped = max(0, min(int(value), NUMERIC_MAX))
    if descending:
        clamped = NUMERIC_MAX - clamped
    return f"{clamped:0{NUMERIC_WIDTH}d}"


def datetime_key(value: datetime | None, *, descending: bool = False) -> str:
    if value is None:
        return "~"
    encoded = encode_datetime(value)
    return _invert_ascii(encoded) if descending else encoded


def compound_key(*keys: str) -> str:
    return "\x1f".join(keys)


def paginate(
    items: Iterable[TModel],
    *,
    limit: int,
    cursor: str | None,
    sort_key: Callable[[TModel], str],
    transform: Callable[[TModel], U],
) -> CursorPage[U]:
    return paginate_in_memory(
        items,
        limit=limit,
        cursor=cursor,
        sort_key=sort_key,
        item_id=lambda item: str(item.id),
        transform=transform,
    )
