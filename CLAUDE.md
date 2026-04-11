# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CarModPicker is a full-stack web application for managing car modifications. Users can track their cars, create build lists with parts, browse a global parts catalog, and log their builds in forum-style threads. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) backend + React 19 (TypeScript) frontend + PostgreSQL, deployed on AWS (App Runner + RDS).

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
pytest -n auto
pytest -n auto --cov=app --cov-report=term-missing
pytest -n auto path/to/test_file.py       # single file
pytest -n auto -k "test_name"             # single test

# Linting / formatting
black --config pyproject.toml .
isort .
pyright
bandit -r app
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
npm run watch   # auto-rebuild on change
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

- **`main.py`** — App factory: registers all 21 routers, CORS, rate-limiting, and error-handler middleware.
- **`routers/`** — One file per domain (`auth`, `users`, `cars`, `global_parts`, `build_lists`, `build_list_parts`, `build_list_phases`, `build_logs`, `votes`, `reports`, `images`, `search`, `admin`, etc.).
- **`models/`** — SQLAlchemy 2.0 ORM models (20+ tables).
- **`schemas/`** — Pydantic v2 request/response schemas.
- **`services/`** — Business logic layer called by routers.
- **`dependencies/`** — FastAPI `Depends()` helpers (DB session, current user, auth).
- **`middleware/`** — Rate limiting + error handlers.
- **`alembic/versions/`** — Migration history (never edit manually).
- **`static_assets/`** — Seed data (manufacturers, categories).

**Auth:** JWT (HS256, configurable expiry 15 min–7 days) + bcrypt passwords + optional TOTP 2FA. Email verification and password reset via AWS SES (boto3, IAM role auth, React Email HTML templates in `backend/app/core/email_templates/`).

**Images:** Uploaded to S3 (`carmodpicker-prod-user-images`, private) via boto3; presigned URLs used for serving. Pillow used for processing.

### Frontend (`frontend/src/`)

- **`pages/`** — Route-level components (lazy-loaded).
- **`components/`** — Shared UI components.
- **`api/`** — Axios-based API client modules (one per backend domain).
- **`contexts/`** — React contexts (auth, user state).
- **`hooks/`** — Custom React hooks.
- React Router 7 for routing; Tailwind CSS 4 for styling.

### Chrome Extension (`chrome-extension/src/`)

- Content scripts scrape product data from retailer pages and POST to the backend API to create parts.

---

## Key Conventions

- **Alembic migrations:** Always use `alembic revision --autogenerate`. Never write migration files by hand.
- **pytest:** Always pass `-n auto` for parallel execution.
- **Votes and reports** are polymorphic — the `votes` and `reports` routers handle all entity types through a unified endpoint.
- **Subscription tiers** gate features and ad display in the frontend.
- The backend CORS config explicitly allows `chrome-extension://` origins and `null` (for service workers).
