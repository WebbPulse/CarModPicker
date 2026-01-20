"""Tests for subscription service."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList
from app.api.models.subscription import Subscription
from app.api.models.user import User
from app.api.services.subscription_service import SubscriptionService


class TestSubscriptionService:
    """Test cases for subscription service."""

    def test_get_user_limits_free_tier(self, db_session: Session, test_user: User) -> None:
        """Test getting limits for free tier user."""
        # Ensure user is on free tier
        test_user.subscription_tier = "free"
        test_user.subscription_status = "active"
        db_session.commit()

        limits = SubscriptionService.get_user_limits(test_user)
        assert limits["cars"] == 3
        assert limits["build_lists"] == 5

    def test_get_user_limits_premium_tier(self, db_session: Session, test_user: User) -> None:
        """Test getting limits for premium tier user."""
        # Set user to premium
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "active"
        db_session.commit()

        limits = SubscriptionService.get_user_limits(test_user)
        assert limits["cars"] is None  # Unlimited
        assert limits["build_lists"] is None  # Unlimited

    def test_get_user_limits_premium_inactive(self, db_session: Session, test_user: User) -> None:
        """Test getting limits for premium tier user with inactive status."""
        # Set user to premium but inactive
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "inactive"
        db_session.commit()

        limits = SubscriptionService.get_user_limits(test_user)
        # Should return free tier limits since status is not active
        assert limits["cars"] == 3
        assert limits["build_lists"] == 5

    def test_get_user_usage(self, db_session: Session, test_user: User) -> None:
        """Test getting user usage statistics."""
        # Create build lists for the user
        build_list1 = BuildList(
            name="Test Build List 1",
            description="Test",
            user_id=test_user.id,
        )
        build_list2 = BuildList(
            name="Test Build List 2",
            description="Test",
            user_id=test_user.id,
        )
        db_session.add_all([build_list1, build_list2])
        db_session.commit()

        usage = SubscriptionService.get_user_usage(db_session, test_user.id)
        assert usage["cars"] == 0  # Cars are centrally managed
        assert usage["build_lists"] == 2

    def test_get_user_usage_no_build_lists(self, db_session: Session, test_user: User) -> None:
        """Test getting user usage with no build lists."""
        usage = SubscriptionService.get_user_usage(db_session, test_user.id)
        assert usage["cars"] == 0
        assert usage["build_lists"] == 0

    def test_can_create_car(self, db_session: Session, test_user: User) -> None:
        """Test checking if user can create a car."""
        # Cars are centrally managed, so regular users cannot create cars
        result = SubscriptionService.can_create_car(db_session, test_user)
        assert result is False

    def test_can_create_build_list_free_tier_within_limit(self, db_session: Session, test_user: User) -> None:
        """Test checking if free tier user can create build list within limit."""
        # Set user to free tier
        test_user.subscription_tier = "free"
        test_user.subscription_status = "active"
        db_session.commit()

        # Create 3 build lists (under the limit of 5)
        for i in range(3):
            build_list = BuildList(
                name=f"Test Build List {i}",
                description="Test",
                user_id=test_user.id,
            )
            db_session.add(build_list)
        db_session.commit()

        result = SubscriptionService.can_create_build_list(db_session, test_user)
        assert result is True

    def test_can_create_build_list_free_tier_at_limit(self, db_session: Session, test_user: User) -> None:
        """Test checking if free tier user can create build list at limit."""
        # Set user to free tier
        test_user.subscription_tier = "free"
        test_user.subscription_status = "active"
        db_session.commit()

        # Create 5 build lists (at the limit)
        for i in range(5):
            build_list = BuildList(
                name=f"Test Build List {i}",
                description="Test",
                user_id=test_user.id,
            )
            db_session.add(build_list)
        db_session.commit()

        result = SubscriptionService.can_create_build_list(db_session, test_user)
        assert result is False

    def test_can_create_build_list_premium_tier(self, db_session: Session, test_user: User) -> None:
        """Test checking if premium tier user can create build list (unlimited)."""
        # Set user to premium
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "active"
        db_session.commit()

        # Create many build lists
        for i in range(10):
            build_list = BuildList(
                name=f"Test Build List {i}",
                description="Test",
                user_id=test_user.id,
            )
            db_session.add(build_list)
        db_session.commit()

        result = SubscriptionService.can_create_build_list(db_session, test_user)
        assert result is True  # Premium users have unlimited build lists

    def test_can_create_global_part(self, db_session: Session, test_user: User) -> None:
        """Test checking if user can create global part."""
        # All users can create global parts
        result = SubscriptionService.can_create_global_part(db_session, test_user)
        assert result is True

    def test_get_subscription_status_free_tier(self, db_session: Session, test_user: User) -> None:
        """Test getting subscription status for free tier user."""
        # Set user to free tier
        test_user.subscription_tier = "free"
        test_user.subscription_status = "active"
        db_session.commit()

        status = SubscriptionService.get_subscription_status(db_session, test_user)
        assert status.tier == "free"
        assert status.status == "active"
        assert status.limits["cars"] == 3
        assert status.limits["build_lists"] == 5
        assert "usage" in status.dict()

    def test_get_subscription_status_premium_tier(self, db_session: Session, test_user: User) -> None:
        """Test getting subscription status for premium tier user."""
        # Set user to premium
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "active"
        expires_at = datetime.now(UTC) + timedelta(days=30)
        test_user.subscription_expires_at = expires_at
        db_session.commit()

        status = SubscriptionService.get_subscription_status(db_session, test_user)
        assert status.tier == "premium"
        assert status.status == "active"
        assert status.limits["cars"] is None
        assert status.limits["build_lists"] is None
        # Handle timezone-aware vs timezone-naive comparison
        if status.expires_at.tzinfo is None and expires_at.tzinfo is not None:
            # Database returned timezone-naive, compare by converting to naive
            assert status.expires_at == expires_at.replace(tzinfo=None)
        elif status.expires_at.tzinfo is not None and expires_at.tzinfo is None:
            # Database returned timezone-aware, compare by converting to aware
            assert status.expires_at.replace(tzinfo=None) == expires_at
        else:
            assert status.expires_at == expires_at

    def test_upgrade_to_premium(self, db_session: Session, test_user: User) -> None:
        """Test upgrading user to premium subscription."""
        # Initially free tier
        test_user.subscription_tier = "free"
        test_user.subscription_status = "active"
        db_session.commit()

        # Upgrade to premium
        expires_at = datetime.now(UTC) + timedelta(days=30)
        updated_user = SubscriptionService.upgrade_to_premium(db_session, test_user, expires_at)

        assert updated_user.subscription_tier == "premium"
        assert updated_user.subscription_status == "active"
        # Handle timezone-aware vs timezone-naive comparison
        if updated_user.subscription_expires_at.tzinfo is None and expires_at.tzinfo is not None:
            assert updated_user.subscription_expires_at == expires_at.replace(tzinfo=None)
        elif updated_user.subscription_expires_at.tzinfo is not None and expires_at.tzinfo is None:
            assert updated_user.subscription_expires_at.replace(tzinfo=None) == expires_at
        else:
            assert updated_user.subscription_expires_at == expires_at

        # Check subscription record was created
        subscription = (
            db_session.query(Subscription)
            .filter(Subscription.user_id == test_user.id, Subscription.status == "active")
            .first()
        )
        assert subscription is not None
        assert subscription.tier == "premium"

    def test_upgrade_to_premium_default_expiration(self, db_session: Session, test_user: User) -> None:
        """Test upgrading user to premium with default expiration."""
        # Initially free tier
        test_user.subscription_tier = "free"
        test_user.subscription_status = "active"
        db_session.commit()

        # Upgrade to premium without specifying expiration
        updated_user = SubscriptionService.upgrade_to_premium(db_session, test_user)

        assert updated_user.subscription_tier == "premium"
        assert updated_user.subscription_status == "active"
        assert updated_user.subscription_expires_at is not None
        # Should be approximately 30 days from now (allow some tolerance)
        expected_expires = datetime.now(UTC) + timedelta(days=30)
        # Handle timezone-aware vs timezone-naive comparison
        if updated_user.subscription_expires_at.tzinfo is None:
            # Database returned timezone-naive, convert expected to naive for comparison
            expected_expires_naive = expected_expires.replace(tzinfo=None)
            time_diff = abs((updated_user.subscription_expires_at - expected_expires_naive).total_seconds())
        else:
            # Database returned timezone-aware
            time_diff = abs((updated_user.subscription_expires_at - expected_expires).total_seconds())
        assert time_diff < 60  # Within 1 minute

    def test_cancel_subscription(self, db_session: Session, test_user: User) -> None:
        """Test canceling user's premium subscription."""
        # Set user to premium
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "active"
        expires_at = datetime.now(UTC) + timedelta(days=30)
        test_user.subscription_expires_at = expires_at
        db_session.commit()

        # Create subscription record
        subscription = Subscription(
            user_id=test_user.id,
            tier="premium",
            status="active",
            expires_at=expires_at,
        )
        db_session.add(subscription)
        db_session.commit()

        # Cancel subscription
        updated_user = SubscriptionService.cancel_subscription(db_session, test_user)

        assert updated_user.subscription_status == "cancelled"

        # Check subscription record was updated
        db_session.refresh(subscription)
        assert subscription.status == "cancelled"

    def test_check_expired_subscriptions(self, db_session: Session, test_user: User) -> None:
        """Test checking and updating expired subscriptions."""
        # Set user to premium with expired date
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "active"
        test_user.subscription_expires_at = datetime.now(UTC) - timedelta(days=1)  # Expired
        db_session.commit()

        # Check expired subscriptions
        SubscriptionService.check_expired_subscriptions(db_session)

        # Refresh user
        db_session.refresh(test_user)
        assert test_user.subscription_status == "expired"
        assert test_user.subscription_tier == "free"

    def test_check_expired_subscriptions_not_expired(self, db_session: Session, test_user: User) -> None:
        """Test checking subscriptions that are not expired."""
        # Set user to premium with future expiration
        test_user.subscription_tier = "premium"
        test_user.subscription_status = "active"
        test_user.subscription_expires_at = datetime.now(UTC) + timedelta(days=30)  # Not expired
        db_session.commit()

        # Check expired subscriptions
        SubscriptionService.check_expired_subscriptions(db_session)

        # Refresh user
        db_session.refresh(test_user)
        assert test_user.subscription_status == "active"
        assert test_user.subscription_tier == "premium"
