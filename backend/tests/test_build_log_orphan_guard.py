"""DATA-08 invariant: every build_list has a build_log row (eager-create).

Phase 4 plan 04-02 task 3. Exercises the eager-create path in
backend/app/api/services/build_list_service.py and the post-backfill
invariant asserted by D-27: no build list exists without a build log.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.schemas.build_list import BuildListCreate
from app.api.services.build_list_service import BuildListService
from app.db.dynamo.build_lists import BuildListRepository
from app.db.dynamo.users import User
from tests.conftest import create_car_orm_in_db

logger = logging.getLogger(__name__)


def test_new_build_list_has_eager_build_log(db_session: Session, test_user: User) -> None:
    """Seed a BuildList via the service; assert a BuildLog row exists (D-23)."""
    car = create_car_orm_in_db(
        db_session,
        make="Honda",
        model="Civic",
        generation_name="10th Gen",
        start_year=2016,
        end_year=2021,
    )
    assert car is not None

    svc = BuildListService()
    payload = BuildListCreate(name="test-eager-create", description="seed", car_id=car.id)
    bl = svc.create(payload, test_user, db=db_session, logger=logger)

    # Invariant: the just-created BuildList has a BuildLog row.
    bl_row = db_session.scalars(select(DBBuildLog).where(DBBuildLog.build_list_id == bl.id)).first()
    assert bl_row is not None, f"BuildList {bl.id} has no eager BuildLog row"


def test_no_orphan_build_lists(db_session: Session, premium_test_user: User) -> None:
    """The DATA-08 invariant (D-27): no build_list lacks a build_log.

    Uses premium_test_user to bypass the free-tier single-build-list cap so we
    can seed multiple build_lists in a single test.
    """
    car = create_car_orm_in_db(
        db_session,
        make="Toyota",
        model="Supra",
        generation_name="A90",
        start_year=2019,
        end_year=2025,
    )
    assert car is not None

    svc = BuildListService()
    for i in range(3):
        svc.create(
            BuildListCreate(name=f"seed-orphan-test-{i}", description=None, car_id=car.id),
            premium_test_user,
            db=db_session,
            logger=logger,
        )

    logged_ids = set(db_session.scalars(select(DBBuildLog.build_list_id)).all())
    orphans = [bl.id for bl in BuildListRepository().scan_all() if bl.id not in logged_ids]
    assert orphans == [], f"{len(orphans)} build lists lack a build_log: {orphans}"
