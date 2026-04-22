# Architecture

**Analysis Date:** 2026-04-22

## Pattern Overview

**Overall:** Layered N-tier (3-layer) + FastAPI + React + Crawler subsystem

**Key Characteristics:**
- **Backend:** Request → Middleware → Endpoint (Router) → Service → Model (ORM) → Database
- **Frontend:** React Router → Page components → Service API calls → Axios client
- **Infrastructure:** AWS (App Runner + RDS PostgreSQL + S3 + EventBridge + CloudFront)
- **Generics everywhere:** Base router, base service, and adapter patterns reduce redundancy
- **Polymorphic systems:** Unified vote/report endpoints handle all entity types through a single router

## Layers

**Middleware Layer:**
- Purpose: Pre/post-request processing, error handling, rate limiting, request context injection
- Location: `backend/app/api/middleware/`
- Contains:
  - `error_handler.py` — Standardizes all error responses (catches HTTPException, validation errors, DB errors)
  - `rate_limiter.py` — Per-IP/per-user rate limiting (disabled in tests by default)
  - `request_context.py` — Injects request_id and user_id into log context
  - `crawl_upload_body_limit.py` — Rejects oversized Content-Length from extension uploads before heavier processing
- Depends on: FastAPI middleware hooks, SQLAlchemy exceptions, logging
- Used by: `main.py` registers all middleware on app startup

**Endpoint Layer (Routers):**
- Purpose: HTTP request validation, dependency injection, response serialization
- Location: `backend/app/api/endpoints/`
- Contains: One router file per domain (e.g., `users.py`, `build_lists.py`, `parts.py`, `votes.py`)
- Pattern: Most use `BaseEndpointRouter` to register standard CRUD operations (GET, POST, PUT, DELETE, count, list)
- Depends on: `BaseCRUDService`, `BaseVoteRouter`, `BaseReportRouter`, schemas (Pydantic), auth dependencies
- Used by: Registered in `main.py` via `EndpointRegistry.register_crud_endpoint()` or `register_endpoint()`

**Service Layer:**
- Purpose: Business logic, validation, authorization checks, database queries
- Location: `backend/app/api/services/`
- Contains: One service per domain (e.g., `user_service.py`, `build_list_service.py`)
- Pattern: Most extend `BaseCRUDService` for standard CRUD (create, read, update, delete, list)
- Special: `BaseVoteService`, `BaseReportService` — polymorphic services handling multiple entity types
- Depends on: SQLAlchemy models, authorization utilities, common operations
- Used by: Endpoints call service methods, passing db session and current user

**Model Layer (ORM):**
- Purpose: Data persistence schema via SQLAlchemy 2.0
- Location: `backend/app/api/models/`
- Contains: 25+ models (User, BuildList, Part, Vote, Report, etc.)
- Pattern: SQLAlchemy declarative base; relationships use lazy=select and joinedload for optimization
- Special: Polymorphic votes/reports via `base_*_id`/`base_*_type` pattern (single Vote table for all entities)
- Depends on: SQLAlchemy core/ORM
- Used by: Services query models, endpoints serialize to schemas

**Schema Layer (Validation & Serialization):**
- Purpose: Request validation (Pydantic) and response serialization
- Location: `backend/app/api/schemas/`
- Contains: One schema file per domain with Create/Read/Update variants (e.g., `BuildListCreate`, `BuildListRead`)
- Pattern: Pydantic v2; read schemas can nest other schemas (e.g., `BuildListReadWithVotes` includes vote summaries)
- Depends on: Pydantic validators
- Used by: Endpoints use as request/response_model, services deserialize via `model_dump()`

**Database Layer:**
- Purpose: SQL persistence, transactions, migrations
- Location: `backend/app/db/session.py` (session factory), `backend/alembic/versions/` (migration history)
- Pattern: SQLAlchemy session management via `get_db()` dependency; migrations auto-generated
- Depends on: PostgreSQL 16 (production), SQLite in-memory (tests)
- Used by: Services get session from `Depends(get_db)`

## Data Flow

**Request → Response:**

1. **Middleware chain** (top to bottom):
   - `request_context_middleware` — Assigns request_id, extracts user_id into context
   - `crawl_upload_content_length_middleware` — Rejects oversized extension uploads
   - `rate_limit_middleware` — Checks rate limits per IP/user
   - `error_handler_middleware` — Wraps entire chain to catch exceptions

2. **Endpoint routing:**
   - `EndpointRegistry` registers routers with FastAPI app
   - FastAPI matches HTTP method/path to endpoint function
   - Dependency injection (auth, db session, logger) happens here via `Depends()`

3. **Service layer call:**
   - Endpoint passes db session, current user, and Pydantic schema to service method
   - Service validates business logic (ownership, authorization, existence checks)
   - Service calls SQLAlchemy model methods or queries

4. **Database transaction:**
   - Service queries/modifies ORM models
   - Changes flush to pending state in session
   - Session commits or rolls back on exception

5. **Response:**
   - Service returns model instance to endpoint
   - Endpoint serializes via response_model (Pydantic schema)
   - Error handler catches any HTTPException and standardizes response
   - Middleware logs request/response

**Example: Create a build list**

```
POST /api/build-lists
  → Header: Authorization: Bearer <token>
  → Body: { "name": "...", "description": "...", "car_generation_id": "..." }
    ↓
  Middleware validates token, extracts user_id, checks rate limit
    ↓
  Endpoint: build_lists.py → create_build_list(data: BuildListCreate, current_user, db)
    ↓
  Service: BuildListService.create()
    - Validate car_generation exists
    - Check user ownership of car_generation
    - Create BuildList(name, description, user_id, car_generation_id)
    - db.add(build_list); db.commit()
    ↓
  Response: { "id": "...", "name": "...", "user_id": "...", ... } (BuildListRead schema)
```

**State Management:**

- **Backend:** Database is source of truth; no in-memory caching for user data (rate limits are cached in-memory per worker)
- **Frontend:** React context (AuthContext, AppSettingsContext) + local component state
- **Session:** JWT token valid 15 min–7 days (user-configurable, clamped by server)
- **Authentication:** Email verification required before first login; optional 2FA (TOTP) and WebAuthn

## Key Abstractions

**BaseEndpointRouter:**
- Purpose: Generic CRUD endpoint registration (list, create, get, update, delete, count)
- Example: `backend/app/api/utils/base_endpoint_router.py` (300+ lines)
- Pattern: Accepts service + router + entity_name; registers standardized endpoints
- Usage: `build_lists.py` uses `BaseEndpointRouter(service=build_list_service, router=router, ...)`
- Benefit: Eliminates boilerplate; endpoint logic reduced from ~500 lines to ~100

**BaseCRUDService:**
- Purpose: Generic CRUD service implementation (create, read, update, delete, list, count)
- Example: `backend/app/api/services/base_crud_service.py` (200+ lines)
- Pattern: Accepts model class + entity_name; implements all standard operations
- Delegates heavy lifting to `common_operations.py` (validate pagination, verify ownership, etc.)
- Usage: `BuildListService(BaseCRUDService)` inherits create/read/update/delete; adds business logic in overrides

**BaseVoteRouter & BaseVoteService:**
- Purpose: Polymorphic voting system (one endpoint handles votes on any entity type)
- Example: `backend/app/api/utils/base_vote_router.py`, `backend/app/api/services/base_vote_service.py`
- Pattern: Entity type + entity_id passed as params; service queries via `base_*_type`/`base_*_id` columns
- Usage: `POST /api/votes` with `{ "base_part_id": "...", "vote_type": "up" }` or `{ "base_build_list_id": "...", "vote_type": "down" }`
- Benefit: Single endpoint supports votes on parts, build lists, build logs, users, etc. without duplication

**BaseReportRouter & BaseReportService:**
- Purpose: Polymorphic reporting system (same pattern as votes)
- Usage: `POST /api/reports` with `{ "base_build_list_id": "...", "reason": "spam" }`

**RetailerCrawlerAdapter:**
- Purpose: Per-retailer product scraping
- Example: `backend/app/crawlers/adapters/base.py` (abstract base class)
- Pattern: Subclass and implement `discover_product_urls()` and `parse_product_page(html, url)`
- Tiers: Three fetcher tiers (`"http"`, `"tls"`, `"browser"`) for different anti-scraping tactics
- Usage: Adapter registered in `backend/app/crawlers/adapters/__init__.py`; runner executes via CLI

**EndpointRegistry:**
- Purpose: Standardized router registration with documentation
- Example: `backend/app/api/utils/endpoint_registry.py` (100 lines)
- Pattern: Call `endpoint_registry.register_crud_endpoint()` or `register_endpoint(prefix, router, ...)`
- Benefit: OpenAPI docs auto-generated with entity_name and description

**Common Patterns & Utilities:**
- `common_operations.py` — Shared validation (verify_entity_exists, verify_entity_ownership, get_entities_with_pagination)
- `common_patterns.py` — Standard filter/sort/pagination logic for list endpoints
- `response_patterns.py` — Standardized response wrappers (success, error, paginated)
- `authorization.py` — Permission checks (is_owner, is_admin, subscription checks)

## Entry Points

**Backend:**
- Location: `backend/app/main.py`
- Triggers: `uvicorn app.main:app --reload` (dev) or App Runner deployment (prod)
- Responsibilities:
  - Creates FastAPI app with lifespan hook
  - Registers middleware (CORS, rate limit, request context, error handler)
  - Initializes service accounts, crawler configs, car generations on startup
  - Registers all endpoint routers via EndpointRegistry
  - Defines `/`, `/health`, `/ready` health check endpoints

**Frontend:**
- Location: `frontend/src/main.tsx`
- Triggers: `npm run dev` or Vite build output loaded in browser
- Responsibilities:
  - Creates React root and mounts App component
  - Wraps with providers (GoogleOAuthProvider, BrowserRouter, AuthProvider, AppSettingsProvider, ErrorBoundary)
  - Loads root page element from `frontend/index.html`

**Chrome Extension (Content Script):**
- Location: `chrome-extension/src/content.ts`
- Triggers: On page load for URLs matching extension's content_scripts manifest
- Responsibilities:
  - Injects scraper UI into retailer product pages
  - Extracts product data (price, name, image, specifications)
  - Posts to `POST /api/crawled-pages` with HTML + extracted JSON

**Chrome Extension (Popup):**
- Location: `chrome-extension/src/main-popup.tsx` + `chrome-extension/src/pages/popup.tsx`
- Triggers: User clicks extension icon
- Responsibilities:
  - Shows login screen or main UI (search parts, record prices, create build lists)
  - Communicates with background script for persistent auth/API calls

## Error Handling

**Strategy:** Centralized middleware catches all exceptions and returns standardized JSON responses

**Patterns:**

1. **HTTPException** (explicit errors from endpoints):
   - Code: `raise HTTPException(status_code=404, detail="Build list not found")`
   - Caught by `error_handler_middleware` and serialized to `{ "success": false, "message": "...", "error_code": "..." }`

2. **Validation Errors** (Pydantic):
   - Caught by error middleware and converted to 422 with field-level detail

3. **Database Errors** (SQLAlchemy):
   - `OperationalError` (connection lost) → 503 Service Unavailable
   - Other errors → 500 Internal Server Error with generic message (real error logged server-side)

4. **Rate Limit Exceeded:**
   - Returns 429 Too Many Requests with Retry-After header

5. **Authorization Failures:**
   - Invalid/expired JWT → 401 Unauthorized
   - Missing required role (admin, superuser) → 403 Forbidden
   - Insufficient subscription tier → 403 with `error_code: "SUBSCRIPTION_REQUIRED"`

**Frontend error handling:**
- Components wrapped in `ErrorBoundary` catch React rendering errors
- API client (`services/Api.ts`) wraps axios calls and retries on specific errors
- User-facing errors shown via toast notifications or error cards

## Cross-Cutting Concerns

**Logging:**
- Tool: Python `logging` module (FastAPI + Uvicorn)
- Pattern: Structured logging with request_id/user_id context injected into every log line
- Location: `backend/app/core/logging.py` (formatter) + `backend/app/core/log_context.py` (context filter)
- Levels: INFO (default), DEBUG (dev only), WARNING (errors), ERROR (exceptions)

**Validation:**
- Pydantic schemas in endpoints for request validation
- Services validate business rules (ownership, existence, authorization)
- Custom validators in schemas (e.g., name length, email format)
- `common_operations.py` provides reusable checks (verify_entity_exists, verify_entity_ownership)

**Authentication:**
- JWT (HS256, configurable expiry) + bcrypt passwords
- Email verification required before first login
- Optional 2FA: TOTP (time-based one-time password) or WebAuthn (passkey)
- OAuth: Google sign-in/signup/link account
- Location: `backend/app/api/endpoints/auth.py` (large, handles all auth flows)

**Authorization:**
- Role-based: user, admin, superuser
- Owner-based: users own their build lists, cars, etc.
- Subscription-based: premium features gated by subscription tier (handled in endpoints via `verify_subscription()`)
- Location: `backend/app/api/utils/authorization.py` + dependencies in `backend/app/api/dependencies/auth.py`

**Pagination:**
- Query params: `skip` (default 0) and `limit` (default 20, max 1000)
- Response: `{ "data": [...], "total": N, "skip": S, "limit": L }`
- Location: `backend/app/api/utils/pagination_utils.py`
- Used by: All list endpoints via `common_patterns.apply_standard_filters()`

**Image Handling:**
- Upload: S3 via boto3; presigned URLs for serving
- Processing: Pillow for resizing/validation
- Deletion: S3 delete when image_source rows removed
- Location: `backend/app/api/endpoints/images.py` + `backend/app/api/services/storage_service.py`

**Voting & Reporting:**
- Polymorphic design: single vote/report table with base_*_type and base_*_id columns
- Vote endpoints: `POST /api/votes`, `DELETE /api/votes/{vote_id}`, `GET /api/votes/summary/{base_entity_type}/{entity_id}`
- Report endpoints: identical pattern
- Location: `backend/app/api/endpoints/votes.py`, `backend/app/api/endpoints/reports.py`

**Rate Limiting:**
- Per-IP and per-user buckets (token bucket algorithm)
- Rates: Configurable per endpoint (default: 100 req/min)
- Disabled in tests unless `ENABLE_RATE_LIMITING=true` set
- Location: `backend/app/api/middleware/rate_limiter.py`

**Crawler System:**
- Discovery: Adapters implement `discover_product_urls()` (sitemaps, category listings, etc.)
- Parsing: Adapters implement `parse_product_page(html, url)` → ScrapedPayload
- Fetching: Three tiers (HTTP, TLS-fingerprint, headless browser) handle anti-scraping
- Scheduling: EventBridge schedules trigger crawler via Lambda/ECS; results ingested via POST to backend
- Extension: Content scripts scrape retailer pages in-browser, POST HTML + JSON to `POST /api/crawled-pages`
- Location: `backend/app/crawlers/` + `chrome-extension/src/content.ts`

---

*Architecture analysis: 2026-04-22*
