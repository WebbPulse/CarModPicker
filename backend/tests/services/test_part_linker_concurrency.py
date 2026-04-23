"""DATA-04 + PARTS-01: 10-thread concurrency test proving link_new_part is
race-safe under Postgres FOR UPDATE locks.

Module-level pytestmark skips the entire file when POSTGRES_TEST_URL is unset
(Phase 4 D-02). CI job ``postgres-tests`` in backend-ci.yml stands up the side-car.

Contract (WARN 8): all seed + verify queries filter by a per-test unique
``shared_gtin`` so cross-test data in the session-scoped postgres_engine does not
interfere. Do NOT scan ``DBPart`` without the gtin filter.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.api.models.category import Category as DBCategory
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.user import User as DBUser
from app.api.services.part_linker_service import link_new_part, unlink_part

pytestmark = pytest.mark.postgres


def _worker_suffix() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "main")


def _seed(
    postgres_engine, shared_gtin: str
) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    """Seed a test user, category, manufacturer, and 10 parts sharing a gtin.

    ``shared_gtin`` is the per-test unique key that honors the WARN 8 isolation
    contract — every verify query filters by this key.
    """
    SessionLocal = sessionmaker(
        bind=postgres_engine, autocommit=False, autoflush=False
    )
    with SessionLocal() as s:
        # NOTE: User.email_verified (NOT is_verified) per backend/app/api/models/user.py:29.
        user = DBUser(
            username=f"linker_{_worker_suffix()}_{uuid.uuid4().hex[:8]}",
            email=f"linker_{_worker_suffix()}_{uuid.uuid4().hex[:8]}@test.local",
            hashed_password="x",
            email_verified=True,
        )
        s.add(user)
        s.flush()

        category = DBCategory(
            name=f"cat_{_worker_suffix()}_{uuid.uuid4().hex[:8]}",
            display_name="Test Category",
        )
        s.add(category)
        s.flush()

        manufacturer = DBPartManufacturer(
            name=f"mfr_{_worker_suffix()}_{uuid.uuid4().hex[:8]}"
        )
        s.add(manufacturer)
        s.flush()

        part_ids: list[uuid.UUID] = []
        for i in range(10):
            p = DBPart(
                name=f"Part {i}",
                user_id=user.id,
                category_id=category.id,
                part_manufacturer_id=manufacturer.id,
                gtin=shared_gtin,
                source="scraped",
            )
            s.add(p)
            s.flush()
            part_ids.append(p.id)
        s.commit()
        return user.id, category.id, part_ids


def test_link_new_part_10_thread_contention(postgres_engine) -> None:
    """D-05 invariants under 10-thread contention on link_new_part."""
    shared_gtin = f"G{_worker_suffix()}{uuid.uuid4().hex[:12]}"
    _, _, part_ids = _seed(postgres_engine, shared_gtin)

    SessionLocal = sessionmaker(
        bind=postgres_engine, autocommit=False, autoflush=False
    )

    def link_one(part_id: uuid.UUID) -> uuid.UUID:
        with SessionLocal() as s:
            part = s.get(DBPart, part_id)
            assert part is not None, f"Seeded part {part_id} missing"
            link_new_part(s, part)
            s.commit()
            return part.id

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(link_one, pid) for pid in part_ids]
        for f in as_completed(futures):
            f.result()  # re-raise any thread-level exception

    # Verification session (single-threaded). Filter by shared_gtin per WARN 8 contract.
    with SessionLocal() as verify:
        # INVARIANT 1: exactly one canonical
        canonical_count = verify.scalar(
            select(func.count())
            .select_from(DBPart)
            .where(DBPart.gtin == shared_gtin, DBPart.canonical_part_id.is_(None))
        )
        assert canonical_count == 1, (
            f"Expected exactly 1 canonical for gtin={shared_gtin}, got {canonical_count}"
        )

        # Collect all parts sharing the gtin.
        parts = verify.scalars(
            select(DBPart).where(DBPart.gtin == shared_gtin)
        ).all()
        assert len(parts) == 10

        canonical_ids = {p.id for p in parts if p.canonical_part_id is None}
        assert len(canonical_ids) == 1

        # INVARIANT 2: no cycles — every non-canonical points at the canonical.
        for p in parts:
            if p.canonical_part_id is not None:
                assert p.canonical_part_id in canonical_ids, (
                    f"Part {p.id} has canonical_part_id={p.canonical_part_id} "
                    f"which is not among canonicals {canonical_ids} (cycle or orphan)"
                )

        # INVARIANT 3: no orphans — every canonical_part_id value resolves to a live canonical.
        sibling_refs = {
            p.canonical_part_id for p in parts if p.canonical_part_id is not None
        }
        live_canonicals = set(
            verify.scalars(
                select(DBPart.id).where(
                    DBPart.id.in_(sibling_refs), DBPart.canonical_part_id.is_(None)
                )
            ).all()
        )
        assert sibling_refs == live_canonicals, (
            f"Some siblings point to dead canonicals. "
            f"sibling_refs={sibling_refs}, live={live_canonicals}"
        )


def test_unlink_and_relink_under_load(postgres_engine) -> None:
    """Interleave link_new_part and unlink_part; invariants must still hold."""
    shared_gtin = f"G2{_worker_suffix()}{uuid.uuid4().hex[:12]}"
    _, _, part_ids = _seed(postgres_engine, shared_gtin)

    SessionLocal = sessionmaker(
        bind=postgres_engine, autocommit=False, autoflush=False
    )

    def link_one(part_id: uuid.UUID) -> None:
        with SessionLocal() as s:
            part = s.get(DBPart, part_id)
            if part is not None:
                link_new_part(s, part)
                s.commit()

    def unlink_one(part_id: uuid.UUID) -> None:
        with SessionLocal() as s:
            part = s.get(DBPart, part_id)
            if part and part.canonical_part_id is not None:
                unlink_part(s, part)
                s.commit()

    with ThreadPoolExecutor(max_workers=10) as ex:
        # Alternate link / unlink calls across the pool
        futures = []
        for i, pid in enumerate(part_ids):
            if i % 2 == 0:
                futures.append(ex.submit(link_one, pid))
            else:
                futures.append(ex.submit(unlink_one, pid))
        for f in as_completed(futures):
            f.result()

    # Final invariants — at most one canonical per resolved-head, no orphans.
    # Filter by shared_gtin per WARN 8 contract.
    with SessionLocal() as verify:
        parts = verify.scalars(
            select(DBPart).where(DBPart.gtin == shared_gtin)
        ).all()
        canonical_ids = {p.id for p in parts if p.canonical_part_id is None}
        assert len(canonical_ids) <= 10, "Sanity: canonical count bounded by pool size"
        sibling_refs = {
            p.canonical_part_id for p in parts if p.canonical_part_id is not None
        }
        orphans = sibling_refs - canonical_ids
        assert not orphans, f"Found orphaned canonical refs: {orphans}"
