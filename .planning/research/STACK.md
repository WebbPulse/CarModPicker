# Stack Research: Tech-Debt Refactor Milestone

**Domain:** Mature FastAPI + React + PostgreSQL platform (CarModPicker)
**Researched:** 2026-04-21
**Confidence:** HIGH (versions verified via PyPI/npm; idioms verified via official docs and Context7)

---

## Purpose of This Document

This is NOT a greenfield stack recommendation. CarModPicker already has a working production stack.
This document answers: **for the stack already in use, what does current best-practice look like as of 2026?**

For each library: pinned version → current stable → recommended target → modern idioms to adopt → anti-patterns to eliminate.

---

## Backend Core

### FastAPI

| | |
|--|--|
| **Pinned** | 0.128.0 |
| **Current stable** | 0.136.0 (2026-04-16) |
| **Recommended target** | 0.136.0 |
| **Priority** | MUST upgrade — breaking changes between 0.128 → 0.136 affect this codebase |
| **Confidence** | HIGH |

**What changed 0.128 → 0.136 that matters:**
- 0.135.0: SSE (`EventSourceResponse`) support natively (minor — not used yet)
- 0.135.1: Fixed `TaskGroup` yield handling in request async exit stack (bug fix — relevant if lifespan uses task groups)
- 0.135.2: Raised minimum Pydantic to `>=2.9.0` (already satisfied at 2.11.3)
- 0.136.0: Starlette 1.0.0 support; **strict Content-Type checking for JSON requests** (BREAKING for some API clients — any client that omits `Content-Type: application/json` on POST bodies will now get a 422 by default; set `strict_content_type=False` to disable if needed during migration)

**Lifespan hooks — must adopt:**

The app already uses `lifespan=` context manager in `main.py` (correct). This is the current idiom. Confirm there are zero remaining `@app.on_event("startup")` / `@app.on_event("shutdown")` decorators anywhere in the codebase — these are deprecated and silently skipped when `lifespan=` is also set.

```python
# CORRECT (already in use)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown

app = FastAPI(lifespan=lifespan)

# WRONG — deprecated, silently ignored alongside lifespan=
@app.on_event("startup")
async def startup():
    ...
```

**Dependency injection — current idioms:**

The app's `get_logger` injected via `Depends()` is correct but uncommon; logging is normally module-level (`logger = logging.getLogger(__name__)`). The `Depends()` pattern for logger is harmless but adds needless overhead per request. Module-level loggers are the standard FastAPI pattern.

```python
# CURRENT — logger injected as Depends() (works but unusual)
async def endpoint(logger: logging.Logger = Depends(get_logger)):
    ...

# BETTER — module-level logger (zero overhead, standard pattern)
logger = logging.getLogger(__name__)

async def endpoint():
    logger.info("...")
```

**Async vs sync endpoints — decision rule:**

The codebase uses synchronous SQLAlchemy sessions (`Session`, not `AsyncSession`). Endpoints marked `async def` with a sync `Session` dependency are **not wrong** — FastAPI runs the sync session in a thread pool. But the endpoints must not call other blocking I/O besides the DB. The rule:

- `async def` + sync `Session` dependency: FastAPI threadpools the session, endpoint runs on event loop — fine for this architecture, do not change during refactor
- `async def` + truly blocking CPU work: must offload to thread pool explicitly via `asyncio.run_in_executor`
- `def` (sync) with sync dependencies: also fine; FastAPI threadpools the entire handler

Do NOT mix `async def` with any genuinely blocking library calls without explicit threadpool offload. The codebase's pattern is consistent and should not be changed wholesale — only flag violations found in the audit.

**Middleware — current idioms:**

The custom `BaseHTTPMiddleware` subclasses are correct. One caveat: `BaseHTTPMiddleware` has a known performance overhead (wraps each request in a new coroutine stack). For high-throughput use, Starlette's pure ASGI middleware is faster. At CarModPicker's current traffic level this is not a concern. Keep `BaseHTTPMiddleware` for readability.

**APIRouter composition — current idioms:**

`EndpointRegistry` wrapping `APIRouter` is idiomatic. One thing to verify: all routers use `prefix=` and `tags=` consistently for OpenAPI docs clarity.

---

### Uvicorn

| | |
|--|--|
| **Pinned** | 0.34.0 |
| **Current stable** | 0.45.0 (2026-04-21) |
| **Recommended target** | 0.45.0 |
| **Priority** | SHOULD upgrade — multiple bug fixes and performance improvements across 11 minor versions |
| **Confidence** | HIGH |

No breaking changes expected. Standard `pip install --upgrade uvicorn` upgrade.

---

### SQLAlchemy

| | |
|--|--|
| **Pinned** | 2.0.41 |
| **Current stable** | 2.0.49 (2026-04-03) |
| **Recommended target** | 2.0.49 |
| **Priority** | SHOULD upgrade — patch releases only within the 2.0 series, no breaking changes |
| **Confidence** | HIGH |

**Already correct: 2.0-style ORM usage**

The codebase uses `Mapped[]` typed columns and `mapped_column()` — this is the correct SQLAlchemy 2.0 style. Do NOT revert to the 1.x `Column()` pattern.

```python
# CORRECT — SQLAlchemy 2.0 style (already in use)
class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(nullable=True)

# WRONG — 1.x legacy style (do not use)
class User(Base):
    id = Column(UUID, primary_key=True)
    username = Column(String, unique=True)
```

**Sync vs async session — keep sync for this milestone:**

The codebase uses synchronous `Session` + `psycopg2-binary`. This is the correct choice for the current architecture: sync SQLAlchemy in async FastAPI endpoints runs in FastAPI's threadpool. Migrating to `AsyncSession` + `asyncpg` is a significant refactor (all queries must change, lazy loading breaks silently in async, need `selectinload()` everywhere) and is out of scope for a tech-debt cleanup milestone. **Keep sync session + psycopg2 for this milestone.**

The async session migration is future work if concurrency benchmarks show a bottleneck — at current traffic levels it is premature optimization.

**N+1 prevention — must adopt during refactor:**

The known N+1 in build logs (from CONCERNS.md) must be fixed. The current codebase uses `lazy=select` (default lazy loading). The fix:

```python
# WRONG — N+1: each access to build_list.parts fires a separate query
build_lists = session.scalars(select(BuildList)).all()
for bl in build_lists:
    print(bl.parts)  # fires N queries

# CORRECT — use selectinload for one-to-many collections
from sqlalchemy.orm import selectinload

stmt = select(BuildList).options(selectinload(BuildList.parts))
build_lists = session.scalars(stmt).all()
# fires exactly 2 queries total regardless of result count

# For many-to-one (single object), joinedload is preferred (one JOIN, no extra query)
from sqlalchemy.orm import joinedload

stmt = select(BuildList).options(joinedload(BuildList.owner))
```

Rule of thumb:
- One-to-many collection: `selectinload()` (avoids cartesian explosion)
- Many-to-one single object: `joinedload()` (one JOIN is efficient for single lookups)
- Explicitly set `lazy="raise"` on relationships being fixed to catch regressions in tests

**Query style — 2.0 select() is required:**

```python
# CORRECT — 2.0 style
from sqlalchemy import select
stmt = select(User).where(User.email == email)
user = session.scalars(stmt).first()

# WRONG — 1.x legacy query API (still works in 2.0 but is deprecated path)
user = session.query(User).filter(User.email == email).first()
```

Audit the codebase for any remaining `session.query()` calls and migrate them to `select()` during the refactor. CONVENTIONS.md shows `db.query(DBUser)` usage in `auth.py` — this is the primary target.

---

### Alembic

| | |
|--|--|
| **Pinned** | 1.16.2 |
| **Current stable** | 1.18.4 (2026-02-10) |
| **Recommended target** | 1.18.4 |
| **Priority** | SHOULD upgrade — 1.18.0 added plugin system and improved autogenerate |
| **Confidence** | HIGH |

**Already correct: autogenerate only**

The project correctly uses `alembic revision --autogenerate` only. Never write migration files by hand. This is correct.

**Naming conventions — adopt if not present:**

If the `Base.metadata` doesn't already have a naming convention, add one to prevent Alembic from generating anonymous constraint names (which break on rename/alter):

```python
from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

**Migration hygiene — column renames:**

Alembic sees a column rename as `DROP + ADD` (data loss). Never rename columns directly in the model and autogenerate — always use explicit `op.alter_column()` in a manual migration step.

---

### Pydantic

| | |
|--|--|
| **Pinned** | 2.11.3 |
| **Current stable** | 2.13.3 (2026-04-20) |
| **Recommended target** | 2.13.3 |
| **Priority** | SHOULD upgrade — minor, patch-level improvements within v2 series |
| **Confidence** | HIGH |

**Already correct: ConfigDict and field_validator**

The codebase uses `ConfigDict(from_attributes=True)` and `@field_validator` with `@classmethod` — these are the correct v2 patterns.

**Computed fields — adopt where properties are used:**

If any schema models use `@property` to expose derived values, replace with `@computed_field` so they appear in serialization automatically:

```python
# WRONG — @property is invisible to Pydantic serialization
class PartRead(BaseModel):
    price_cents: int

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100

# CORRECT — @computed_field is included in .model_dump() and response JSON
from pydantic import computed_field

class PartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    price_cents: int

    @computed_field
    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100
```

**Annotated validators — prefer for reusable constraints:**

```python
from typing import Annotated
from pydantic import AfterValidator

def must_be_positive(v: int) -> int:
    if v <= 0:
        raise ValueError("must be positive")
    return v

PositiveInt = Annotated[int, AfterValidator(must_be_positive)]

# Reuse across schemas without copy-pasting @field_validator
class PartCreate(BaseModel):
    price_cents: PositiveInt
    quantity: PositiveInt
```

**model_validator for cross-field validation:**

```python
from pydantic import model_validator

class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode='after')
    def check_date_order(self) -> 'DateRange':
        if self.end < self.start:
            raise ValueError('end must be after start')
        return self
```

**v1 patterns to eliminate:**

- `@validator` decorator → replace with `@field_validator` (v1 validator is still imported but emits deprecation warnings in v2)
- `class Config:` nested class → replace with `model_config = ConfigDict(...)`
- `orm_mode = True` → replace with `from_attributes=True` in ConfigDict
- `.dict()` method → replace with `.model_dump()`
- `.parse_obj()` → replace with `.model_validate()`

Audit all schema files for `@validator`, `class Config`, `orm_mode`, `.dict()`, `.parse_obj()`.

---

### Authentication — python-jose → PyJWT

| | |
|--|--|
| **Pinned** | python-jose[cryptography] 3.5.0 |
| **Current stable (PyJWT)** | PyJWT 2.12.1 (2026-03-13) |
| **Recommended target** | PyJWT 2.12.1 |
| **Priority** | SHOULD replace — FastAPI officially updated docs to recommend PyJWT (PR #11589, May 2024) |
| **Confidence** | HIGH |

**Why replace python-jose:**

python-jose is essentially unmaintained (minimal commits since 2021). FastAPI has officially moved its documentation to recommend PyJWT. CVE-2024-33663 (algorithm confusion) affects python-jose when `algorithms` is not explicitly specified to `jwt.decode()`. The codebase comment in `requirements.txt` correctly notes the ecdsa CVE is not exploitable with HS256, but the package being unmaintained is itself a risk.

**Migration is simple — same `encode`/`decode` surface:**

```python
# BEFORE (python-jose)
from jose import JWTError, jwt
payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
token = jwt.encode(data, SECRET_KEY, algorithm="HS256")

# AFTER (PyJWT)
import jwt as pyjwt
from jwt.exceptions import InvalidTokenError

payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
token = pyjwt.encode(data, SECRET_KEY, algorithm="HS256")
# Note: PyJWT encode() returns str (not bytes) in v2+
```

The main difference: `JWTError` → `InvalidTokenError` (or `jwt.PyJWTError`). Since the app only uses HS256, the migration is a straight find-replace with one exception rename.

---

### psycopg2-binary

| | |
|--|--|
| **Pinned** | 2.9.10 |
| **Current stable** | 2.9.12 (2026-04-20) |
| **Recommended target** | 2.9.12 (same major) |
| **Priority** | MINOR upgrade — keep psycopg2 for this milestone (see SQLAlchemy note above) |
| **Confidence** | HIGH |

**Longer-term consideration (future milestone):** psycopg3 (`psycopg` package, v3.3.3) is now production stable and provides native async support with SQLAlchemy 2.0. Migration requires switching to `create_async_engine("postgresql+psycopg://...")` + `AsyncSession`. Not for this milestone.

---

### boto3

| | |
|--|--|
| **Pinned** | 1.42.91 |
| **Current stable** | 1.42.93 (2026-04-21) |
| **Recommended target** | 1.42.93 |
| **Priority** | MINOR patch upgrade |
| **Confidence** | HIGH |

**Type stubs — current idiom is correct:**

`boto3-stubs[s3,sesv2]` is the correct approach. The `TYPE_CHECKING` guard prevents importing stubs at runtime:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

def upload_file(client: "S3Client", ...) -> None:
    ...
```

This pattern is already idiomatic and correct. The boto3 stubs approach is the accepted standard for type-safe AWS SDK usage in Python.

---

### Type Checking — mypy vs pyright

| | |
|--|--|
| **mypy pinned** | 1.17.1 |
| **mypy current stable** | 1.20.2 (2026-04-21) |
| **Recommended** | Keep both: pyright in editor (already configured in pyproject.toml), mypy in CI |
| **Confidence** | MEDIUM |

The codebase already runs both mypy and pyright (per CONVENTIONS.md). This is actually a strong pattern:
- pyright catches errors faster in the editor (3-5x faster than mypy, no plugin needed for FastAPI/Pydantic)
- mypy in CI ensures library compatibility via its plugin ecosystem

Upgrade mypy to 1.20.2. Ensure `pyright` is pinned in dev tooling (not just installed via editors). Run `pyright --verifytypes app` to check for missing type annotations in the service layer.

---

### pytest / pytest-asyncio / pytest-xdist

| | |
|--|--|
| **pytest pinned** | 9.0.3 |
| **pytest current stable** | 9.0.3 (confirmed current as of 2026-04-21) |
| **pytest-asyncio pinned** | 1.3.0 |
| **pytest-asyncio current stable** | 1.3.0 (confirmed current) |
| **pytest-xdist pinned** | 3.8.0 |
| **Recommended target** | Keep current versions — all are at current stable |
| **Priority** | NO upgrade needed |
| **Confidence** | HIGH |

**pytest-asyncio 1.3.0 — legacy mode removed:**

Version 1.3.0 removed `legacy` mode. Only `auto` and `strict` modes remain. Ensure `asyncio_mode` is explicitly configured in `pyproject.toml` (or `pytest.ini`):

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # recommended for pure-asyncio projects
# OR
asyncio_mode = "strict"  # requires explicit @pytest.mark.asyncio on each test
```

If the project uses async tests without explicit mode config, add it now to silence deprecation warnings in 1.3.0.

**pytest-xdist with async tests:**

`-n auto` + `asyncio_mode = "auto"` works correctly in pytest-asyncio 1.3.0 — each worker gets its own event loop. The existing `-n auto` convention is correct. Do not use `--dist=loadscope` unless you have shared async fixtures that break across workers (investigate if flaky async tests appear).

**Test isolation pattern — already correct:**

The savepoint/outer-transaction rollback pattern documented in CONVENTIONS.md (`join_transaction_mode="create_savepoint"`) is the correct pattern for fast test isolation without resetting the database between tests. Keep it.

---

## Frontend Core

### React

| | |
|--|--|
| **Pinned** | 19.1.0 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed |

**React 19 hooks to adopt during refactor:**

React 19.1.0 is current. The refactor opportunity is adopting React 19 APIs that may not be in use yet:

`useOptimistic` — for mutations where you want to show instant feedback before the server confirms:

```tsx
// Before React 19: manual state management + rollback on error
const [votes, setVotes] = useState(initialVotes);
const handleVote = async () => {
    setVotes(v => v + 1);  // optimistic
    try { await postVote(); }
    catch { setVotes(v => v - 1); }  // rollback
};

// React 19: useOptimistic handles this cleanly
import { useOptimistic, useTransition } from 'react';
const [optimisticVotes, addOptimisticVote] = useOptimistic(
    serverVotes,
    (current, increment: number) => current + increment
);
const [isPending, startTransition] = useTransition();
const handleVote = () => {
    startTransition(async () => {
        addOptimisticVote(1);
        await postVote();
    });
};
```

`use()` hook — for consuming promises or context mid-render (replaces some `useEffect`+state patterns):

```tsx
// For context, use() can be called conditionally (unlike useContext)
import { use } from 'react';
const user = use(AuthContext);  // simpler than useContext in some cases
```

`useTransition` with async — now supports async functions directly in React 19:

```tsx
const [isPending, startTransition] = useTransition();
startTransition(async () => {
    await someAsyncOperation();  // works in React 19, didn't before
});
```

**What NOT to adopt:**

Server Components and server actions are a Next.js/Remix pattern. CarModPicker is a Vite SPA — these do not apply. Do not attempt to adopt RSC patterns.

**Context usage — current idioms remain correct:**

`AuthContext` and `AppSettingsContext` pattern is idiomatic React. The `useAuth()` hook that throws when used outside provider is the correct guard pattern. No changes needed.

**Error boundaries — ensure coverage:**

React 19 improved error boundary behavior. The root `ErrorBoundary` in `main.tsx` is correct. Ensure route-level error boundaries exist for pages that make async API calls — a single root boundary means the entire app crashes on one page's error.

---

### React Router

| | |
|--|--|
| **Pinned** | 7.6.0 |
| **Confidence** | HIGH — at current stable or near it |
| **Priority** | No upgrade needed |

**SPA mode — correct usage:**

CarModPicker is a Vite SPA. React Router 7 in "library mode" (using `createBrowserRouter` + `RouterProvider`) is correct for this architecture. Do NOT migrate to "framework mode" (which adds SSR complexity appropriate for Remix-style apps, not a Vite SPA with a separate FastAPI backend).

**clientLoader pattern — adopt for data-fetching routes:**

React Router 7 supports `clientLoader` for route-level data fetching. This is cleaner than fetching in `useEffect`:

```tsx
// React Router 7 clientLoader (if using framework/data router mode)
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
    const part = await partsApi.getPart(params.id);
    return { part };
}

export default function PartPage({ loaderData }: Route.ComponentProps) {
    const { part } = loaderData;
    // ...
}
```

Evaluate whether the frontend's current `useEffect`-on-mount data fetching can be migrated to `clientLoader` during page refactors. This is "nice to adopt" for new pages, not a forced migration for existing pages.

---

### TypeScript

| | |
|--|--|
| **Pinned** | ~5.8.3 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed |

**Type-safety gaps to address:**

- Replace any `any` casts that exist in API response types with proper interfaces
- Ensure all `axios` response types use generic `AxiosResponse<T>` not raw `any`
- Use `satisfies` operator (TS 4.9+) for configuration objects that need narrowing:

```typescript
const config = {
    baseURL: '/api',
    timeout: 5000,
} satisfies Partial<AxiosRequestConfig>;
```

- Import types with `import type` consistently (already enforced by ESLint config, verify coverage)

---

### Vite + Build Tools

| | |
|--|--|
| **Vite pinned (frontend)** | 6.3.5 |
| **Vite pinned (extension)** | 6.4.2 |
| **Confidence** | HIGH — at current stable series |
| **Priority** | No upgrade needed |

**Vite 6 patterns — already correct:**

The `@tailwindcss/vite` plugin instead of PostCSS `tailwindcss` plugin is the correct Vite 6 + Tailwind v4 approach. The SWC plugin (`@vitejs/plugin-react-swc`) for fast JSX transpilation is correct.

**Environment variables:**

Vite 6 uses `import.meta.env.VITE_*` — ensure no `process.env` references remain in frontend code.

---

### Vitest

| | |
|--|--|
| **Pinned** | 3.2.4 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed |

**Current idioms to adopt:**

Coverage provider: `@vitest/coverage-v8` is the correct provider (already used). `c8` is the predecessor — ensure no lingering `c8` references.

Test context API (Vitest 3):

```typescript
// Vitest 3: use test.extend for shared context (preferred over beforeEach setup)
const test = base.extend<{ user: User }>({
    user: async ({}, use) => {
        const u = await createTestUser();
        await use(u);
        await cleanup(u);
    }
});
```

**Performance:** Enable `experimental.fsModuleCache` in vitest config for faster incremental re-runs:

```typescript
// vite.config.ts
export default defineConfig({
    test: {
        experimental: {
            fsModuleCache: true,
        }
    }
})
```

---

### Tailwind CSS

| | |
|--|--|
| **Pinned** | 4.1.7 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed; clean up v3 patterns |

**The app is already on v4 (correct).** The cleanup work is removing v3 patterns that may have survived the migration.

**v3 patterns to eliminate during component refactors:**

1. `tailwind.config.js` should no longer exist — config belongs in CSS via `@theme {}`. If a `tailwind.config.js` or `tailwind.config.ts` is still present, migrate those theme values to the CSS file.

2. Three-directive imports:
```css
/* WRONG (v3 pattern) */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* CORRECT (v4) */
@import "tailwindcss";
```

3. Gradient utility renames:
```html
<!-- WRONG (v3 name) -->
<div class="bg-gradient-to-r from-blue-500 to-purple-500">

<!-- CORRECT (v4 name) -->
<div class="bg-linear-to-r from-blue-500 to-purple-500">
```

4. Border and divide color defaults changed from `gray-200` to `currentColor` in v4. Any `border` or `divide-*` class without explicit color now renders differently than in v3. Audit for visual regressions.

5. Arbitrary value overuse: `w-[37px]` style arbitrary values should be replaced with design token values or CSS custom properties registered in `@theme {}`. Keep arbitrary values only when a design token genuinely doesn't cover the case.

6. The `content` array in config is gone in v4 — Tailwind scans automatically. Delete any leftover `content: [...]` configuration.

**v4 idioms to use (not v3):**

```css
/* CSS-first theme definition (v4) */
@import "tailwindcss";

@theme {
    --color-brand: oklch(0.65 0.2 250);
    --font-heading: "Inter", sans-serif;
    --radius-card: 0.75rem;
}
```

```html
<!-- Use CSS vars directly as utilities -->
<div class="bg-(--color-brand) rounded-(--radius-card)">
```

---

## AWS / Infrastructure

### App Runner + RDS PG16 + S3 + SES + EventBridge

| | |
|--|--|
| **Confidence** | MEDIUM — based on official AWS docs and WebSearch |
| **Priority** | Audit-level; no infra swaps this milestone |

**Secrets management — current pattern needs verification:**

If secrets are injected as env vars via Terraform/App Runner config at deploy time (not via Secrets Manager native integration), consider migrating to App Runner's native Secrets Manager integration. This pulls secrets at runtime rather than bake-time:

- App Runner supports native Secrets Manager integration: the service IAM role needs `secretsmanager:GetSecretValue` on the specific secret ARNs
- Benefit: secrets rotation without redeploy; audit trail via CloudWatch
- The IAM role should be scoped to `Resource: arn:aws:secretsmanager:REGION:ACCOUNT:secret:carmodpicker/*` not `*`

**X-Ray tracing:**

App Runner has native AWS X-Ray integration. If not enabled, this is a one-checkbox change in the App Runner service config (or Terraform `observability_configuration_arn`). X-Ray provides distributed tracing across App Runner → RDS → S3 without code changes beyond adding the SDK.

**IAM least privilege — verify:**

The App Runner instance role and any Lambda/ECS crawler roles should follow least-privilege:
- S3: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` scoped to specific bucket ARNs (not `s3:*`)
- SES: `ses:SendEmail`, `ses:SendRawEmail` scoped to specific sender identity
- Secrets Manager: `secretsmanager:GetSecretValue` scoped to specific secret ARNs

**RDS connection pool:**

The default SQLAlchemy connection pool (`pool_size=5, max_overflow=10`) may be too small or too large for App Runner's concurrency model. App Runner can scale to multiple instances; each instance has its own pool. Verify `pool_pre_ping=True` is set (detects stale connections after RDS failover) and `pool_recycle` is set to `<1800` seconds (avoids hitting RDS's idle connection timeout).

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,       # reconnect after RDS failover
    pool_recycle=1800,        # recycle before RDS idle timeout
)
```

---

## Anti-Patterns to Eliminate

| Anti-Pattern | Where | Why Bad | Fix |
|---|---|---|---|
| `session.query()` legacy API | `auth.py`, possibly others | SQLAlchemy 2.0 deprecated path | Migrate to `select()` + `session.scalars()` |
| `@app.on_event()` decorators | Anywhere they persist | Silently no-ops alongside `lifespan=` | Remove (or consolidate into lifespan) |
| `@validator` (Pydantic v1) | Schema files | Emits deprecation warnings in Pydantic v2 | Replace with `@field_validator` |
| `class Config:` (Pydantic v1) | Schema files | Deprecated in v2 | Replace with `model_config = ConfigDict(...)` |
| `.dict()` / `.parse_obj()` | Anywhere | Pydantic v1 method names | Replace with `.model_dump()` / `.model_validate()` |
| python-jose for JWT | `auth.py` | Unmaintained; FastAPI docs recommend PyJWT | Migrate to `PyJWT` |
| Lazy-loaded relationships in list endpoints | Services | N+1 queries | Add `selectinload()` to list queries |
| `process.env` in frontend | Any frontend file | Vite uses `import.meta.env` | Replace with `import.meta.env.VITE_*` |
| `bg-gradient-to-*` | Tailwind CSS | v3 class name, broken in v4 | Replace with `bg-linear-to-*` |
| `@tailwind base/components/utilities` | CSS files | v3 import syntax | Replace with `@import "tailwindcss"` |
| Logger injected via `Depends()` | `auth.py`, others | Overhead per request; non-standard | Replace with module-level `logging.getLogger(__name__)` |

---

## Version Summary Table

| Package | Pinned | Current Stable | Gap | Action |
|---|---|---|---|---|
| FastAPI | 0.128.0 | 0.136.0 | 8 minor | MUST upgrade (strict CT-Type behavior) |
| Uvicorn | 0.34.0 | 0.45.0 | 11 minor | SHOULD upgrade |
| SQLAlchemy | 2.0.41 | 2.0.49 | 8 patch | SHOULD upgrade |
| Alembic | 1.16.2 | 1.18.4 | 2 minor | SHOULD upgrade |
| Pydantic | 2.11.3 | 2.13.3 | 2 minor | SHOULD upgrade |
| python-jose | 3.5.0 | 3.5.0 | — | REPLACE with PyJWT 2.12.1 |
| psycopg2-binary | 2.9.10 | 2.9.12 | 2 patch | MINOR |
| boto3 | 1.42.91 | 1.42.93 | 2 patch | MINOR |
| mypy | 1.17.1 | 1.20.2 | 3 patch | MINOR |
| pytest | 9.0.3 | 9.0.3 | — | Current |
| pytest-asyncio | 1.3.0 | 1.3.0 | — | Current |
| React | 19.1.0 | 19.1.0 | — | Current |
| React Router | 7.6.0 | ~7.6 | — | Current |
| TypeScript | 5.8.3 | ~5.8 | — | Current |
| Vite | 6.3.5 / 6.4.2 | ~6.4 | — | Current |
| Vitest | 3.2.4 | ~3.2 | — | Current |
| Tailwind CSS | 4.1.7 | 4.1.7 | — | Current, clean v3 patterns |

---

## What NOT to Change This Milestone

| Decision | Rationale |
|---|---|
| Keep sync SQLAlchemy session | Migrating to AsyncSession + asyncpg is a major refactor. Not needed at current traffic. Correct to defer. |
| Keep React Router in library mode (not framework mode) | SPA + separate FastAPI backend is the right architecture. Framework mode adds SSR complexity that doesn't fit. |
| Keep psycopg2-binary | Coupled to sync session decision above. |
| Keep BaseHTTPMiddleware | Performance overhead negligible at current traffic. Readable. |
| Keep -n auto parallel pytest | The savepoint isolation pattern works correctly with xdist. No reason to change. |
| Keep axios (not fetch) | Axios intercepts + retry logic is already wired in. Migrating to native fetch is scope creep. |
| No RSC/Server Components | Vite SPA architecture. Server Components are a different deployment model. |
| No LLM APIs in this milestone | Per PROJECT.md — cost-gated until business model proven. |

---

## Sources

- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) — version verification, Starlette 1.0 breaking changes, lifespan idioms
- [FastAPI Lifespan Events Docs](https://fastapi.tiangolo.com/advanced/events/) — current lifespan pattern
- [FastAPI Discussion #11345](https://github.com/fastapi/fastapi/discussions/11345) — python-jose → PyJWT migration confirmation
- [SQLAlchemy 2.0 Async IO Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — AsyncSession caveats, lazy loading in async
- [SQLAlchemy Relationship Loading](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html) — selectinload vs joinedload
- [Pydantic v2 Validators](https://pydantic.dev/docs/validation/latest/concepts/validators/) — field_validator, model_validator, annotated patterns
- [Tailwind CSS v4.0 Blog Post](https://tailwindcss.com/blog/tailwindcss-v4) — breaking changes from v3
- [PyPI: FastAPI](https://pypi.org/project/fastapi/) — current stable version
- [PyPI: SQLAlchemy](https://pypi.org/project/sqlalchemy/) — current stable version
- [PyPI: Pydantic](https://pypi.org/project/pydantic/) — current stable version
- [PyPI: Alembic](https://pypi.org/project/alembic/) — current stable version
- [PyPI: Uvicorn](https://pypi.org/project/uvicorn/) — current stable version
- [PyPI: PyJWT](https://pypi.org/project/PyJWT/) — recommended JWT replacement
- [PyPI: pytest-asyncio](https://pypi.org/project/pytest-asyncio/) — 1.3.0 confirmed current
- [AWS App Runner Security Best Practices](https://docs.aws.amazon.com/apprunner/latest/dg/security-best-practices.html) — IAM, Secrets Manager native integration
- [React 19 Release Notes](https://react.dev/blog/2024/12/05/react-19) — useOptimistic, useTransition, use()
- [pytest-asyncio 1.3.0 Docs](https://pytest-asyncio.readthedocs.io/en/stable/) — asyncio_mode configuration, legacy removal

---

*Stack research for: CarModPicker tech-debt refactor milestone*
*Researched: 2026-04-21*
