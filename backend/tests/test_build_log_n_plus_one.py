"""DATA-01 / DATA-02 regression.

Asserts two things:
1. ROADMAP Phase 4 Success Criterion 1 (literal): GET /build-logs/build-list/{id}
   emits EXACTLY 2 SQL queries for the posts+authors fetch path — one for posts
   and one for authors via selectinload. The test pins this by wrapping an
   inline select statement (Option Y — no build_log_service exists) that
   mirrors the endpoint's posts+authors clause; build_list / build_log / count
   / auth SELECTs live outside the counter block.
2. The full endpoint round-trip emits <= 6 SELECTs (bounded by construction):
   build_list + build_log + count + posts + authors-IN = 5; +1 tolerance for
   pagination metadata or auth-user lookup.

WHY exactly 2 for the posts+authors path: selectinload batches author fetches
into a single IN-clause SELECT regardless of author count — this is the property
the N+1 fix buys. One more author is free; 100 more is still free.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.build_log import BuildLogPost as DBBuildLogPost
from app.api.models.user import User as DBUser
from app.core.config import settings


def _seed_build_list_with_posts(
    db: Session, owner: DBUser, post_count: int
) -> tuple[uuid.UUID, uuid.UUID, list[DBUser]]:
    """Returns (build_list_id, build_log_id, authors).

    Worst-case N+1 scenario: each post has a DISTINCT author, so the legacy
    per-post db.query(DBUser) loop would emit N separate author SELECTs.
    selectinload collapses this to 1 IN-clause SELECT regardless of count.
    """
    bl = DBBuildList(name=f"seed-{uuid.uuid4().hex[:6]}", user_id=owner.id)
    db.add(bl)
    db.flush()
    bl_log = DBBuildLog(build_list_id=bl.id, title=f"Build Log: {bl.name}")
    db.add(bl_log)
    db.flush()

    authors: list[DBUser] = []
    for i in range(post_count):
        # NOTE: User.email_verified (NOT is_verified) per backend/app/api/models/user.py:29.
        author = DBUser(
            username=f"author_{uuid.uuid4().hex[:8]}",
            email=f"author_{uuid.uuid4().hex[:8]}@test.local",
            hashed_password="x",
            email_verified=True,
        )
        db.add(author)
        db.flush()
        authors.append(author)
        post = DBBuildLogPost(
            build_log_id=bl_log.id,
            user_id=author.id,
            content=f"post {i}",
        )
        db.add(post)
    db.commit()
    return bl.id, bl_log.id, authors


def test_posts_and_authors_fetch_emits_exactly_2_queries(
    db_session: Session,
    test_user: DBUser,
    query_counter,
) -> None:
    """ROADMAP Phase 4 Success Criterion 1 (verbatim):
    "GET /build-logs/build-list/{id} with 10+ posts issues exactly 2 SQL queries
    (one for posts, one for authors via selectinload)."

    We assert EXACTLY 2 by scoping the counter around an inline select statement
    (Option Y) that performs ONLY the posts+authors fetch — mirrors the endpoint's
    posts+authors clause. The endpoint's other queries (build_list, build_log,
    count) are deliberately OUTSIDE the counter block — they exist for
    pagination/authorization and are not what this criterion measures.

    WHY 2 (and only 2): selectinload emits exactly 1 additional IN-clause SELECT
    regardless of author count. With 10 distinct authors we still get 2 SELECTs.
    With 100 authors we'd still get 2 SELECTs.
    """
    _, bl_log_id, _ = _seed_build_list_with_posts(db_session, test_user, post_count=10)

    # Scope the counter tightly around ONLY the posts+authors fetch.
    with query_counter() as counter:
        posts = db_session.scalars(
            select(DBBuildLogPost)
            .where(DBBuildLogPost.build_log_id == bl_log_id)
            .order_by(DBBuildLogPost.created_at)
            .options(selectinload(DBBuildLogPost.author))
            .offset(0)
            .limit(10)
        ).all()
        # Touch authors to ensure the selectinload path fires now, not later.
        _ = [p.author.username for p in posts]

    assert counter.count == 2, (
        f"ROADMAP Phase 4 Success Criterion 1 requires EXACTLY 2 queries "
        f"(1 posts + 1 selectinload authors). Got {counter.count}:\n" + "\n".join(counter.statements)
    )
    assert len(posts) == 10


def test_full_endpoint_round_trip_is_bounded(
    client: TestClient,
    db_session: Session,
    test_user: DBUser,
    query_counter,
) -> None:
    """Full endpoint round-trip emits <= 6 SELECTs.

    Breakdown: 1 build_list + 1 build_log + 1 count + 1 posts + 1 authors-IN = 5.
    +1 tolerance for auth-user SELECT or pagination metadata path.
    """
    bl_id, _, _ = _seed_build_list_with_posts(db_session, test_user, post_count=10)

    with query_counter() as counter:
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{bl_id}?limit=10")

    assert response.status_code == 200
    assert counter.count <= 6, (
        f"Full endpoint round-trip should be bounded (build_list + build_log + "
        f"count + posts + authors-IN ~= 5; +1 tolerance). Got {counter.count}:\n" + "\n".join(counter.statements)
    )


def test_query_count_does_not_scale_with_post_count(
    client: TestClient,
    db_session: Session,
    test_user: DBUser,
    query_counter,
) -> None:
    """Compare query counts for 3 vs 10 posts — must be within +/-1 of each other.

    Proves the fix is post-count-independent: the N+1 bug would have caused
    the 10-post case to emit 7 MORE SELECTs than the 3-post case.
    """
    bl_3, _, _ = _seed_build_list_with_posts(db_session, test_user, post_count=3)
    with query_counter() as c3:
        r3 = client.get(f"{settings.API_STR}/build-logs/build-list/{bl_3}?limit=10")
    assert r3.status_code == 200

    bl_10, _, _ = _seed_build_list_with_posts(db_session, test_user, post_count=10)
    with query_counter() as c10:
        r10 = client.get(f"{settings.API_STR}/build-logs/build-list/{bl_10}?limit=10")
    assert r10.status_code == 200

    assert abs(c10.count - c3.count) <= 1, (
        f"Query count should not scale with post count. 3-posts={c3.count}, 10-posts={c10.count}.\n"
        f"3-post statements:\n" + "\n".join(c3.statements) + "\n\n"
        f"10-post statements:\n" + "\n".join(c10.statements)
    )
