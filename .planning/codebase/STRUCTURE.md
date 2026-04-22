# Codebase Structure

**Analysis Date:** 2026-04-22

## Directory Layout

```
/home/tyler-webb/Documents/Github/CarModPicker/
├── backend/                       # FastAPI application (Python 3.13)
│   ├── app/
│   │   ├── main.py               # App factory; middleware + router registration
│   │   ├── api/
│   │   │   ├── endpoints/         # One router file per domain
│   │   │   ├── services/          # Business logic layer
│   │   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── schemas/           # Pydantic request/response schemas
│   │   │   ├── middleware/        # HTTP middleware (error, rate limit, context)
│   │   │   ├── dependencies/      # FastAPI dependency injection (auth, db)
│   │   │   └── utils/             # Shared patterns (base routers, common ops)
│   │   ├── db/
│   │   │   └── session.py         # SQLAlchemy session factory
│   │   ├── services/              # Domain services (job_service, crawler_schedule_service)
│   │   ├── crawlers/              # Product scraping system
│   │   │   ├── adapters/          # Per-retailer crawler implementations
│   │   │   └── fetchers.py        # HTTP/TLS/browser fetch layer
│   │   └── core/                  # Configuration, logging, email templates
│   ├── alembic/
│   │   └── versions/              # Migration history (auto-generated)
│   ├── tests/                     # Pytest test suite
│   ├── pyproject.toml             # Poetry deps + tool config
│   └── docker-compose.yml         # Local PostgreSQL
│
├── frontend/                      # React 19 + TypeScript
│   ├── src/
│   │   ├── main.tsx               # App entrypoint; provider setup
│   │   ├── App.tsx                # Root router setup
│   │   ├── pages/                 # Route-level components (lazy-loaded)
│   │   ├── components/            # Reusable UI components
│   │   ├── services/
│   │   │   └── Api.ts             # Axios API client (all endpoints)
│   │   ├── contexts/              # React context providers
│   │   ├── hooks/                 # Custom React hooks
│   │   ├── types/
│   │   │   └── Api.ts             # TypeScript interfaces for API responses
│   │   ├── utils/                 # Utility functions
│   │   ├── assets/                # Images, icons
│   │   └── constants/             # App constants
│   ├── index.html                 # HTML template
│   ├── vite.config.ts             # Vite bundler config
│   ├── tsconfig.json              # TypeScript config
│   └── package.json               # npm dependencies
│
├── chrome-extension/              # Chrome extension for retailer scraping
│   ├── src/
│   │   ├── content.ts             # Content script (runs in page context)
│   │   ├── background.ts          # Background script (persistent)
│   │   ├── main-popup.tsx          # Popup React entry point
│   │   ├── main-options.tsx        # Options page React entry point
│   │   ├── pages/
│   │   │   ├── popup.tsx           # Popup UI
│   │   │   └── options.tsx         # Options page UI
│   │   ├── components/            # Extension UI components
│   │   ├── utils/                 # Helpers (image URL parsing, etc.)
│   │   └── types/                 # TypeScript interfaces
│   ├── manifest.json              # Chrome extension manifest
│   ├── public/
│   │   ├── popup.html
│   │   └── options.html
│   ├── tsconfig.json
│   └── package.json
│
├── terraform/                     # Infrastructure as Code (AWS)
│   ├── apprunner.tf               # AWS App Runner service (backend)
│   ├── rds.tf                     # RDS PostgreSQL
│   ├── s3.tf                      # S3 buckets (images, frontend, etc.)
│   ├── cloudfront.tf              # CloudFront distribution
│   ├── ecs.tf                     # ECS for background jobs
│   ├── scheduler.tf               # EventBridge for crawler schedules
│   ├── iam_github_actions.tf      # GitHub Actions IAM role
│   ├── ses.tf                     # SES for email
│   └── variables.tf               # Input variables
│
├── scripts/                       # Utility scripts
│   ├── populate_sample_data.py    # Load test data into local DB
│   └── ...
│
├── docs/                          # Documentation
├── email-templates/               # Email template HTML (React Email)
└── .planning/
    └── codebase/                  # GSD codebase maps (this file goes here)
```

## Directory Purposes

**Backend Directories:**

**`backend/app/api/endpoints/`:**
- Purpose: HTTP route handlers (one file per domain)
- Contains: Router files using `BaseEndpointRouter` or custom endpoint functions
- Key files: `users.py`, `build_lists.py`, `parts.py`, `auth.py`, `admin.py`, `votes.py`, `reports.py`
- Pattern: Each file creates an `APIRouter`, optionally wraps with `BaseEndpointRouter`, exports `router`

**`backend/app/api/services/`:**
- Purpose: Business logic and database queries (one service per domain)
- Contains: Service classes extending `BaseCRUDService` or specialized services
- Key files: `build_list_service.py`, `user_service.py`, `crawler_schedule_service.py`, `vote_service.py`
- Pattern: Services receive db session, validate ownership/authorization, call model methods

**`backend/app/api/models/`:**
- Purpose: SQLAlchemy ORM model definitions
- Contains: One model per domain entity (User, BuildList, Part, Vote, etc.)
- Key files: `user.py`, `build_list.py`, `part.py`, `vote.py`, `report.py`
- Pattern: SQLAlchemy declarative; relationships use `relationship()` + lazy strategies
- Special: Polymorphic votes/reports use `base_*_id` + `base_*_type` for single-table inheritance

**`backend/app/api/schemas/`:**
- Purpose: Pydantic v2 request/response validation and serialization
- Contains: One schema file per domain with Create/Read/Update variants
- Key files: `user.py` (UserCreate, UserRead, UserUpdate), `build_list.py`, `part.py`
- Pattern: Read schemas often nest other schemas (e.g., BuildListReadWithVotes includes VoteSummary)

**`backend/app/api/middleware/`:**
- Purpose: HTTP middleware for request/response processing
- Contains:
  - `error_handler.py` — Catches all exceptions, returns standardized error responses
  - `rate_limiter.py` — Per-IP/per-user rate limiting
  - `request_context.py` — Injects request_id/user_id into logging context
  - `crawl_upload_body_limit.py` — Rejects oversized extension uploads early
- Pattern: Each middleware registered in `main.py` via `app.middleware("http")(func)`

**`backend/app/api/dependencies/`:**
- Purpose: FastAPI dependency injection helpers
- Contains: `auth.py` (get_current_user, get_optional_current_user, JWT validation, password hashing)
- Pattern: Used in endpoints via `Depends(get_current_user)` to inject authenticated user

**`backend/app/api/utils/`:**
- Purpose: Shared utilities and base patterns
- Key files:
  - `base_endpoint_router.py` — Generic CRUD router (registers list, create, get, update, delete, count endpoints)
  - `base_crud_service.py` — Generic CRUD service implementation
  - `base_vote_router.py` / `base_vote_service.py` — Polymorphic voting
  - `base_report_router.py` / `base_report_service.py` — Polymorphic reporting
  - `common_operations.py` — Shared validation (verify_entity_exists, verify_ownership, pagination)
  - `common_patterns.py` — Standard filter/sort/search logic
  - `response_patterns.py` — Standardized response wrappers
  - `authorization.py` — Permission/subscription checks
  - `endpoint_registry.py` — Router registration with OpenAPI documentation

**`backend/app/db/`:**
- Purpose: Database session management
- Contains: `session.py` (SessionLocal factory, get_db dependency, check_db_ready health check)
- Pattern: Every endpoint gets db session via `Depends(get_db)`

**`backend/app/crawlers/`:**
- Purpose: Product scraping system
- Contains:
  - `base.py` — Abstract `RetailerCrawlerAdapter` base class
  - `adapters/__init__.py` — Registers all adapter subclasses
  - `adapters/tier0_http/`, `adapters/tier1_tls/`, `adapters/tier2_browser/` — Per-retailer implementations
  - `fetchers.py` — HTTP/TLS/browser fetch layer
  - `__main__.py` — CLI for running crawlers locally
- Pattern: Adapters implement `discover_product_urls()` and `parse_product_page(html, url)`

**`backend/app/core/`:**
- Purpose: Application configuration and initialization
- Contains:
  - `config.py` — Settings from environment variables
  - `logging.py` — Log formatter with colored levels
  - `log_context.py` — Request context filter (request_id, user_id)
  - `init_service_accounts.py` — Creates crawler service account on startup
  - `init_crawler_adapter_configs.py` — Loads per-retailer tuning
  - `init_cars.py` — Seeds car generation data
  - `email_templates/` — React Email HTML templates for password reset, email verification, etc.
- Pattern: All initialized in `main.py` lifespan hook

**`backend/alembic/`:**
- Purpose: Database schema migrations
- Contains: `versions/` directory with auto-generated migration files (never edit manually)
- Pattern: `alembic revision --autogenerate -m "description"` generates files based on model changes

**`backend/tests/`:**
- Purpose: Pytest test suite
- Contains: Unit and integration tests mirroring `app/` structure
- Pattern: Tests use SQLite in-memory database (no PostgreSQL setup required)
- Run: `pytest -n auto` (parallel execution)

---

**Frontend Directories:**

**`frontend/src/pages/`:**
- Purpose: Route-level components (one per major route/page)
- Contains: Lazy-loaded components imported in `App.tsx`
- Key files: `Home.tsx`, `Profile.tsx`, `builder/Builder.tsx`, `authentication/Login.tsx`, `admin/Admin.tsx`
- Pattern: Pages are code-split and loaded on-demand via `lazy()` wrapper

**`frontend/src/components/`:**
- Purpose: Reusable UI components
- Contains: Subdirectories by feature area (buildLists, parts, users, authentication, etc.)
- Pattern: PascalCase files; each file may export one or multiple components
- Key: `layout/` for header, footer, sidebar; `common/` for shared widgets

**`frontend/src/services/Api.ts`:**
- Purpose: Axios-based API client
- Contains: All API methods (users, parts, buildLists, auth, admin, etc.)
- Pattern: One method per endpoint; wraps axios calls with error handling and retry logic
- Environment: Reads `VITE_BACKEND`, `VITE_STAGING_API_URL`, `VITE_PROD_API_URL` to determine API base URL

**`frontend/src/contexts/`:**
- Purpose: React context providers (global state)
- Contains: `AuthContext.tsx` (current user, login/logout), `AppSettingsContext.tsx` (global ads toggle)
- Pattern: `useAuth()` hook for accessing auth state, `useAppSettings()` for app settings

**`frontend/src/hooks/`:**
- Purpose: Custom React hooks
- Contains: `useAuth()`, `useIsPremium()`, `usePaginatedData()`, etc.
- Pattern: Encapsulate state management and side effects

**`frontend/src/types/Api.ts`:**
- Purpose: TypeScript interfaces for API responses
- Contains: All Pydantic schema types (UserRead, BuildListRead, etc.)
- Pattern: Mirrors backend schema structure; imported by Api.ts and components

**`frontend/src/utils/`:**
- Purpose: Utility functions
- Contains: String formatting, date parsing, lazy loading, error handling helpers

**`frontend/src/constants/`:**
- Purpose: App-wide constants
- Contains: Subscription tiers, error codes, feature flags, etc.

**`frontend/src/assets/`:**
- Purpose: Static images, icons, fonts
- Pattern: Imported directly in components

---

**Chrome Extension Directories:**

**`chrome-extension/src/content.ts`:**
- Purpose: Content script (runs in page context on retailer websites)
- Responsibilities: Injects scraper UI, extracts product data, POSTs to backend
- Triggers: On page load for URLs matching manifest's content_scripts

**`chrome-extension/src/background.ts`:**
- Purpose: Background/service worker (persistent across tabs)
- Responsibilities: Handles message passing, auth token storage, background tasks

**`chrome-extension/src/pages/popup.tsx`:**
- Purpose: Extension popup UI
- Responsibilities: Search parts, record prices, create build lists, logout
- Triggers: User clicks extension icon

**`chrome-extension/src/pages/options.tsx`:**
- Purpose: Extension options page
- Triggers: User opens extension settings

**`chrome-extension/manifest.json`:**
- Purpose: Extension metadata and permissions
- Contains: Icon paths, version, content script URLs, host permissions

---

**Terraform Directories:**

**`terraform/apprunner.tf`:**
- Purpose: Backend service deployment
- Contains: App Runner service, auto-scaling rules, environment variables

**`terraform/rds.tf`:**
- Purpose: PostgreSQL database
- Contains: RDS instance, subnet group, security group

**`terraform/s3.tf`:**
- Purpose: S3 buckets for user images, frontend artifacts, etc.
- Contains: Bucket creation, CORS, lifecycle policies

**`terraform/cloudfront.tf`:**
- Purpose: CDN for frontend distribution
- Contains: Distribution config, cache behaviors, origin points

**`terraform/ecs.tf`:**
- Purpose: ECS cluster and tasks for background jobs
- Contains: Task definitions, container config

**`terraform/scheduler.tf`:**
- Purpose: EventBridge for crawler scheduling
- Contains: Scheduled rules that trigger crawlers

---

## Key File Locations

**Entry Points:**

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app factory; middleware + router registration |
| `frontend/src/main.tsx` | React DOM mount + provider setup |
| `frontend/src/App.tsx` | Root router (defines all routes) |
| `chrome-extension/src/content.ts` | Content script (retailer page scraper) |
| `chrome-extension/src/background.ts` | Background service worker |

**Configuration:**

| File | Purpose |
|------|---------|
| `backend/app/core/config.py` | Environment-based settings |
| `backend/pyproject.toml` | Python dependencies + Poetry config |
| `frontend/package.json` | npm dependencies |
| `frontend/vite.config.ts` | Vite bundler config |
| `chrome-extension/manifest.json` | Extension metadata |
| `terraform/variables.tf` | AWS resource variables |

**Core Logic:**

| File | Purpose |
|------|---------|
| `backend/app/api/endpoints/auth.py` | Authentication flows (JWT, OAuth, 2FA) |
| `backend/app/api/endpoints/users.py` | User CRUD, profile, preferences |
| `backend/app/api/endpoints/build_lists.py` | Build list CRUD |
| `backend/app/api/endpoints/parts.py` | Part catalog search/filter |
| `backend/app/api/services/build_list_service.py` | Build list business logic |
| `backend/app/api/models/user.py` | User ORM model |
| `backend/app/api/schemas/user.py` | User request/response schemas |

**Testing:**

| File | Purpose |
|------|---------|
| `backend/tests/test_main.py` | App startup tests |
| `backend/tests/services/test_build_list_service.py` | BuildListService unit tests |
| `backend/tests/crawlers/` | Crawler adapter tests |

---

## Naming Conventions

**Backend Files:**

- **Endpoint files:** `snake_case.py` (e.g., `build_lists.py`, `car_generations.py`)
- **Service files:** `snake_case_service.py` (e.g., `build_list_service.py`, `user_service.py`)
- **Model files:** `snake_case.py` (e.g., `build_list.py`, `car_generation.py`)
- **Schema files:** `snake_case.py` (e.g., `build_list.py`, `user.py`)
- **Utility files:** `snake_case.py` or `snake_case_utils.py` (e.g., `pagination_utils.py`)

**Backend Classes:**

- **Models:** `PascalCase` with DB-specific suffixes (e.g., `BuildList`, `CarGeneration`, `PartListing`)
- **Schemas:** `PascalCase` with variant suffixes (e.g., `BuildListCreate`, `BuildListRead`, `BuildListUpdate`)
- **Services:** `PascalCaseService` (e.g., `BuildListService`)
- **Routers:** `base_*_router.py` → `Base*Router` class (e.g., `BaseEndpointRouter`, `BaseVoteRouter`)

**Backend Functions:**

- **Route handlers:** `snake_case` (e.g., `create_build_list`, `update_user`)
- **Service methods:** `snake_case` (e.g., `verify_entity_exists`, `get_with_pagination`)

**Frontend Files:**

- **Page components:** `PascalCase.tsx` (e.g., `Home.tsx`, `Profile.tsx`, `builder/Builder.tsx`)
- **UI components:** `PascalCase.tsx` (e.g., `Button.tsx`, `Modal.tsx`, `Header.tsx`)
- **Hooks:** `useXxx.ts` (e.g., `useAuth.ts`, `usePaginatedData.ts`)
- **Services:** `camelCase.ts` (e.g., `api.ts`, `storage.ts`)
- **Utilities:** `camelCase.ts` (e.g., `formatters.ts`, `validators.ts`)
- **Types:** `camelCase.ts` (e.g., `types.ts`, `api.ts` for interfaces)

**Frontend Variables & Functions:**

- `camelCase` (e.g., `isLoading`, `handleClick`, `fetchBuildLists`)

**Chrome Extension Files:**

- Entry points: `snake_case.ts` (e.g., `content.ts`, `background.ts`)
- React components: `PascalCase.tsx` (e.g., `MainScreen.tsx`, `LoginScreen.tsx`)

---

## Where to Add New Code

**New API Endpoint (e.g., for a new entity Retailer):**

1. **Create service:** `backend/app/api/services/retailer_service.py`
   - Extend `BaseCRUDService[Retailer, RetailerCreate, RetailerRead, RetailerUpdate]`
   - Add business logic (validation, authorization) as needed

2. **Create model:** `backend/app/api/models/retailer.py`
   - Define SQLAlchemy ORM model with relationships

3. **Create schema:** `backend/app/api/schemas/retailer.py`
   - Define `RetailerCreate`, `RetailerRead`, `RetailerUpdate` Pydantic schemas

4. **Create endpoint:** `backend/app/api/endpoints/retailers.py`
   - Create router: `router = APIRouter()`
   - Create service: `retailer_service = RetailerService()`
   - Create base router: `BaseEndpointRouter(service=retailer_service, router=router, ...)`
   - Add custom endpoints if needed

5. **Register in main.py:** `backend/app/main.py`
   - Import the router: `from .api.endpoints import retailers`
   - Register: `endpoint_registry.register_crud_endpoint(retailers.router, ...)`

6. **Add migration:** 
   - `alembic revision --autogenerate -m "add retailer table"`

**New Frontend Page:**

1. Create page component: `frontend/src/pages/Retailers.tsx`
   - Use `useAuth()` for auth state
   - Use `Api.Retailers.*` for API calls
   - Implement routing in `App.tsx`

2. Add route in `frontend/src/App.tsx`:
   ```typescript
   const Retailers = lazy(() => import('./pages/Retailers.tsx'));
   // In Routes: <Route path="/retailers" element={<Retailers />} />
   ```

**New Component:**

1. Create component: `frontend/src/components/retailers/RetailerCard.tsx`
2. Import in pages/components that need it
3. Use TypeScript interfaces from `frontend/src/types/Api.ts`

**New Utility Function:**

- Backend: `backend/app/api/utils/retailer_utils.py` (if large) or add to existing `common_operations.py`
- Frontend: `frontend/src/utils/retailerHelpers.ts` or relevant existing file

**New Crawler Adapter (e.g., for FCP Europe):**

1. Create adapter: `backend/app/crawlers/adapters/tier0_http/fcp_europe.py` (or tier1_tls/tier2_browser based on difficulty)
2. Subclass `RetailerCrawlerAdapter`
3. Implement `discover_product_urls()` and `parse_product_page(html, url)`
4. Set `FETCHER_TIER` if needed (default is "http")
5. Register in `backend/app/crawlers/adapters/__init__.py`: `"fcp_europe": FCPEuropeAdapter`

---

## Special Directories

**`backend/alembic/versions/`:**
- Purpose: Migration history (auto-generated, never edit manually)
- Generated: Yes (via `alembic revision --autogenerate`)
- Committed: Yes (essential for schema reproduction)

**`backend/tests/`:**
- Purpose: Test suite
- Generated: No (developer-written)
- Committed: Yes (essential for CI/CD)
- Database: Uses in-memory SQLite (not PostgreSQL)

**`frontend/dist/`:**
- Purpose: Vite build output (bundled JS, CSS, etc.)
- Generated: Yes (via `npm run build`)
- Committed: No (.gitignore)

**`chrome-extension/dist/`:**
- Purpose: Built extension files
- Generated: Yes (via `npm run build`)
- Committed: No (.gitignore)

**`terraform/.terraform/`:**
- Purpose: Terraform working directory (downloaded providers, state)
- Generated: Yes (via `terraform init`)
- Committed: No (.gitignore)

**`terraform/.terraform.lock.hcl`:**
- Purpose: Terraform dependency lock file
- Generated: Yes (via `terraform init`)
- Committed: Yes (ensures reproducible Terraform runs)

**`backend/venv/` or `.venv/`:**
- Purpose: Python virtual environment
- Generated: Yes (via `python -m venv` or Poetry)
- Committed: No (.gitignore)

**`.env` files:**
- Purpose: Environment variables (secrets, config)
- Generated: Manual (never committed)
- Committed: No (.gitignore)
- Examples: `.env.local`, `.env.test`, `.env.production`

---

*Structure analysis: 2026-04-22*
