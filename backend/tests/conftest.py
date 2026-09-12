"""Shared pytest fixtures and helpers for the backend test suite."""

import os
import uuid
from typing import Any, Dict, Generator, Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from webbpulse.log_context import UNSET, request_id_var, user_id_var

os.environ["TESTING"] = "true"
os.environ["ENABLE_RATE_LIMITING"] = "false"

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-a-real-one")

INVALID_UUID: UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")
INVALID_UUID_STR: str = str(INVALID_UUID)

from app.api.schemas.car_generation import CarGenerationRead  # noqa: E402
from app.api.services.car_generation_service import CarGenerationService  # noqa: E402
from app.db.dynamo.catalog import (  # noqa: E402
    CarGeneration,
    CarGenerationRepository,
    CarMake,
    CarMakeRepository,
    CarModel,
    CarModelRepository,
    Category,
    CategoryRepository,
    Part,
    PartCar,
    PartCarRepository,
    PartListing,
    PartListingRepository,
    PartManufacturer,
    PartManufacturerRepository,
    PartPriceHistory,
    PartPriceHistoryRepository,
    PartRepository,
    Retailer,
    RetailerRepository,
)
from app.db.dynamo.users import User, UserRepository  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


class TestDatabase:
    """A per-test marker handed to tests as db_session, now that every table is in DynamoDB.

    The name survives because tests use it to order fixtures and derive unique names.
    """


@pytest.fixture(scope="function")
def db_session(dynamo_tables: Any) -> TestDatabase:
    """Yield the per-test marker tests accept as db_session."""
    return TestDatabase()


@pytest.fixture
def client(db_session: TestDatabase, dynamo_tables: Any) -> Generator[TestClient, None, None]:
    """A test client over the current test's mocked DynamoDB tables.

    Not a context manager on purpose: lifespan would seed thousands of car rows per test.
    """
    yield TestClient(fastapi_app)


@pytest.fixture(scope="function")
def test_user(db_session: TestDatabase, dynamo_tables: Any) -> User:
    """Create a test user for testing."""
    user = User(
        username=f"test_user_{os.getpid()}_{id(db_session)}",
        email=f"test_user_{os.getpid()}_{id(db_session)}@example.com",
        email_verified=True,
        disabled=False,
        is_admin=False,
        is_superuser=False,
    )
    return UserRepository().create_user(user)


@pytest.fixture(scope="function")
def premium_test_user(db_session: TestDatabase, dynamo_tables: Any) -> User:
    """Create a test user with premium subscription (unlimited build lists)."""
    user = User(
        username=f"premium_user_{os.getpid()}_{id(db_session)}",
        email=f"premium_user_{os.getpid()}_{id(db_session)}@example.com",
        email_verified=True,
        disabled=False,
        is_admin=False,
        is_superuser=False,
        subscription_tier="premium",
        subscription_status="active",
        subscription_expires_at=None,
    )
    return UserRepository().create_user(user)


@pytest.fixture(scope="function")
def test_category(db_session: TestDatabase, dynamo_tables: Any) -> Category:
    """Create a test category for testing."""
    category = Category(
        name=f"test_category_{os.getpid()}_{id(db_session)}",
        display_name=f"Test Category {os.getpid()}_{id(db_session)}",
        description="A test category",
        is_active=True,
        sort_order=1,
    )
    return CategoryRepository().create_unique(category)


@pytest.fixture(scope="function")
def test_part_manufacturer(db_session: TestDatabase, dynamo_tables: Any) -> PartManufacturer:
    """Create a test part_manufacturer for testing."""
    part_manufacturer = PartManufacturer(
        name=f"test_part_manufacturer_{os.getpid()}_{id(db_session)}",
        description="A test part_manufacturer",
        is_active=True,
    )
    return PartManufacturerRepository().create_unique(part_manufacturer)


@pytest.fixture(scope="function")
def test_admin_user(db_session: TestDatabase, dynamo_tables: Any) -> User:
    """Create an admin user for testing."""
    user = User(
        username=f"admin_user_{os.getpid()}_{id(db_session)}",
        email=f"admin_user_{os.getpid()}_{id(db_session)}@example.com",
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=False,
    )
    return UserRepository().create_user(user)


@pytest.fixture(scope="function")
def test_superuser_user(db_session: TestDatabase, dynamo_tables: Any) -> User:
    """Create a superuser for testing."""
    user = User(
        username=f"superuser_{os.getpid()}_{id(db_session)}",
        email=f"superuser_{os.getpid()}_{id(db_session)}@example.com",
        email_verified=True,
        disabled=False,
        is_admin=True,
        is_superuser=True,
    )
    return UserRepository().create_user(user)


_CATALOG_REPOSITORIES: Dict[type, type] = {
    CarMake: CarMakeRepository,
    CarModel: CarModelRepository,
    CarGeneration: CarGenerationRepository,
    Category: CategoryRepository,
    PartManufacturer: PartManufacturerRepository,
    Retailer: RetailerRepository,
    Part: PartRepository,
    PartCar: PartCarRepository,
    PartListing: PartListingRepository,
    PartPriceHistory: PartPriceHistoryRepository,
}


def catalog_repository(model: type) -> Any:
    """Return the repository class registered for a catalog model."""
    return _CATALOG_REPOSITORIES[model]()


def save_catalog(entity: Any, car_ids: Optional[list[UUID]] = None) -> Any:
    """Persist a catalog model through its repository and return the stored copy."""
    repository = catalog_repository(type(entity))
    if isinstance(entity, Part):
        linked = list(car_ids if car_ids is not None else entity.car_ids)
        entity = entity.model_copy(update={"car_ids": linked})
        actions = [PartCarRepository().link_action(entity.id, car_id) for car_id in linked]
        return repository.create_unique(entity, extra_actions=actions)
    if hasattr(repository, "create_unique"):
        return repository.create_unique(entity)
    return repository.create(entity)


def get_default_category_id(db_session: TestDatabase) -> UUID:
    """Get the ID of the 'other' category for testing."""
    categories = CategoryRepository()
    category = categories.get_by_name("other")
    if not category:
        category = categories.create_unique(
            Category(
                name="other",
                display_name="Other",
                description="Miscellaneous parts",
                is_active=True,
                sort_order=999,
            )
        )
    return category.id


def identity_context(subject: str) -> str:
    """The `x-amzn-request-context` header an authorizer produces for `subject`.

    Row 13 of `docs/identity-adoption.md` deleted `POST /api/auth/token`, which
    is what this suite used to call to get a credential. There is no in-process
    replacement for it: the package's login is mounted only where the
    `IDENTITY_*` settings and a KMS signing key exist, and verifying an RS256
    token in process needs `kms:GetPublicKey`, neither of which a unit test has.

    So the suite authenticates the way production actually delivers a verified
    credential to this application: as claims an authorizer already checked,
    flattened into the request context. That is the native shape,
    `authorizer.jwt.claims`, and `app/api/dependencies/identity_claims.py` reads
    it through the package's own reader. Every value is a string, `exp`
    included, because that is what API Gateway puts there; see the fixture note
    in `tests/test_identity_row11.py`, which this mirrors deliberately rather
    than duplicating a second shape of the same header.
    """
    import json

    claims = {
        "sub": subject,
        "iss": "https://api.carmodpicker.test/api/auth",
        "aud": "carmodpicker-test-api",
        "typ": "access",
        "iat": "1788938046",
        "exp": "1788938646",
        "jti": "976037a1ea4847da8a633b3338d61f65",
        "username": "test",
        "roles": "[]",
    }
    return json.dumps({"authorizer": {"jwt": {"claims": claims}}})


def auth_headers_for(user_id: Any) -> Dict[str, str]:
    """Request headers that authenticate as `user_id`.

    The one place the suite builds a credential. `REQUEST_CONTEXT_HEADER` is the
    header the Lambda Web Adapter sets from the invoke event, and an inbound
    header of that name never reaches it in a deployment, which is why carrying
    it here is a test harness rather than a hole: `TestClient` is the adapter's
    position in this process.
    """
    from webbpulse.http import REQUEST_CONTEXT_HEADER

    return {REQUEST_CONTEXT_HEADER: identity_context(str(user_id))}


def auth_headers(credential: str) -> Dict[str, str]:
    """Turn a credential from `login_user` into request headers.

    The counterpart to `login_user`, and the replacement for the
    `{"Authorization": f"Bearer {token}"}` literal that used to appear at every
    call site. Written as a function taking the credential rather than the user,
    so that a test which already holds one from `login_user` does not have to
    reach back for the user row.
    """
    from webbpulse.http import REQUEST_CONTEXT_HEADER

    return {REQUEST_CONTEXT_HEADER: credential}


def login_user(client: TestClient, username: str, password: str = "testpassword") -> str:
    """The credential for `username`, as the value tests put in a header.

    Kept under its old name and old signature so the several hundred call sites
    that say `login_user(client, user.username)` did not all have to change in
    the row that deleted the legacy login route. What it returns is no longer a
    bearer token: it is the `x-amzn-request-context` value for that user, and
    `auth_headers` below is what turns it into headers. `password` is accepted
    and ignored, because an identity credential is not minted from one here.
    """
    user = UserRepository().get_by_username(username)
    assert user is not None, f"No such user to authenticate: {username}"
    return identity_context(str(user.id))


def create_and_login_user(
    client: TestClient,
    username: str,
    password_override: str = "testpassword",
) -> Dict[str, Any]:
    """Create a user row and return it in the shape `UserRead` serialises to.

    A direct repository write since the users domain follow up deleted
    `POST /api/users/`: registration is the identity package's route now, and it
    mints a credential this harness has no use for. `password_override` is
    accepted and ignored for the same reason `login_user` ignores its password.
    """
    del password_override

    user = UserRepository().create_user(
        User(
            username=username,
            email=f"{username}@example.com",
            email_verified=True,
        )
    )
    login_user(client, username)

    return user.model_dump(mode="json")


def create_car_for_user_cookie_auth(client: TestClient) -> UUID:
    """Deprecated. Create a car for the logged-in user; prefer create_car_in_db."""
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


def _create_car_generation(
    make: str,
    model: str,
    generation_name: str,
    start_year: int,
    end_year: Optional[int],
    description: Optional[str],
) -> CarGeneration:
    """Create the make, model and generation rows for one car, reusing any that exist."""
    makes = CarMakeRepository()
    models = CarModelRepository()
    generations = CarGenerationRepository()

    make_entity = makes.get_by_name(make)
    if make_entity is None:
        make_entity = makes.create_unique(CarMake(name=make))

    car_model_entity = models.get_by_make_and_name(make_entity.id, model)
    if car_model_entity is None:
        car_model_entity = models.create_unique(CarModel(car_make_id=make_entity.id, name=model))

    return generations.create_unique(
        CarGeneration(
            car_model_id=car_model_entity.id,
            generation_name=generation_name,
            start_year=start_year,
            end_year=end_year,
            description=description,
        )
    )


def create_car_in_db(
    db: Any,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: Optional[int] = 2021,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a car directly and return it in the API shape, for tests needing a specific car."""
    car = _create_car_generation(make, model, generation_name, start_year, end_year, description)
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
    db: Any,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: Optional[int] = 2021,
    description: Optional[str] = None,
) -> CarGenerationRead:
    """Create a car and return its hydrated read model (car_make_name, car_model_name, id, ...).
    Use when tests need the car object rather than the API dict.
    """
    car = _create_car_generation(make, model, generation_name, start_year, end_year, description)
    return CarGenerationService().hydrate_one(car)


@pytest.fixture
def caplog_with_context(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """caplog with the log context filter installed, so records carry request and user ids.

    pytest's own handler does not inherit the root filter, so it is added here.
    """
    from webbpulse.log_context import LogContextFilter

    caplog.handler.addFilter(LogContextFilter())
    return caplog


from sentry_sdk.transport import Transport as _SentryTransport  # noqa: E402


class _CapturingTransport(_SentryTransport):
    """An in-memory Sentry transport collecting envelopes in a shared class level list."""

    events: list = []

    def __init__(self, options=None):
        """Accept whatever options the SDK passes and keep the shared list."""
        super().__init__(options)
        self.__class__.events = []

    def capture_envelope(self, envelope) -> None:
        """Record one envelope."""
        self.__class__.events.append(envelope)

    def flush(self, timeout=None, callback=None) -> None:
        """Flushing is a no-op for the in-memory transport."""
        pass

    def kill(self) -> None:
        """Killing is a no-op for the in-memory transport."""
        pass


@pytest.fixture
def sentry_events(monkeypatch: pytest.MonkeyPatch):
    """Yield the list Sentry envelopes are appended to, closing the client on teardown."""
    import sentry_sdk

    monkeypatch.setenv("TESTING", "")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_DSN", "http://key@localhost/1")

    sentry_sdk.init(
        dsn="http://key@localhost/1",
        transport=_CapturingTransport,
        before_send=lambda ev, h: ev,
    )
    try:
        yield _CapturingTransport.events
    finally:
        client = sentry_sdk.get_client()
        if client is not None:
            client.close()


@pytest.fixture
def mock_s3(monkeypatch: pytest.MonkeyPatch) -> Generator[Dict[str, Any], None, None]:
    """An in-memory S3 through moto, with the storage service pointed at it."""
    from moto import mock_aws

    with mock_aws():
        import boto3

        import app.api.services.storage_service as ss_module
        from app.core.config import settings as app_settings

        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-user-images")

        monkeypatch.setattr(app_settings, "USER_IMAGES_BUCKET", "test-user-images")

        monkeypatch.setattr(ss_module.storage_service, "s3_client", s3)
        monkeypatch.setattr(ss_module.storage_service, "s3_client_presigner", s3)
        monkeypatch.setattr(ss_module.storage_service, "bucket_name", "test-user-images")

        yield {
            "client": s3,
            "user_images_bucket": "test-user-images",
        }


@pytest.fixture(autouse=True)
def _isolate_log_context() -> Generator[None, None, None]:
    """Reset the request and user id context variables to UNSET after every test.

    `resolve_identity_user` and the other production setters bind these for the
    life of their own request context and do not reset them, which is correct in
    a server but leaks into the next test when a test calls them directly.
    """
    yield
    request_id_var.set(UNSET)
    user_id_var.set(UNSET)


@pytest.fixture(autouse=True)
def _isolate_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set fake AWS credentials and drop any profile, so no test reaches a real account."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)


@pytest.fixture
def dynamo_tables(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    """Create every DynamoDB table under moto for one test and reset the clients around it."""
    from moto import mock_aws

    from app.core.config import settings as app_settings
    from app.db.dynamo import client as dynamo_client
    from app.db.dynamo.tables import TABLES

    monkeypatch.setattr(app_settings, "AWS_REGION", "us-east-1")
    monkeypatch.setattr(app_settings, "DYNAMODB_TABLE_PREFIX", "test")
    monkeypatch.setattr(app_settings, "DYNAMODB_ENDPOINT_URL", "")

    with mock_aws():
        dynamo_client.reset_clients()
        resource = dynamo_client.get_resource()
        for spec in TABLES:
            resource.create_table(**spec.create_table_request(dynamo_client.table_name(spec)))
        try:
            yield resource
        finally:
            dynamo_client.reset_clients()


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

    user_data = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "testpassword",
    }
    response = client.post(f"{settings.API_STR}/auth/register", json=user_data)
    assert response.status_code == 200
    admin_user_data: Dict[str, Any] = response.json()
    assert isinstance(admin_user_data, dict)

    login_user(client, username)

    return UserRepository().get_or_raise(UUID(admin_user_data["id"]))
