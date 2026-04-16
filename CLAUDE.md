# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CarModPicker is a full-stack web application for managing car modifications. Users can track their cars, create build lists with parts, browse a global parts catalog, and log their builds in forum-style threads. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) backend + React 19 (TypeScript) frontend + PostgreSQL, deployed on AWS (App Runner + RDS). Infrastructure managed with Terraform (`terraform/`).

---

## Commands

### Backend (`backend/`)

```bash
# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Database (requires Docker)
docker-compose up -d      # start PostgreSQL
docker-compose down       # stop

# Migrations — always use autogenerate, never write manually
alembic revision --autogenerate -m "description"
alembic upgrade head

# Tests — always run with -n auto for parallel execution
# Tests use SQLite in-memory (not PostgreSQL) — no DB setup required
pytest -n auto
pytest -n auto --cov=app --cov-report=term-missing
pytest -n auto path/to/test_file.py       # single file
pytest -n auto -k "test_name"             # single test
# Rate limiting is disabled in tests by default; set ENABLE_RATE_LIMITING=true to test it

# Populate local DB with sample data
python ../scripts/populate_sample_data.py   # run from backend/

# Linting / formatting
black --config pyproject.toml .
isort .
pyright
bandit -r app

# Crawler (run from backend/)
python -m app.crawlers --adapter <name> [--limit N] [--delay SEC]
# Required env: CRAWLER_USER_ID, CRAWLER_DEFAULT_CATEGORY_NAME
```

### Frontend (`frontend/`)

```bash
npm run dev           # dev server on port 4000 (proxies /api to backend)
npm run dev:staging   # use staging API
npm run dev:prod      # use production API
npm run build         # tsc -b && vite build
npm run lint          # eslint
npm run type-check    # tsc --noEmit
npm test              # vitest
npm run test:coverage
```

### Chrome Extension (`chrome-extension/`)

```bash
npm run build   # production build → dist/
npm run watch   # auto-rebuild on change (then reload in chrome://extensions/)
```

---

## Architecture

### Request flow

```
Browser / Chrome Extension
    → React frontend (port 4000, dev proxy /api → 8000)
    → FastAPI backend (port 8000, prefix /api)
    → PostgreSQL (Docker locally, RDS PostgreSQL 16 in prod)
```

### Backend (`backend/app/`)

- **`main.py`** — App factory: registers all routers via `EndpointRegistry`, adds CORS, rate-limiting, and error-handler middleware. The `lifespan` hook initializes a crawler service account on startup.
- **`api/endpoints/`** — One file per domain (`auth`, `users`, `cars`, `global_parts`, `build_lists`, `build_list_parts`, `build_list_phases`, `build_logs`, `votes`, `reports`, `images`, `search`, `admin`, `crawled_pages`, `brands`, `categories`, `retailers`, `bug_reports`).
- **`api/models/`** — SQLAlchemy 2.0 ORM models (22+ tables).
- **`api/schemas/`** — Pydantic v2 request/response schemas.
- **`api/services/`** — Business logic layer called by endpoints.
- **`api/dependencies/auth.py`** — FastAPI `Depends()` helpers: `get_current_user`, `get_optional_current_user`, `get_current_admin_user`, `get_current_superuser`.
- **`api/middleware/`** — Rate limiting + content-length guard + error handlers.
- **`api/utils/`** — Shared patterns: `BaseEndpointRouter` (generic CRUD router), `BaseCRUDService`, `EndpointRegistry` (standardized router registration), `base_vote_router`, `base_report_router`, pagination, authorization, subscription checks.
- **`crawlers/`** — Per-retailer scraping system. Subclass `RetailerCrawlerAdapter`, implement `discover_product_urls()` and `parse_product_page()`, register in `adapters/__init__.py`.
- **`core/`** — Config, logging, email templates (React Email HTML, sent via SES), car/category seed data.
- **`alembic/versions/`** — Migration history (never edit manually).

**Auth:** JWT (HS256, configurable expiry 15 min–7 days per user preference) + bcrypt passwords + optional TOTP 2FA. Requires email verification before login is allowed. Email sent via AWS SES with IAM role auth.

**Images:** Uploaded to S3 (`carmodpicker-prod-user-images`, private) via boto3; presigned URLs used for serving. Pillow used for processing.

**Special endpoints:**
- `GET /health` — liveness check (always 200)
- `GET /ready` — readiness check (503 until DB is reachable; used during App Runner cold start)

### Backend patterns

Most endpoints are built on `BaseEndpointRouter` (generic CRUD over `BaseCRUDService`) rather than hand-rolled route functions. When adding a new domain, follow this pattern instead of writing boilerplate. Votes and reports use `base_vote_router` / `base_report_router` — both are polymorphic and handle all entity types through a unified endpoint.

### Frontend (`frontend/src/`)

- **`pages/`** — Route-level components (lazy-loaded).
- **`components/`** — Shared UI components.
- **`api/`** — Axios-based API client modules (one per backend domain).
- **`contexts/`** — React contexts (auth, user state).
- **`hooks/`** — Custom React hooks.
- React Router 7 for routing; Tailwind CSS 4 for styling.
- **Subscription tiers** gate features and ad display.

### Chrome Extension (`chrome-extension/src/`)

Content scripts scrape product data from retailer pages and POST to the backend API. Files that need an extension reload in `chrome://extensions/`: `manifest.json`, `background.ts`, `popup.html/css`. Content/popup/options scripts auto-update on next page load / popup reopen.

---

## Key Conventions

- **Alembic migrations:** Always use `alembic revision --autogenerate`. Never write migration files by hand.
- **pytest:** Always pass `-n auto` for parallel execution. Tests use SQLite in-memory — no Postgres required.
- **New CRUD endpoints:** Extend `BaseEndpointRouter` + `BaseCRUDService`; register with `EndpointRegistry` in `main.py`.
- The backend CORS config explicitly allows `chrome-extension://` origins and `null` (for service workers).
