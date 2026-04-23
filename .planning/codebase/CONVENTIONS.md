# Coding Conventions

**Analysis Date:** 2026-04-22

## Naming Patterns

**Python Functions:**
- snake_case for all functions and methods
- Example: `create_job`, `infer_car_generations`, `get_default_category_id` (from `backend/tests/conftest.py`)

**Python Classes:**
- PascalCase for ORM models and services
- Example: `User`, `CarGeneration`, `BackgroundJob` (from `backend/app/api/models/user.py`)
- Exception: Pydantic schemas also use PascalCase: `UserCreate`, `UserRead`, `UserUpdate` (from `backend/app/api/schemas/user.py`)

**Python Constants:**
- UPPER_CASE for module-level constants
- Example: `DEFAULT_HEARTBEAT_TIMEOUT_SEC = 180`, `SOCIAL_URL_MAX_LENGTH = 500` (from `backend/app/services/job_service.py`)

**Python Variables:**
- snake_case for local variables, function parameters, and instance attributes
- Example: `email_verified`, `hashed_password`, `is_superuser`, `subscription_expires_at` (from `backend/app/api/models/user.py`)

**TypeScript/React Components:**
- PascalCase for component exports
- Example: `Input`, `SearchableSelect`, `ResponsiveTableWrapper` (from `frontend/src/components/common/Input.tsx`)

**TypeScript Functions and Hooks:**
- camelCase for functions and custom hooks
- Example: `useAuth`, `buildExternalImageUrl`, `create_and_login_user` (from `frontend/src/hooks/useAuth.ts`)

**TypeScript Constants:**
- UPPER_CASE for module-level constants
- camelCase for const variables in functions
- Example: `const WIX = '...'`, `const baseClasses = '...'` (from `frontend/src/components/common/Input.tsx`)

**File Names:**
- Python: snake_case (e.g., `user.py`, `base_endpoint_router.py`)
- TypeScript: camelCase for hooks (e.g., `useAuth.ts`, `useContainerWidth.ts`)
- React: PascalCase for components (e.g., `Input.tsx`, `SearchableSelect.tsx`)
- Test files: snake_case with `test_` prefix (Python) or `.test.ts` suffix (TypeScript)

## Code Style

**Formatting:**
- **Backend:** Black (line length: 120)
  - Config: `backend/pyproject.toml`, `[tool.black]` section
  - Command: `black --config pyproject.toml .`
  
- **Frontend:** Prettier (line length: 80, single quotes, trailing commas)
  - Config: `frontend/.prettierrc.json`
  - Example settings: `"semi": true, "singleQuote": true, "printWidth": 80`
  - Command: `npm run lint` (includes prettier check)

**Linting:**
- **Backend:** 
  - isort for import sorting (profile: "black", line length: 120)
    - Config: `backend/pyproject.toml`, `[tool.isort]` section
    - Command: `isort .`
  - pyright for type checking (strict mode enabled)
    - Config: `backend/pyproject.toml`, `[tool.mypy]` section
    - Command: `pyright`
  - bandit for security scanning (level: medium/high)
    - Config: `backend/pyproject.toml`, `[tool.bandit]` section
    - Command: `bandit -r app -ll`

- **Frontend:** 
  - eslint with TypeScript support and React hooks rules
    - Config: `frontend/eslint.config.js`
    - Rules: `react-hooks/rules-of-hooks: 'error'`, `react-hooks/exhaustive-deps: 'warn'`
    - Type-checked files: `src/**/*.ts`, `src/**/*.tsx`
    - Test files: relaxed unsafe assignment checks
    - Command: `npm run lint`
  - TypeScript compiler in strict mode
    - Config: `frontend/tsconfig.app.json`
    - Key flags: `"strict": true, "noUnusedLocals": true, "noUnusedParameters": true`
    - Command: `npm run type-check` (runs `tsc --noEmit`)

## Import Organization

**Backend (Python):**

Order (enforced by isort):
1. Standard library imports
2. Third-party imports (fastapi, sqlalchemy, pydantic, pytest)
3. Local app imports (from `app.`)

Example (from `backend/app/api/endpoints/auth.py`):
```python
# Standard library
import base64
import binascii
import io
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

# Third-party
import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

# Local
from app.api.dependencies.auth import (...)
from app.api.models.user import User as DBUser
from app.core.config import settings
from app.db.session import get_db
```

**Frontend (TypeScript):**

Order (enforced by eslint):
1. React and library imports
2. Type imports from local modules
3. Regular imports from local modules

Example (from `frontend/src/services/Api.ts`):
```typescript
import axios, { type AxiosError, type AxiosResponse } from 'axios';
import type {
  AdminUserUpdate,
  BodyLoginForAccessToken,
  // ... more types
} from '../types/Api';
```

**Path Aliases:**
- Backend: `known_first_party = ["app"]` allows `from app.api.models import User`
- Frontend: No path aliases configured; relative imports used (e.g., `import { useAuth } from '../contexts/AuthContextDefinition'`)

## Error Handling

**Backend Patterns:**

HTTPException with status codes and detail messages (from `backend/app/api/endpoints/auth.py`):
```python
from fastapi import HTTPException, status

# Typical pattern
if not user:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

# Authentication errors use 401 Unauthorized
raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
```

Try-catch with logging for expected errors:
```python
try:
    totp = pyotp.TOTP(user.totp_secret)
except Exception as e:
    logger.error(f"Invalid TOTP secret format for user: {user.username}, error: {str(e)}")
    ResponsePatterns.raise_internal_server_error("2FA configuration error")
```

Middleware error handling:
- Registered in `backend/app/main.py` with `EndpointRegistry`
- Centralizes error responses to ensure consistency
- Rate limiting middleware (when enabled) returns 429 Too Many Requests

**Frontend Patterns:**

Try-catch in async operations:
```typescript
// From axios API client pattern (frontend/src/services/Api.ts)
const response = await axios.get('/api/endpoint', {
  headers: { Authorization: `Bearer ${token}` }
});

// Component-level error boundaries and async error handling
try {
  const result = await apiCall();
} catch (error) {
  if (axios.isAxiosError(error)) {
    // Handle HTTP errors
    const status = error.response?.status;
    const message = error.response?.data?.detail || error.message;
  }
}
```

Custom error utilities in `ResponsePatterns` (backend):
- `ResponsePatterns.raise_internal_server_error(detail)` for 500 errors
- Consistent error response format across all endpoints

## Logging

**Framework:** Python logging (backend), console (frontend)

**Backend Patterns:**
- Get logger per module: `from app.core.logging import get_logger` (dependency injection)
- Log level usage:
  - INFO: Significant operations (user actions, job completions)
  - WARNING: Recoverable issues (validation failures)
  - ERROR: Unrecoverable issues with context
  
Example (from `backend/app/api/endpoints/auth.py`):
```python
from app.core.logging import get_logger

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str | UserRead | bool]:
    """Authenticate user and return access token and user details."""
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user:
        logger.warning(f"Login attempt for non-existent user: {form_data.username}")
        raise HTTPException(...)
```

**Frontend Patterns:**
- Console logging for debugging (no structured logging library)
- Silent most console warnings/errors via test setup (`frontend/src/test/setup.ts`)

## Comments

**When to Comment:**

Backend (Python):
- Module docstring at file start explaining purpose
- Function docstrings (triple quotes) describing parameters and return value
- Inline comments for non-obvious logic or workarounds

Example (from `backend/tests/conftest.py`):
```python
"""
Per-test session wrapped in an outer transaction that always rolls back.
`join_transaction_mode="create_savepoint"` lets test code call session.commit()
without ending the outer transaction — commits become SAVEPOINT releases.
"""
```

Example with inline comments (from `backend/app/api/models/user.py`):
```python
# Nullable: OAuth-only users (e.g. signed up via Google) have no password set.
hashed_password: Mapped[Optional[str]] = mapped_column(nullable=True)
```

Frontend (TypeScript):
- JSDoc for exported functions and components
- Inline comments for complex logic
- Trailing comments on HTML attributes for clarity

Example (from `frontend/src/components/common/Input.tsx`):
```typescript
// Calculate padding classes based on icons
let paddingClasses = '!px-5'; // Default padding with !important to override CSS
if (leftIconToUse && rightIconToUse) {
  paddingClasses = '!pl-16 !pr-16'; // Both icons: balanced padding
}
```

**JSDoc/TSDoc:**
- Not heavily used; prefer self-documenting code with clear names
- Type annotations serve as documentation in TypeScript
- React component prop interfaces serve as parameter documentation

## Function Design

**Size:** Prefer small, focused functions (< 50 lines in most cases)

**Parameters:**
- Use explicit named parameters over `**kwargs` or object spread
- Backend example (from `backend/app/services/job_service.py`):
```python
def create_job(
    db: Session,
    *,  # Force keyword-only arguments after db
    job_type: str,
    triggered_by: str,
    params: Optional[dict[str, Any]] = None,
    created_by_user_id: Optional[UUID] = None,
    worker_instance_id: Optional[str] = None,
) -> BackgroundJob:
```

- Frontend: Props passed as object; interface defines shape explicitly:
```typescript
interface InputProps {
  type?: string;
  placeholder?: string;
  value?: string | number;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  // ... other props
}
```

**Return Values:**
- Explicit return type annotations (required by type checkers)
- Backend: SQLAlchemy ORM models, Pydantic schemas, or primitives
- Frontend: React components return JSX.Element, hooks return typed values

## Module Design

**Exports:**

Backend:
- Services export a class (e.g., `class BaseCRUDService`)
- Endpoints are routers: `router = APIRouter()`, functions decorated with `@router.get()`, etc.
- Models are SQLAlchemy classes decorated with `@dataclass` metadata
- Schemas are Pydantic models

Example endpoint structure (from `backend/app/api/endpoints/auth.py`):
```python
router = APIRouter()

@router.post("/token")
async def login_for_access_token(...) -> dict[str, ...]:
    """Docstring"""
    # implementation
```

Frontend:
- Components export as default export or named export
- Hooks export as named exports (e.g., `export const useAuth = () => {...}`)
- Services/API modules export an object or class with methods

Example (from `frontend/src/hooks/useAuth.ts`):
```typescript
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

**Barrel Files:**
- Used in backend: `backend/app/api/models/__init__.py`, `backend/app/api/schemas/__init__.py`
- Allows `from app.api.models import User` instead of `from app.api.models.user import User`
- Frontend: Minimal use; components imported directly by path

**Dependency Injection (Backend):**
- FastAPI `Depends()` pattern for shared dependencies
- Session, logger, current user all injected via `Depends()`

Example (from `backend/app/api/endpoints/auth.py`):
```python
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
):
```

**Pydantic v2 Schemas:**
- `ConfigDict` for model config (e.g., `from_attributes=True` for ORM mode)
- Field validators with `@field_validator` decorator
- Serializers with `@field_serializer` decorator

Example (from `backend/app/api/schemas/user.py`):
```python
@field_validator("instagram_url", mode="before")
@classmethod
def validate_instagram_url(cls, v: Optional[str]) -> Optional[str]:
    return _validate_social_url(v, "Instagram", SOCIAL_PLATFORM_HOSTS["instagram"])
```

## Alembic downgrade testing

(Phase 4 DATA-09 / D-31)

Every migration PR must include documented evidence that the Alembic revision
round-trips cleanly against a local Docker Postgres. CI automation is
deferred until the Postgres side-car matures beyond the single
concurrency-test job (see Phase 4 Deferred Ideas in
`.planning/phases/04-db-parts-hardening/04-CONTEXT.md`). The convention is
reviewer-gated: it is the migration author's responsibility to run the
round-trip locally and paste the green output into the PR.

### Procedure

1. Start a local Postgres instance. Two common options:

   ```
   # Recommended for migration work: the test-only side-car on port 5433
   # (added by plan 04-05; ephemeral tmpfs volume, no persistence).
   docker compose -f docker-compose.test.yml up -d postgres-test
   ```

   ```
   # Or use the dev default on port 5432 if you prefer.
   docker compose -f backend/docker-compose.yml up -d
   ```

2. Run the round-trip helper with an EXPLICIT revision id or the literal
   `head`:

   ```
   cd backend
   ./scripts/test_migration_round_trip.sh <revision_id>
   # or explicitly target head:
   ./scripts/test_migration_round_trip.sh head
   ```

   The script runs:

   ```
   alembic upgrade <revision_id>
   alembic downgrade -1
   alembic upgrade head
   ```

   and exits non-zero if any step fails. The REVISION argument is REQUIRED
   (INFO 13) — omitting it fails with a usage message instead of silently
   defaulting to `head`, so reviewers can confirm the author ran the script
   against the specific revision under review.

3. Paste the script's green output into the PR conversation under a
   "Migration round-trip" heading. Reviewers verify the three-step sequence
   completed; if any step failed, block the PR.

### Exceptions

- **Forward-only data migrations** — `downgrade()` is annotated with the
  `# SAFE: forward-only data backfill; no reversal needed` convention (Phase
  1 SAFE-04). The round-trip still runs, but the downgrade step is expected
  to be a no-op.
- **Already-applied migrations on prod** — historic revisions that pre-date
  this convention are grandfathered (see Phase 1 SAFE-08 repair pattern).

### Rationale

`alembic downgrade -1` followed by `upgrade head` is the smallest invariant
that catches the most common migration-authoring bugs: missing `op.drop_*`
in `downgrade()`, mismatched column types, naming-convention drift,
ordering issues in destructive ops, etc. Automating in CI is a future task;
a reviewer-gated doc check is sufficient for the current team size.

---

*Convention analysis: 2026-04-22*
