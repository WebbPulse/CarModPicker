import os
import uuid
from typing import Any, Dict, Generator, Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variables BEFORE importing any app code
# so storage service, rate limiter, etc. detect the test environment at import time.
os.environ["TESTING"] = "true"
os.environ["ENABLE_RATE_LIMITING"] = "false"

INVALID_UUID: UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")
INVALID_UUID_STR: str = str(INVALID_UUID)

# Imports deferred until after env setup.
from app.api.dependencies.auth import get_password_hash  # noqa: E402
from app.api.models.category import Category  # noqa: E402
from app.api.models.part_manufacturer import PartManufacturer  # noqa: E402
from app.api.models.user import User  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    """
    One SQLite in-memory engine per xdist worker, shared across every test in that
    worker. Tables are created once; per-test isolation is achieved via nested
    transactions (SAVEPOINTs) in db_session, not by tearing down the engine.
    """
    eng = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # SQLite defaults to autocommit-ish behavior that breaks SAVEPOINT nesting.
    # This disables pysqlite's implicit BEGIN so SQLAlchemy fully controls transactions.
    @event.listens_for(eng, "connect")
    def _disable_pysqlite_autobegin(dbapi_connection, _):  # type: ignore[no-untyped-def]
        dbapi_connection.isolation_level = None

    @event.listens_for(eng, "begin")
    def _emit_begin(conn):  # type: ignore[no-untyped-def]
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(bind=eng)

    yield eng

    eng.dispose()


@pytest.fixture(scope="function")
def db_session(engine: Engine) -> Generator[Session, None, None]:
    """
    Per-test session wrapped in an outer transaction that always rolls back.
    `join_transaction_mode="create_savepoint"` lets test code call session.commit()
    without ending the outer transaction — commits become SAVEPOINT releases.
    """
    connection = engine.connect()
    transaction = connection.begin()

    SessionLocal = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    TestClient bound to the current test's db_session.

    Intentionally NOT used as a context manager — that would trigger app lifespan,
    which runs init_car_generations() (6500+ rows) and crawler/service-account seeding
    on every test. Tests that need that seed data must invoke the init functions
    explicitly (see test_init_cars_display_name.py for the pattern).
    """

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass  # session lifecycle is owned by the db_session fixture

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(fastapi_app)
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    """Create a test user for testing."""
    user = User(
        username=f"test_user_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        email=f"test_user_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=False,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def premium_test_user(db_session: Session) -> User:
    """Create a test user with premium subscription (unlimited build lists)."""
    user = User(
        username=f"premium_user_{os.getpid()}_{id(db_session)}",
        email=f"premium_user_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=False,
        is_superuser=False,
        subscription_tier="premium",
        subscription_status="active",
        subscription_expires_at=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_category(db_session: Session) -> Category:
    """Create a test category for testing."""
    category = Category(
        name=f"test_category_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        display_name=f"Test Category {os.getpid()}_{id(db_session)}",
        description="A test category",
        is_active=True,
        sort_order=1,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture(scope="function")
def test_part_manufacturer(db_session: Session) -> PartManufacturer:
    """Create a test part_manufacturer for testing."""
    part_manufacturer = PartManufacturer(
        name=f"test_part_manufacturer_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        description="A test part_manufacturer",
        is_active=True,
    )
    db_session.add(part_manufacturer)
    db_session.commit()
    db_session.refresh(part_manufacturer)
    return part_manufacturer


@pytest.fixture(scope="function")
def test_admin_user(db_session: Session) -> User:
    """Create an admin user for testing."""
    user = User(
        username=f"admin_user_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        email=f"admin_user_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_superuser_user(db_session: Session) -> User:
    """Create a superuser for testing."""
    user = User(
        username=f"superuser_{os.getpid()}_{id(db_session)}",  # Make unique per worker
        email=f"superuser_{os.getpid()}_{id(db_session)}@example.com",
        hashed_password=get_password_hash("testpassword"),
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# Test utilities
def get_default_category_id(db_session: Session) -> UUID:
    """Get the ID of the 'other' category for testing."""
    category = db_session.query(Category).filter(Category.name == "other").first()
    if not category:
        # Create the 'other' category if it doesn't exist
        category = Category(
            name="other",
            display_name="Other",
            description="Miscellaneous parts",
            is_active=True,
            sort_order=999,
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)
    return category.id


def login_user(client: TestClient, username: str, password: str = "testpassword") -> str:
    """Login a user and return the Bearer token for use in Authorization headers."""
    from app.core.config import settings

    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200
    response_data = response.json()
    assert "access_token" in response_data
    return response_data["access_token"]


def create_and_login_user(
    client: TestClient,
    username: str,
    password_override: str = "testpassword",
    db_session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Create a user and log them in, returning the user info."""
    from app.core.config import settings

    # Create user
    user_data = {
        "username": username,
        "email": f"{username}@example.com",
        "password": password_override,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert response.status_code == 200
    user_data_response: Dict[str, Any] = response.json()
    assert isinstance(user_data_response, dict)

    # Manually verify the email for testing purposes
    from app.api.models.user import User

    # Use the provided database session or get one from the test client
    if db_session is None:
        from app.db.session import get_db

        db = next(get_db())
        try:
            user = db.query(User).filter(User.username == username).first()
            if user:
                user.email_verified = True
                db.commit()
        finally:
            db.close()
    else:
        # Use the provided session
        user = db_session.query(User).filter(User.username == username).first()
        if user:
            user.email_verified = True
            db_session.commit()

    # Login (token is returned but not stored - tests should use it explicitly)
    login_user(client, username, password_override)

    return user_data_response


def create_car_for_user_cookie_auth(client: TestClient) -> UUID:
    """DEPRECATED: Create a car for the currently logged-in user.

    This function is deprecated since cars are now centrally managed by admins.
    Use create_car_in_db() for test setup instead.
    """
    import warnings

    warnings.warn(
        "create_car_for_user_cookie_auth is deprecated. Cars are now centrally managed. "
        "Use create_car_in_db(db_session, ...) for test setup instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    raise NotImplementedError(
        "create_car_for_user_cookie_auth is deprecated. Cars are now centrally managed. "
        "Use create_car_in_db(db_session, ...) for test setup instead."
    )


def create_car_in_db(
    db: Session,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: int = 2021,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a car directly in the database for test setup. Cars are seeded from
    backend source code in production; this helper is for tests that need a specific car.
    Creates CarMake and CarModel if needed, then CarGeneration.
    Returns a dict with id, make, model, generation_name, start_year, end_year (API shape).
    """
    from app.api.models.car_generation import CarGeneration
    from app.api.models.car_make import CarMake
    from app.api.models.car_model import CarModel

    make_entity = db.query(CarMake).filter(CarMake.name == make).first()
    if make_entity is None:
        make_entity = CarMake(name=make)
        db.add(make_entity)
        db.flush()

    car_model_entity = db.query(CarModel).filter(CarModel.car_make_id == make_entity.id, CarModel.name == model).first()
    if car_model_entity is None:
        car_model_entity = CarModel(car_make_id=make_entity.id, name=model)
        db.add(car_model_entity)
        db.flush()

    car = CarGeneration(
        car_model_id=car_model_entity.id,
        generation_name=generation_name,
        start_year=start_year,
        end_year=end_year,
        description=description,
    )
    db.add(car)
    db.commit()
    db.refresh(car)
    return {
        "id": car.id,
        "make": make,
        "model": model,
        "generation_name": car.generation_name,
        "start_year": car.start_year,
        "end_year": car.end_year,
        "description": car.description,
        "created_at": car.created_at.isoformat() if car.created_at else None,
        "updated_at": car.updated_at.isoformat() if car.updated_at else None,
    }


def create_car_orm_in_db(
    db: Session,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: int = 2021,
    description: Optional[str] = None,
):
    """Create a car in the DB and return the CarGeneration ORM instance (with relationships loaded).
    Use when tests need the CarGeneration object (e.g. car.car_make_name, car.id) rather than the API dict.
    """
    from sqlalchemy.orm import joinedload

    from app.api.models.car_generation import CarGeneration
    from app.api.models.car_make import CarMake
    from app.api.models.car_model import CarModel

    make_entity = db.query(CarMake).filter(CarMake.name == make).first()
    if make_entity is None:
        make_entity = CarMake(name=make)
        db.add(make_entity)
        db.flush()

    car_model_entity = db.query(CarModel).filter(CarModel.car_make_id == make_entity.id, CarModel.name == model).first()
    if car_model_entity is None:
        car_model_entity = CarModel(car_make_id=make_entity.id, name=model)
        db.add(car_model_entity)
        db.flush()

    car = CarGeneration(
        car_model_id=car_model_entity.id,
        generation_name=generation_name,
        start_year=start_year,
        end_year=end_year,
        description=description,
    )
    db.add(car)
    db.commit()
    db.refresh(car)
    # Reload with relationships so car.car_make_name / car.car_model_name work
    car = (
        db.query(CarGeneration)
        .options(joinedload(CarGeneration.car_model).joinedload(CarModel.car_make))
        .filter(CarGeneration.id == car.id)
        .first()
    )
    return car


@pytest.fixture
def mock_s3(monkeypatch: pytest.MonkeyPatch) -> Generator[Dict[str, Any], None, None]:
    """
    Fake in-memory S3 using moto.

    Patches both the StorageService singleton (USER_IMAGES_BUCKET) and the lazy
    crawl client globals (CRAWL_BUCKET) so tests can write to and read from S3
    without touching any real cloud service or running MinIO.

    Yields a dict with keys:
      client            — moto boto3 S3 client (for assertions)
      user_images_bucket — "test-user-images"
      crawl_bucket       — "test-crawl-data"
    """
    from moto import mock_aws

    with mock_aws():
        import boto3

        import app.api.services.storage_service as ss_module
        import app.crawlers.base as base_module
        from app.core.config import settings as app_settings

        # Single moto client shared by both buckets
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-user-images")
        s3.create_bucket(Bucket="test-crawl-data")

        # Patch settings so any path that reads settings.* gets test values
        monkeypatch.setattr(app_settings, "USER_IMAGES_BUCKET", "test-user-images")
        monkeypatch.setattr(app_settings, "CRAWL_BUCKET", "test-crawl-data")

        # Inject moto client directly into StorageService singleton.
        # (The singleton was initialized with s3_client=None because _is_test_environment()
        # returned True at module load.  We bypass re-init by patching the attributes.)
        monkeypatch.setattr(ss_module.storage_service, "s3_client", s3)
        monkeypatch.setattr(ss_module.storage_service, "s3_client_presigner", s3)
        monkeypatch.setattr(ss_module.storage_service, "bucket_name", "test-user-images")

        # Inject moto client directly into the lazy crawl client globals.
        # get_crawl_s3_client() sees non-None values and returns them immediately,
        # so no new boto3.client() call is made (endpoint_url irrelevant).
        monkeypatch.setattr(base_module, "_crawl_s3_client", s3)
        monkeypatch.setattr(base_module, "_crawl_bucket_name", "test-crawl-data")

        yield {
            "client": s3,
            "user_images_bucket": "test-user-images",
            "crawl_bucket": "test-crawl-data",
        }


# -----------------------------------------------------------------------
# SAFE-06: pytest-recording (vcrpy) configuration for auth characterization
# tests. Scrubs headers, post-body, and query-params that might carry
# production secrets. record_mode="none" means CI replays only — to record
# a new cassette locally, run pytest with `--record-mode=once`.
# -----------------------------------------------------------------------


@pytest.fixture(scope="module")
def vcr_config() -> dict:
    """VCR configuration consumed by pytest-recording's @pytest.mark.vcr."""
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("cookie", "REDACTED"),
            ("set-cookie", "REDACTED"),
            ("x-goog-api-key", "REDACTED"),
        ],
        "filter_post_data_parameters": [
            ("client_secret", "REDACTED"),
            ("code", "REDACTED"),
            ("refresh_token", "REDACTED"),
        ],
        "filter_query_parameters": [
            ("api_key", "REDACTED"),
            ("access_token", "REDACTED"),
        ],
        "record_mode": "none",
        "match_on": ("method", "scheme", "host", "port", "path", "query"),
    }


def create_and_login_admin_user(client: TestClient, username: str) -> User:
    """Create an admin user and log them in."""
    from app.core.config import settings

    # Create admin user
    user_data = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "testpassword",
    }
    response = client.post(f"{settings.API_STR}/auth/register", json=user_data)
    assert response.status_code == 200
    admin_user_data: Dict[str, Any] = response.json()
    assert isinstance(admin_user_data, dict)

    # Login
    login_user(client, username)

    # Return a mock User object since we can't easily construct one from the response
    # This is a test utility function, so this is acceptable
    from app.api.models.user import User

    user_id: UUID = UUID(admin_user_data["id"])
    user_name: str = admin_user_data.get("username", "")
    user_email: str = admin_user_data.get("email", "")

    return User(
        id=user_id,
        username=user_name,
        email=user_email,
        hashed_password="",
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=False,
    )
