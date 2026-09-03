"""DATA-10 regression: lazy='raise' relationships fail loud on unloaded access,
succeed when caller pre-loads via selectinload.

WARN 10 note: SQLAlchemy's ``lazy="raise"`` raises ``InvalidRequestError`` on the
FIRST attribute access of an unloaded relationship. No ``db_session.expire()`` is
needed — a freshly-fetched entity (without the selectinload option) already has
the relationship in the "unloaded" state. The access itself triggers the raise.

Targets (per Phase 4 D-28):
- ``BuildList.build_list_parts``
- ``BuildList.build_list_phases``

Every caller of these relationships must pre-load via
``.options(selectinload(...))`` — any future site that misses the option fails at
test time instead of silently N+1-ing in production.
"""

from __future__ import annotations

import pytest
import sqlalchemy.exc
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.models.build_list import BuildList as DBBuildList
from app.db.dynamo.users import User as DBUser


def test_build_list_parts_raises_without_selectinload(db_session: Session, test_user: DBUser) -> None:
    """Fetch WITHOUT selectinload — first access to ``build_list.build_list_parts`` must raise."""
    bl = DBBuildList(name="lazy_raise_parts_raise", user_id=test_user.id)
    db_session.add(bl)
    db_session.commit()

    fetched = db_session.scalars(select(DBBuildList).where(DBBuildList.id == bl.id)).first()
    assert fetched is not None
    with pytest.raises(sqlalchemy.exc.InvalidRequestError):
        _ = fetched.build_list_parts


def test_build_list_parts_works_with_selectinload(db_session: Session, test_user: DBUser) -> None:
    """Fetch WITH selectinload(build_list_parts) — access returns the (empty) list."""
    bl = DBBuildList(name="lazy_raise_parts_works", user_id=test_user.id)
    db_session.add(bl)
    db_session.commit()

    fetched = db_session.scalars(
        select(DBBuildList).where(DBBuildList.id == bl.id).options(selectinload(DBBuildList.build_list_parts))
    ).first()
    assert fetched is not None
    # empty list is fine; the access itself must not raise
    assert fetched.build_list_parts == []


def test_build_list_phases_raises_without_selectinload(db_session: Session, test_user: DBUser) -> None:
    """Fetch WITHOUT selectinload — first access to ``build_list.build_list_phases`` must raise."""
    bl = DBBuildList(name="lazy_raise_phases_raise", user_id=test_user.id)
    db_session.add(bl)
    db_session.commit()

    fetched = db_session.scalars(select(DBBuildList).where(DBBuildList.id == bl.id)).first()
    assert fetched is not None
    with pytest.raises(sqlalchemy.exc.InvalidRequestError):
        _ = fetched.build_list_phases


def test_build_list_phases_works_with_selectinload(db_session: Session, test_user: DBUser) -> None:
    """Fetch WITH selectinload(build_list_phases) — access returns the (empty) list."""
    bl = DBBuildList(name="lazy_raise_phases_works", user_id=test_user.id)
    db_session.add(bl)
    db_session.commit()

    fetched = db_session.scalars(
        select(DBBuildList).where(DBBuildList.id == bl.id).options(selectinload(DBBuildList.build_list_phases))
    ).first()
    assert fetched is not None
    assert fetched.build_list_phases == []
