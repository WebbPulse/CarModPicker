from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.build_log import BuildLogPost as DBBuildLogPost
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


def _seed_build_list_with_posts(
    db: Session, owner: DBUser, post_count: int
) -> tuple[uuid.UUID, uuid.UUID, list[DBUser]]:
    bl = DBBuildList(name=f"seed-{uuid.uuid4().hex[:6]}", user_id=owner.id)
    db.add(bl)
    db.flush()
    bl_log = DBBuildLog(build_list_id=bl.id, title=f"Build Log: {bl.name}")
    db.add(bl_log)
    db.flush()

    authors: list[DBUser] = []
    for i in range(post_count):
        author = UserRepository().create_user(
            DBUser(
                username=f"author_{uuid.uuid4().hex[:8]}",
                email=f"author_{uuid.uuid4().hex[:8]}@test.local",
                hashed_password="x",
                email_verified=True,
            )
        )
        authors.append(author)
        post = DBBuildLogPost(
            build_log_id=bl_log.id,
            user_id=author.id,
            content=f"post {i}",
        )
        db.add(post)
    db.commit()
    return bl.id, bl_log.id, authors


def test_posts_fetch_emits_exactly_1_query_and_authors_are_batched(
    db_session: Session,
    test_user: DBUser,
    query_counter,
) -> None:
    _, bl_log_id, authors = _seed_build_list_with_posts(db_session, test_user, post_count=10)

    with query_counter() as counter:
        posts = db_session.scalars(
            select(DBBuildLogPost)
            .where(DBBuildLogPost.build_log_id == bl_log_id)
            .order_by(DBBuildLogPost.created_at)
            .offset(0)
            .limit(10)
        ).all()
        fetched_authors = UserRepository().get_many([p.user_id for p in posts if p.user_id is not None])

    assert counter.count == 1, f"Expected exactly 1 SQL query for the posts fetch. Got {counter.count}:\n" + "\n".join(
        counter.statements
    )
    assert len(posts) == 10
    assert set(fetched_authors) == {a.id for a in authors}


def test_full_endpoint_round_trip_is_bounded(
    client: TestClient,
    db_session: Session,
    test_user: DBUser,
    query_counter,
) -> None:
    bl_id, _, _ = _seed_build_list_with_posts(db_session, test_user, post_count=10)

    with query_counter() as counter:
        response = client.get(f"{settings.API_STR}/build-logs/build-list/{bl_id}?limit=10")

    assert response.status_code == 200
    assert counter.count <= 5, (
        f"Full endpoint round-trip should be bounded (build_list + build_log + count + posts ~= 4; +1 tolerance). "
        f"Got {counter.count}:\n" + "\n".join(counter.statements)
    )


def test_query_count_does_not_scale_with_post_count(
    client: TestClient,
    db_session: Session,
    test_user: DBUser,
    query_counter,
) -> None:
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
