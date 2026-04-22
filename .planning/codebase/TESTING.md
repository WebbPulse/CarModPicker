# Testing Patterns

**Analysis Date:** 2026-04-22

## Test Framework

**Backend (Python):**
- Framework: pytest 7+ with pytest-xdist for parallelization
- Config file: `backend/pytest.ini`
- Coverage: pytest-cov with term-missing and HTML report

**Frontend (TypeScript/React):**
- Framework: vitest 1+ with jsdom environment
- Config file: `frontend/vitest.config.ts`
- Coverage: v8 provider with text, JSON, and HTML reports
- Testing library: @testing-library/react (mocked in setup)

**Run Commands:**

Backend:
```bash
# All tests in parallel
pytest -n auto

# With coverage report
pytest -n auto --cov=app --cov-report=term-missing --cov-report=html

# Single file
pytest -n auto backend/tests/test_email.py

# Single test
pytest -n auto -k "test_send_verify_email_success"

# Watch mode (not standard for pytest, but tests can be re-run manually)
pytest -n auto path/to/test_file.py
```

Frontend:
```bash
# All tests
npm test

# Watch mode
npm test -- --watch

# Coverage
npm run test:coverage

# Single file
npm test -- src/utils/externalImageUrls.test.ts

# Single test
npm test -- -t "builds Wix thumbnail"
```

## Test File Organization

**Location:**

Backend:
- Tests live in `backend/tests/` (separate from source, not co-located)
- Pattern: `test_*.py` files at module level (not nested in `app/tests/`)
- Fixtures and utilities in `backend/tests/conftest.py`

Frontend:
- Tests can be co-located with source or in dedicated test directory
- Pattern: `*.test.ts` or `*.test.tsx` suffix
- Example: `frontend/src/utils/externalImageUrls.test.ts` (co-located with `externalImageUrls.ts`)
- Setup file: `frontend/src/test/setup.ts`

**Naming:**
- Test functions: `test_<description>` (Python), `it('<description>')` or `test('<description>')` (TypeScript)
- Test classes: `Test<Feature>` (Python)
- Test suites: `describe('<Feature>')` (TypeScript)

**Structure:**

Backend example (from `backend/tests/test_email.py`):
```python
class TestEmailService:
    """Test cases for the SES-based email service."""

    @patch("app.core.email.settings")
    @patch("app.core.email.boto3.client")
    def test_send_verify_email_success(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
        """send_verify_email returns True and calls SES send_email on success."""
        # Arrange
        mock_settings.EMAIL_ENABLED = True
        mock_ses = MagicMock()
        mock_boto_client.return_value = mock_ses

        # Act
        result = send_verify_email("user@example.com", "https://example.com/verify?token=abc")

        # Assert
        assert result is True
        mock_ses.send_email.assert_called_once()
```

Frontend example (from `frontend/src/utils/externalImageUrls.test.ts`):
```typescript
describe('buildExternalImageUrl', () => {
  it('builds Wix thumbnail fill URL', () => {
    const u = buildExternalImageUrl(WIX, 'thumbnail');
    expect(u).toContain('/v1/fill/w_256,h_256/file.webp');
    expect(u).toMatch(/^https:\/\/static\.wixstatic\.com\/media\//);
  });

  it('returns unknown hosts unchanged', () => {
    const s3 = 'https://example-bucket.s3.amazonaws.com/parts/1/img.webp?X-Amz-Signature=abc';
    expect(buildExternalImageUrl(s3, 'thumbnail')).toBe(s3);
  });
});
```

## Test Structure

**Setup and Teardown (Backend):**

Fixtures handle setup/teardown; pytest runs them automatically:
```python
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
```

Fixture scopes in backend:
- `scope="session"`: One SQLite in-memory engine per xdist worker (created once)
- `scope="function"`: Fixtures like `test_user`, `test_category` recreated per test
- Per-test isolation: Nested transactions (SAVEPOINT) with automatic rollback

**Setup and Teardown (Frontend):**

Setup file (`frontend/src/test/setup.ts`):
```typescript
beforeAll(() => {
  // Mock API client to prevent network requests
  vi.mock('../services/Api', () => ({
    default: mockApiClient,
  }));

  // Suppress known React warnings
  console.error = (...args: unknown[]) => {
    if (typeof args[0] === 'string' && 
        args[0].includes('Warning: ReactDOM.render is no longer supported')) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  // Restore console
  console.error = originalError;
  console.warn = originalWarn;
});
```

## Mocking

**Backend:**

Framework: `unittest.mock.patch` and `unittest.mock.MagicMock`

Pattern for external services:
```python
@patch("app.core.email.settings")
@patch("app.core.email.boto3.client")
def test_send_verify_email_success(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
    # Mock settings
    mock_settings.EMAIL_ENABLED = True
    mock_settings.EMAIL_FROM = "noreply@example.com"

    # Mock SES client
    mock_ses = MagicMock()
    mock_boto_client.return_value = mock_ses

    # Call function
    result = send_verify_email("user@example.com", "https://example.com/verify?token=abc")

    # Assert mock was called correctly
    mock_ses.send_email.assert_called_once()
```

S3 mocking (from `backend/tests/conftest.py`):
```python
@pytest.fixture
def mock_s3(monkeypatch: pytest.MonkeyPatch) -> Generator[Dict[str, Any], None, None]:
    """
    Fake in-memory S3 using moto.

    Patches both the StorageService singleton and lazy crawl client globals.
    """
    from moto import mock_aws
    import boto3

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="test-user-images")
        s3.create_bucket(Bucket="test-crawl-data")

        # Patch settings
        monkeypatch.setattr(app_settings, "USER_IMAGES_BUCKET", "test-user-images")

        # Inject moto client
        monkeypatch.setattr(ss_module.storage_service, "s3_client", s3)

        yield {"client": s3, "user_images_bucket": "test-user-images"}
```

Database mocking:
- No mocking of database; tests use **SQLite in-memory** with real ORM
- Connection: `sqlite:///:memory:` (file: `backend/tests/conftest.py`)
- Per-test isolation via SAVEPOINT (nested transactions)
- `db_session` fixture injects test database into `get_db` dependency

**Frontend:**

Framework: `vitest` with `vi.mock()` and `vi.fn()`

Pattern for API mocking:
```typescript
const mockApiClient = {
  get: vi.fn().mockResolvedValue({ data: null }),
  post: vi.fn().mockResolvedValue({ data: null }),
  put: vi.fn().mockResolvedValue({ data: null }),
  delete: vi.fn().mockResolvedValue({ data: null }),
  patch: vi.fn().mockResolvedValue({ data: null }),
};

vi.mock('../services/Api', () => ({
  default: mockApiClient,
}));
```

**What to Mock:**
- External services (AWS S3, SES, email, auth providers)
- Database client operations (in isolation tests)
- HTTP requests to other APIs

**What NOT to Mock:**
- Database queries (use real in-memory SQLite)
- Internal service methods (use real implementations)
- Language/library built-ins (only if testing error paths)

## Fixtures and Factories

**Test Data (Backend):**

Common fixtures in `backend/tests/conftest.py`:
- `engine`: Session-scoped SQLite in-memory database
- `db_session`: Function-scoped database session with rollback
- `client`: FastAPI TestClient bound to test database
- `test_user`: Standard user fixture
- `premium_test_user`: User with premium subscription
- `test_admin_user`: Admin user
- `test_superuser_user`: Superuser
- `test_category`: Category fixture
- `test_part_manufacturer`: PartManufacturer fixture

Example usage in a test:
```python
def test_build_list_creation(client: TestClient, test_user: User, test_category: Category) -> None:
    """Test that authenticated user can create a build list."""
    token = login_user(client, test_user.username)
    # Use token and fixtures for test
```

**Car Creation Helpers:**

From `backend/tests/conftest.py`:

```python
def create_car_in_db(
    db: Session,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
    start_year: int = 2016,
    end_year: int = 2021,
) -> Dict[str, Any]:
    """Create a car directly in the database for test setup.
    Returns API-shaped dict with id, make, model, generation_name, etc."""
```

```python
def create_car_orm_in_db(
    db: Session,
    make: str = "Honda",
    model: str = "Civic",
    generation_name: str = "10th Gen",
) -> CarGeneration:
    """Create a car and return ORM instance with relationships loaded."""
```

**Authentication Helpers:**

From `backend/tests/conftest.py`:

```python
def login_user(client: TestClient, username: str, password: str = "testpassword") -> str:
    """Login a user and return the Bearer token."""

def create_and_login_user(
    client: TestClient,
    username: str,
    password_override: str = "testpassword",
) -> Dict[str, Any]:
    """Create a user, verify email, log them in, and return user data."""
```

**Environment Setup:**

From `backend/tests/conftest.py` (top of file):
```python
# Set test environment variables BEFORE importing any app code
os.environ["TESTING"] = "true"
os.environ["ENABLE_RATE_LIMITING"] = "false"

# Deferred imports until after env setup
from app.api.models.user import User
from app.main import app as fastapi_app
```

Key behavior:
- **Rate limiting disabled by default** in tests (set `ENABLE_RATE_LIMITING=true` to test rate limiter)
- **Database is in-memory** (no Postgres required)
- **App lifespan not triggered** (tests manually call init functions if needed)

## Coverage

**Backend Coverage:**

Target: Coverage reports generated on every test run
- Report file: `backend/htmlcov/index.html` (after `pytest --cov`)
- Exclude: Migrations (`alembic/versions/`), venv, __pycache__

Command with coverage:
```bash
pytest -n auto --cov=app --cov-report=term-missing --cov-report=html
```

Configuration (from `backend/pytest.ini`):
```ini
addopts = 
    --cov=app
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
```

**Frontend Coverage:**

Target: Incrementally tested utilities; components have integration tests
- Report file: `frontend/coverage/` (after `npm run test:coverage`)
- Exclude: node_modules, test files, type definitions

Configuration (from `frontend/vitest.config.ts`):
```typescript
coverage: {
  provider: 'v8',
  reporter: ['text', 'json', 'html'],
  exclude: [
    'node_modules/',
    'src/test/',
    '**/*.d.ts',
    '**/*.config.*',
    '**/coverage/**',
  ],
}
```

## Test Types

**Unit Tests (Backend):**
- Scope: Single function or service method with mocked dependencies
- Location: `backend/tests/test_<module>.py`
- Example: `test_email.py` tests email template rendering and SES calls in isolation
  
Example (from `backend/tests/test_email.py`):
```python
def test_send_verify_email_success(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
    """send_verify_email returns True and calls SES send_email on success."""
    # AWS and settings mocked; function called in isolation
```

**Unit Tests (Frontend):**
- Scope: Utility functions with real input/output
- Location: `frontend/src/utils/*.test.ts`
- Example: `externalImageUrls.test.ts` tests URL transformation logic

Example (from `frontend/src/utils/externalImageUrls.test.ts`):
```typescript
it('builds Wix thumbnail fill URL', () => {
  const u = buildExternalImageUrl(WIX, 'thumbnail');
  expect(u).toContain('/v1/fill/w_256,h_256/file.webp');
});
```

**Integration Tests (Backend):**
- Scope: Multiple layers (endpoint → service → database)
- Location: In `backend/tests/test_<feature>.py` using `client` fixture
- Example: Car inference tests use real input → function → check output

Example (from `backend/tests/test_car_inference.py`):
```python
class TestInferCarGenerations:
    """Test infer_car_generations returns expected (make, model, generation_name) triples."""

    def test_mkv_supra_a90(self) -> None:
        result = infer_car_generations(
            "Cusco Rear Chassis Power Brace MKV Supra GR A90 / A91",
            "Cusco Rear Chassis Power Brace for the 2020 GR Supra A90.",
        )
        assert ("Toyota", "Supra", "A90") in result
```

**E2E Tests:**
- Not implemented in current codebase
- Frontend: Could use playwright or cypress (not present)
- Backend: HTTP integration tests via TestClient considered integration, not E2E

## Common Patterns

**Async Testing (Backend):**

Pytest handles async functions automatically:
```python
async def login_for_access_token(...) -> dict[str, str | UserRead | bool]:
    """Async endpoint tested directly without extra decoration."""

# Test file
def test_login(client: TestClient) -> None:
    """TestClient internally awaits async endpoints."""
    response = client.post("/api/auth/token", data={"username": "user", "password": "pass"})
    assert response.status_code == 200
```

**Error Testing (Backend):**

Pattern 1 — Expected HTTPException:
```python
def test_invalid_token(self, client: TestClient) -> None:
    """Invalid token returns 401 Unauthorized."""
    response = client.post("/api/verify-email", json={"token": "invalid"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

Pattern 2 — Mocked exception from external service:
```python
@patch("app.core.email.boto3.client")
def test_send_email_ses_error(self, mock_boto_client: MagicMock) -> None:
    """send_verify_email returns False when SES raises an error."""
    from botocore.exceptions import ClientError

    mock_ses = MagicMock()
    mock_ses.send_email.side_effect = ClientError({...}, "SendEmail")
    mock_boto_client.return_value = mock_ses

    result = send_verify_email("user@example.com", "https://example.com/verify")
    assert result is False
```

Pattern 3 — Parametrized tests for multiple error cases:
```python
@pytest.mark.parametrize("input,expected", [
    ("", []),
    (None, []),
    ("  ", []),
])
def test_empty_input(self, input: Optional[str], expected: list) -> None:
    assert infer_car_generations(input, input) == expected
```

**Parametrization (Frontend):**

Frontend uses `describe` + multiple `it` blocks (no parametrize equivalent):
```typescript
describe('buildExternalImageUrl', () => {
  it('builds Wix thumbnail fill URL', () => { ... });
  it('builds Wix hero fit URL', () => { ... });
  it('returns unknown hosts unchanged', () => { ... });
  it('adds width to Shopify CDN URLs', () => { ... });
});
```

Alternative: Array of test cases (manual loop):
```typescript
const cases = [
  { input: WIX, size: 'thumbnail', expected: '/v1/fill/w_256,h_256/' },
  { input: WIX, size: 'hero', expected: '/v1/fit/w_1680,h_1680/' },
];

cases.forEach(({ input, size, expected }) => {
  it(`transforms ${size}`, () => {
    const u = buildExternalImageUrl(input, size);
    expect(u).toContain(expected);
  });
});
```

## CI/CD Integration

**Backend CI (GitHub Actions):**

File: `.github/workflows/backend-ci.yml`

Triggered on:
- Pull requests to `main` branch with changes in `backend/**`

Steps:
1. Python 3.13 setup with pip caching
2. Install dependencies + linting tools
3. **Black formatting check** (`black --check`)
4. **isort import check** (`isort --check-only`)
5. **Type checking** (`pyright`)
6. **Security scan** (`bandit -r app`)
7. **Dependency audit** (`pip-audit`)
8. **Run tests with coverage** (`pytest -n auto --cov=app --cov-report=xml`)

Env vars for CI:
- `SECRET_KEY=test-secret-key-for-ci`
- `ENABLE_RATE_LIMITING=false` (not set; uses conftest default)
- `DEBUG=true`
- `EMAIL_ENABLED=false` (implicit; not required)

**Frontend CI (GitHub Actions):**

File: `.github/workflows/frontend-ci.yml`

Triggered on:
- Pull requests to `main` branch with changes in `frontend/**`

Steps:
1. Node.js 22 setup with npm caching
2. Install dependencies
3. **Prettier formatting check** (`npx prettier --check`)
4. **eslint linting** (`npm run lint`)
5. **Type checking** (`npm run type-check`)
6. **Dependency audit** (`npm audit --audit-level=moderate`)
7. **Build** (`npm run build`)

Note: Tests are **NOT run in CI** for frontend (unlike backend)

---

*Testing analysis: 2026-04-22*
