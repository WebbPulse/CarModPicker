import os
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Optional
from urllib.parse import urlparse, urlunparse
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
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
    def _disable_pysqlite_autobegin(dbapi_connection: Any, _: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(eng, "begin")
    def _emit_begin(conn: Any) -> None:
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


_SELECT_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)


@dataclass
class QueryCounter:
    """DATA-02 — counts SELECT statements inside a query_counter() context block.

    Filters to SELECT only so that BEGIN / COMMIT / SAVEPOINT / RELEASE noise
    from the SAVEPOINT-per-test fixture does not pollute the count.
    """

    count: int = 0
    statements: list[str] = field(default_factory=list)

    def record(self, statement: str) -> None:
        if _SELECT_PATTERN.match(statement):
            self.count += 1
            self.statements.append(statement)


@pytest.fixture
def query_counter(engine: Engine):
    """Return a context manager that counts SELECT statements emitted by `engine`.

    Usage:
        def test_something(client, query_counter):
            with query_counter() as counter:
                client.get(...)
            assert counter.count == 2

    Pitfall 3: event.remove MUST fire in the finally block; otherwise listeners
    leak across tests and every subsequent counter observes prior queries.
    """

    @contextmanager
    def _ctx():
        counter = QueryCounter()

        def _before(conn, cursor, statement, parameters, context, executemany):
            counter.record(statement)

        event.listen(engine, "before_cursor_execute", _before)
        try:
            yield counter
        finally:
            event.remove(engine, "before_cursor_execute", _before)

    return _ctx


def _postgres_url_for_worker() -> Optional[str]:
    """DATA-04 D-02: derive a per-worker Postgres URL from POSTGRES_TEST_URL.

    pytest-xdist sets PYTEST_XDIST_WORKER=gw0, gw1, ... We suffix the database
    name so that workers do not collide (Pitfall 8). Returns None when
    POSTGRES_TEST_URL is unset — fixture will pytest.skip().
    """
    base = os.environ.get("POSTGRES_TEST_URL")
    if not base:
        return None
    worker = os.environ.get("PYTEST_XDIST_WORKER", "master")
    parsed = urlparse(base)
    new_path = f"{parsed.path.rstrip('/')}_{worker}"
    return urlunparse(parsed._replace(path=new_path))


@pytest.fixture(scope="session")
def postgres_engine():
    """Session-scoped Postgres engine for @pytest.mark.postgres tests.

    CONTRACT (WARN 8): Tests using this fixture MUST filter their queries by a
    per-test unique key (e.g., ``shared_gtin = f"G{worker}{uuid.uuid4().hex[:12]}"``)
    and MUST NOT scan full tables. Cross-test data pollution is NOT cleaned up
    between tests within the session-scoped engine; isolation comes from the
    per-test unique key.

    Skips cleanly when POSTGRES_TEST_URL is unset — matches the default
    local-dev contract of SQLite-only tests.
    """
    url = _postgres_url_for_worker()
    if not url:
        pytest.skip("POSTGRES_TEST_URL not set; skipping postgres-backed tests")
    from app.db.base import Base

    eng = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture
def postgres_session(postgres_engine):
    """Function-scoped Postgres session with BEGIN + ROLLBACK per test (WARN 8 alternative).

    Use when your test cannot structure its seed around a per-test unique key.
    Slower but fully isolated across tests.

    WARNING: Transaction-rollback isolation defeats pessimistic-lock semantics —
    the concurrency tests (test_part_linker_concurrency.py) MUST use
    ``postgres_engine`` directly with per-worker/per-test unique keys, NOT this
    fixture. ROLLBACK would undo the very lock acquisition this plan is
    validating.
    """
    SessionLocal = sessionmaker(bind=postgres_engine, autocommit=False, autoflush=False)
    conn = postgres_engine.connect()
    trans = conn.begin()
    session = SessionLocal(bind=conn)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


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
    category = db_session.scalars(select(Category).where(Category.name == "other")).first()
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

    # IN-11: POST /api/users/ already auto-verifies email_verified=True when
    # TESTING=true (see endpoints/users.py::register_user), which conftest sets
    # at import time before any app code loads. The manual flip block that used
    # to live here was a no-op — it flipped True to True and happened to be two
    # of the legacy db.query() calls that Phase 4 WR-01 flagged as residue.
    # (The remaining 6 conftest helpers were migrated in Phase 07 plan 07-03 —
    # zero legacy .query() calls remain in this file.)

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

    make_entity = db.scalars(select(CarMake).where(CarMake.name == make)).first()
    if make_entity is None:
        make_entity = CarMake(name=make)
        db.add(make_entity)
        db.flush()

    car_model_entity = db.scalars(
        select(CarModel).where(
            CarModel.car_make_id == make_entity.id,
            CarModel.name == model,
        )
    ).first()
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

    make_entity = db.scalars(select(CarMake).where(CarMake.name == make)).first()
    if make_entity is None:
        make_entity = CarMake(name=make)
        db.add(make_entity)
        db.flush()

    car_model_entity = db.scalars(
        select(CarModel).where(
            CarModel.car_make_id == make_entity.id,
            CarModel.name == model,
        )
    ).first()
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
    car = db.scalars(
        select(CarGeneration)
        .options(joinedload(CarGeneration.car_model).joinedload(CarModel.car_make))
        .where(CarGeneration.id == car.id)
    ).first()
    return car


@pytest.fixture
def caplog_with_context(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """caplog fixture augmented with RequestContextFilter on the handler so
    LogRecords carry request_id + user_id attrs.

    Landmine (02-RESEARCH.md §3 + §Landmine 15): pytest's caplog attaches its
    own handler at the root logger but does NOT inherit root-logger filters
    installed in app/main.py — without this augmentation, record.request_id
    raises AttributeError despite the filter working fine in production.
    """
    from app.core.log_context import RequestContextFilter

    caplog.handler.addFilter(RequestContextFilter())
    return caplog


# Sentry test transport — 2.x uses capture_envelope (Landmine 3).
# Defined at module scope so tests can import it via
# `from tests.conftest import _CapturingTransport`.
#
# Must subclass sentry_sdk.transport.Transport in 2.x — otherwise the SDK
# treats the class as a "function transport" (deprecated) and silently
# discards envelopes despite accepting the argument.
from sentry_sdk.transport import Transport as _SentryTransport  # noqa: E402


class _CapturingTransport(_SentryTransport):
    """In-memory Sentry transport. Sentry 2.x API: capture_envelope (NOT
    capture_event — that was 1.x). Instances share `events` via class attribute
    so fixtures can observe the list even when the transport is re-constructed
    by sentry_sdk.init.
    """

    events: list = []

    def __init__(self, options=None):
        # sentry_sdk.init passes options positionally; accept for signature compat.
        # Reset on init so each sentry_sdk.init() call starts with empty buffer.
        super().__init__(options)
        self.__class__.events = []

    def capture_envelope(self, envelope) -> None:  # 2.x entry point
        self.__class__.events.append(envelope)

    def flush(self, timeout=None, callback=None) -> None:
        pass

    def kill(self) -> None:
        pass


@pytest.fixture
def sentry_events(monkeypatch: pytest.MonkeyPatch):
    """Yield a list to which Sentry envelopes are appended. Closes the SDK
    client on teardown so tests don't leak references across runs (Landmine 16
    — Sentry init is process-global).

    Sets env so init_sentry() would be active if called, but the fixture
    itself bypasses init_sentry() and calls sentry_sdk.init() directly with
    transport=_CapturingTransport.
    """
    import sentry_sdk

    monkeypatch.setenv("TESTING", "")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_DSN", "http://key@localhost/1")

    sentry_sdk.init(
        dsn="http://key@localhost/1",
        transport=_CapturingTransport,
        before_send=lambda ev, h: ev,
        # intentionally minimal — full init invariants covered in test_sentry_init.py
    )
    try:
        yield _CapturingTransport.events
    finally:
        client = sentry_sdk.get_client()
        if client is not None:
            client.close()


@pytest.fixture
def mock_s3(monkeypatch: pytest.MonkeyPatch) -> Generator[Dict[str, Any], None, None]:
    """
    Fake in-memory S3 using moto.

    Patches the StorageService singleton (USER_IMAGES_BUCKET) so tests can write
    to and read from S3 without touching any real cloud service or running MinIO.

    Yields a dict with keys:
      client            — moto boto3 S3 client (for assertions)
      user_images_bucket — "test-user-images"
    """
    from moto import mock_aws

    with mock_aws():
        import boto3

        import app.api.services.storage_service as ss_module
        from app.core.config import settings as app_settings

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-user-images")

        # Patch settings so any path that reads settings.* gets test values
        monkeypatch.setattr(app_settings, "USER_IMAGES_BUCKET", "test-user-images")

        # Inject moto client directly into StorageService singleton.
        # (The singleton was initialized with s3_client=None because _is_test_environment()
        # returned True at module load.  We bypass re-init by patching the attributes.)
        monkeypatch.setattr(ss_module.storage_service, "s3_client", s3)
        monkeypatch.setattr(ss_module.storage_service, "s3_client_presigner", s3)
        monkeypatch.setattr(ss_module.storage_service, "bucket_name", "test-user-images")

        yield {
            "client": s3,
            "user_images_bucket": "test-user-images",
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
