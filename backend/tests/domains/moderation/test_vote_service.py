"""Tests for vote service."""

import logging
import os
from typing import Any

from app.api.schemas.vote import EntityType, VoteCreate, VoteType
from app.api.services.vote_service import VoteService
from app.db.dynamo.build_lists import BuildList, BuildListRepository
from app.db.dynamo.catalog import Part, PartRepository
from app.db.dynamo.moderation import VoteRepository
from app.db.dynamo.users import User, UserRepository
from tests.conftest import save_catalog


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestVoteService:
    """Test cases for vote service."""

    def test_vote_on_car(self, db_session: Any, test_user: User) -> None:
        """Test voting on a car."""
        from tests.conftest import create_car_orm_in_db

        car = create_car_orm_in_db(
            db_session,
            make="Honda",
            model="Civic",
            generation_name="10th Gen",
            start_year=2016,
            end_year=2021,
        )

        service = VoteService()
        logger = logging.getLogger(__name__)
        vote_data = VoteCreate(vote_type=VoteType.UPVOTE)
        result = service.vote_on_entity(EntityType.CAR_GENERATION, car.id, test_user.id, vote_data, logger)

        assert result.vote is not None
        vote = result.vote
        assert vote.entity_type == "car_generation"
        assert vote.entity_id == car.id
        assert vote.user_id == test_user.id
        assert vote.vote_type == "upvote"
        assert (result.upvotes, result.downvotes, result.total_votes, result.vote_score) == (1, 0, 1, 1)

    def test_vote_on_build_list(self, db_session: Any, test_user: User) -> None:
        """Test voting on a build list."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        logger = logging.getLogger(__name__)
        vote_data = VoteCreate(vote_type=VoteType.UPVOTE)
        result = service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, test_user.id, vote_data, logger)

        assert result.vote is not None
        vote = result.vote
        assert vote.entity_type == "build_list"
        assert vote.entity_id == build_list.id
        assert vote.user_id == test_user.id
        assert vote.vote_type == "upvote"
        assert (result.upvotes, result.downvotes, result.total_votes, result.vote_score) == (1, 0, 1, 1)

    def test_vote_on_part(self, db_session: Any, test_user: User) -> None:
        """Test voting on a global part."""
        from app.db.dynamo.catalog import Category, CategoryRepository

        category = next(iter(CategoryRepository().list_all()), None)
        if not category:
            category = Category(
                name="test_category",
                display_name="Test Category",
                description="A test category",
                is_active=True,
                sort_order=1,
            )
            category = save_catalog(category)

        part = Part(
            name=get_unique_name("test_part"),
            description="Test part",
            user_id=test_user.id,
            category_id=category.id,
        )
        part = save_catalog(part)

        service = VoteService()
        logger = logging.getLogger(__name__)
        vote_data = VoteCreate(vote_type=VoteType.DOWNVOTE)
        result = service.vote_on_entity(EntityType.PART, part.id, test_user.id, vote_data, logger)

        assert result.vote is not None
        vote = result.vote
        assert vote.entity_type == "part"
        assert vote.entity_id == part.id
        assert vote.user_id == test_user.id
        assert vote.vote_type == "downvote"
        assert (result.upvotes, result.downvotes, result.total_votes, result.vote_score) == (0, 1, 1, -1)

        assert PartRepository().get(part.id).net_votes == 0

    def test_vote_update_existing(self, db_session: Any, test_user: User) -> None:
        """Test updating an existing vote."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list2"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        logger = logging.getLogger(__name__)
        vote_data1 = VoteCreate(vote_type=VoteType.UPVOTE)
        first = service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, test_user.id, vote_data1, logger)

        vote_data2 = VoteCreate(vote_type=VoteType.DOWNVOTE)
        second = service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, test_user.id, vote_data2, logger)

        assert first.vote is not None and second.vote is not None
        assert second.vote.id == first.vote.id
        assert second.vote.vote_type == "downvote"
        assert (second.upvotes, second.downvotes, second.total_votes, second.vote_score) == (0, 1, 1, -1)

    def test_remove_vote(self, db_session: Any, test_user: User) -> None:
        """Test removing a vote."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list3"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        logger = logging.getLogger(__name__)
        vote_data = VoteCreate(vote_type=VoteType.UPVOTE)
        created = service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, test_user.id, vote_data, logger)
        assert created.vote is not None

        result = service.remove_vote(EntityType.BUILD_LIST, build_list.id, test_user.id, logger)

        assert result is not None
        assert result.vote is None
        assert (result.upvotes, result.downvotes, result.total_votes, result.vote_score) == (0, 0, 0, 0)

        db_vote = VoteRepository().get(created.vote.id)
        assert db_vote is None

    def test_remove_vote_not_exists(self, db_session: Any, test_user: User) -> None:
        """Test removing a vote that doesn't exist."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list4"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        logger = logging.getLogger(__name__)
        result = service.remove_vote(EntityType.BUILD_LIST, build_list.id, test_user.id, logger)

        assert result is None

    def test_get_vote_summary(self, db_session: Any, test_user: User) -> None:
        """Test getting vote summary."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list5"),
                description="Test",
                user_id=test_user.id,
            )
        )

        user2 = User(
            username=get_unique_name("user2"),
            email=f"{get_unique_name('user2')}@example.com",
            email_verified=True,
            disabled=False,
        )
        user3 = User(
            username=get_unique_name("user3"),
            email=f"{get_unique_name('user3')}@example.com",
            email_verified=True,
            disabled=False,
        )
        user2 = UserRepository().create_user(user2)
        user3 = UserRepository().create_user(user3)

        service = VoteService()
        logger = logging.getLogger(__name__)

        vote_data_up = VoteCreate(vote_type=VoteType.UPVOTE)
        service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, test_user.id, vote_data_up, logger)
        service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, user2.id, vote_data_up, logger)

        vote_data_down = VoteCreate(vote_type=VoteType.DOWNVOTE)
        service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, user3.id, vote_data_down, logger)

        summary = service.get_vote_summary(EntityType.BUILD_LIST, build_list.id)

        assert summary.entity_id == build_list.id
        assert summary.entity_type == "build_list"
        assert summary.upvotes == 2
        assert summary.downvotes == 1
        assert summary.total_votes == 3
        assert summary.vote_score == 1

    def test_get_vote_summary_with_user_vote(self, db_session: Any, test_user: User) -> None:
        """Test getting vote summary with user's vote."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list6"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        logger = logging.getLogger(__name__)
        vote_data = VoteCreate(vote_type=VoteType.UPVOTE)
        service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, test_user.id, vote_data, logger)

        summary = service.get_vote_summary(EntityType.BUILD_LIST, build_list.id, user_id=test_user.id)

        assert summary.user_vote == "upvote"

    def test_get_vote_summary_no_user_vote(self, db_session: Any, test_user: User) -> None:
        """Test getting vote summary when user hasn't voted."""
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list7"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        summary = service.get_vote_summary(EntityType.BUILD_LIST, build_list.id)

        assert summary.user_vote is None

    def test_get_flagged_entities(self, db_session: Any, test_user: User) -> None:
        """Test getting flagged entities."""

        UserRepository().create_user(
            User(
                username=get_unique_name("user4"),
                email=f"{get_unique_name('user4')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("flagged_build_list"),
                description="Test",
                user_id=test_user.id,
            )
        )

        service = VoteService()
        logger = logging.getLogger(__name__)

        vote_data_down = VoteCreate(vote_type=VoteType.DOWNVOTE)
        vote_data_up = VoteCreate(vote_type=VoteType.UPVOTE)

        users = []
        for i in range(7):
            user = User(
                username=get_unique_name(f"voter{i}"),
                email=f"{get_unique_name(f'voter{i}')}@example.com",
                email_verified=True,
                disabled=False,
            )
            users.append(UserRepository().create_user(user))

        for i in range(5):
            service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, users[i].id, vote_data_down, logger)

        for i in range(5, 7):
            service.vote_on_entity(EntityType.BUILD_LIST, build_list.id, users[i].id, vote_data_up, logger)

        flagged = service.get_flagged_entities(EntityType.BUILD_LIST, limit=10)

        assert isinstance(flagged, list)
        flagged_ids = [f.entity_id for f in flagged]
        assert build_list.id in flagged_ids
