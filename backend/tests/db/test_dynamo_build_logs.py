"""Covers the build log and build log post repositories, including the build list cascade."""

from typing import Any
from uuid import uuid4

import pytest

from app.db.dynamo.build_lists import (
    BuildList,
    BuildListLaborEstimateRepository,
    BuildListPartRepository,
    BuildListPhaseRepository,
    BuildListRepository,
    delete_build_list_cascade,
)
from app.db.dynamo.build_logs import (
    BuildLog,
    BuildLogPost,
    BuildLogPostRepository,
    BuildLogRepository,
    build_log_delete_actions,
)


@pytest.fixture
def build_logs(dynamo_tables: Any) -> BuildLogRepository:
    """A build log repository backed by the moto tables."""
    return BuildLogRepository()


@pytest.fixture
def posts(dynamo_tables: Any) -> BuildLogPostRepository:
    """A build log post repository backed by the moto tables."""
    return BuildLogPostRepository()


def test_for_build_list_finds_the_thread(build_logs: BuildLogRepository) -> None:
    """A build list resolves to its own log and not another's."""
    build_list_id = uuid4()
    created = build_logs.create(BuildLog(build_list_id=build_list_id, title="Build Log: Mine"))
    build_logs.create(BuildLog(build_list_id=uuid4(), title="Build Log: Other"))

    found = build_logs.for_build_list(build_list_id)

    assert found is not None
    assert found.id == created.id


def test_for_build_list_is_none_when_missing(build_logs: BuildLogRepository) -> None:
    """A build list with no log resolves to None."""
    assert build_logs.for_build_list(uuid4()) is None


def test_posts_come_back_oldest_first(posts: BuildLogPostRepository) -> None:
    """Posts for one log come back oldest first, scoped to that log."""
    build_log_id = uuid4()
    first = posts.create(BuildLogPost(build_log_id=build_log_id, user_id=uuid4(), content="first"))
    second = posts.create(BuildLogPost(build_log_id=build_log_id, user_id=uuid4(), content="second"))
    posts.create(BuildLogPost(build_log_id=uuid4(), user_id=uuid4(), content="elsewhere"))

    listed = posts.all_for_build_log(build_log_id)

    assert [post.id for post in listed] == [first.id, second.id]


def test_posts_paginate_with_a_cursor(posts: BuildLogPostRepository) -> None:
    """Post listings page through with a cursor and end with none."""
    build_log_id = uuid4()
    for index in range(3):
        posts.create(BuildLogPost(build_log_id=build_log_id, user_id=uuid4(), content=f"post {index}"))

    page = posts.list_for_build_log(build_log_id, limit=2)
    assert len(page.items) == 2
    assert page.next_cursor is not None

    rest = posts.list_for_build_log(build_log_id, limit=2, cursor=page.next_cursor)
    assert len(rest.items) == 1
    assert rest.next_cursor is None


def test_list_by_user(posts: BuildLogPostRepository) -> None:
    """Listing by author returns only that author's posts."""
    author = uuid4()
    posts.create(BuildLogPost(build_log_id=uuid4(), user_id=author, content="a"))
    posts.create(BuildLogPost(build_log_id=uuid4(), user_id=author, content="b"))
    posts.create(BuildLogPost(build_log_id=uuid4(), user_id=uuid4(), content="c"))

    assert len(posts.list_by_user(author)) == 2


def test_anonymous_posts_have_no_user(posts: BuildLogPostRepository) -> None:
    """A post created without an author stores no user id."""
    post = posts.create(BuildLogPost(build_log_id=uuid4(), content="orphaned"))

    assert posts.get_or_raise(post.id).user_id is None


def test_build_list_cascade_removes_the_log_and_its_posts(
    build_logs: BuildLogRepository, posts: BuildLogPostRepository
) -> None:
    """Deleting a build list removes its log and posts and leaves other logs alone."""
    build_lists = BuildListRepository()
    build_list = build_lists.create(BuildList(name="Doomed", user_id=uuid4()))
    log = build_logs.create(BuildLog(build_list_id=build_list.id, title="Build Log: Doomed"))
    post = posts.create(BuildLogPost(build_log_id=log.id, user_id=uuid4(), content="gone"))
    survivor = posts.create(BuildLogPost(build_log_id=uuid4(), user_id=uuid4(), content="kept"))

    delete_build_list_cascade(
        build_list.id,
        build_lists=build_lists,
        parts=BuildListPartRepository(),
        phases=BuildListPhaseRepository(),
        labor_estimates=BuildListLaborEstimateRepository(),
        extra_actions=build_log_delete_actions(build_list.id, build_logs=build_logs, posts=posts),
    )

    assert build_lists.get(build_list.id) is None
    assert build_logs.get(log.id) is None
    assert posts.get(post.id) is None
    assert posts.get(survivor.id) is not None


def test_delete_actions_are_empty_without_a_log(build_logs: BuildLogRepository, posts: BuildLogPostRepository) -> None:
    """A build list with no log yields no delete actions."""
    assert build_log_delete_actions(uuid4(), build_logs=build_logs, posts=posts) == []
