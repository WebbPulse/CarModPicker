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

- **`main.py`** — App factory: registers all routers via `EndpointRegistry`, adds CORS, rate-limiting, and error-handler middleware.
- **`api/endpoints/`** — One file per domain (`auth`, `users`, `car_generations`, `parts`, `build_lists`, `build_list_parts`, `build_list_phases`, `build_logs`, `votes`, `reports`, `images`, `search`, `admin`, `crawled_pages`, `part_manufacturers`, `categories`, `retailers`, `bug_reports`).
- **`api/models/`** — SQLAlchemy 2.0 ORM models (22+ tables).
- **`api/schemas/`** — Pydantic v2 request/response schemas.
- **`api/services/`** — Business logic layer called by endpoints.
- **`api/dependencies/auth.py`** — FastAPI `Depends()` helpers: `get_current_user`, `get_optional_current_user`, `get_current_admin_user`, `get_current_superuser`.
- **`api/middleware/`** — Rate limiting + content-length guard + error handlers.
- **`api/utils/`** — Shared patterns: `BaseEndpointRouter` (generic CRUD router), `BaseCRUDService`, `EndpointRegistry` (standardized router registration), `base_vote_router`, `base_report_router`, pagination, authorization, subscription checks.
- **`core/`** — Config, logging, email templates (React Email HTML, sent via SES), car/category seed data.
- **`backend/app/core/sentry.py`** — Sentry SDK 2.x init helper. Env-gated (TESTING+APP_ENVIRONMENT+DSN). Scope processor reads request_id/user_id from log_context ContextVars.
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

## Branching and deploys

```
feature/* ──PR──▶ staging ──PR──▶ main
                     │              │
                     ▼              ▼
           AWS 748861776298   AWS 734702670403
              (staging)          (production)
```

- Branch new work from `staging`, not `main`. PR into `staging`. Releasing is a PR from `staging` into `main` — that PR is the release boundary.
- Never commit directly to `main` or `staging`. Never force-push either. Stacked PRs bottom out on `staging`.
- Hotfixes branch from `main` and PR into `main`, then are immediately back-merged `main` → `staging`. Skipping the back-merge is how the branches silently diverge.
- Both accounts are `us-west-2`. Terraform Cloud org is `WebbPulse`.

**Protection is enforced by rulesets, with one bypass.** The WebbPulse org is on the GitHub Team plan, and repository rulesets cover both `main` and `staging`: pull request required, force-push and deletion blocked. The repository-admin role can bypass them, so the rulesets stop mistakes, not a determined admin. The real gate is Terraform Cloud manual apply on the production workspace: a merge cannot change AWS, only an apply can. CI runs on every PR but is not blocking — you have to read it.

### Workflows

Six workflows in `.github/workflows/`, three CI and three deploy, each scoped by path. All six are `main`-only today.

| Workflow | Trigger today | Paths |
|---|---|---|
| `backend-ci.yml` | `pull_request` → `main` | `backend/**` |
| `frontend-ci.yml` | `pull_request` → `main` | `frontend/**` |
| `chrome-extension-ci.yml` | `pull_request` → `main` | `chrome-extension/**` |
| `backend-deploy.yml` | `push` → `main` | `backend/**` |
| `frontend-deploy.yml` | `push` → `main` | `frontend/**` |
| `chrome-extension-deploy.yml` | `push` → `main` | `chrome-extension/**` |

The three deploy workflows are fully independent — a backend merge never rebuilds the frontend.

**What has to change when `staging` exists.** The three CI workflows need `staging` added to `pull_request: branches:`, or PRs into `staging` run no checks at all. `backend-deploy.yml` and `frontend-deploy.yml` need `staging` added to `push: branches:` and their hardcoded `environment: production` selected from the branch instead. Both also hardcode `TFC_WORKSPACE_ID: ws-oh1VvpTBPxmcrSYD`, and `frontend-deploy.yml` hardcodes `VITE_API_URL: https://api.carmodpicker.com` — both must become per-environment before a staging push is safe.

**`chrome-extension-deploy.yml` stays `main`-only.** It publishes to the Chrome Web Store, not to AWS: patch-bump `manifest.json`, tag `chrome-extension-vX.Y.Z`, cut a GitHub Release, upload and publish the zip via the CWS API. A browser extension has no staging-account equivalent and there is no staging store listing, so a `staging` trigger would have nothing to deploy to. It is also the one sanctioned exception to "never commit directly to `main`" — it pushes its own version bump with `git push origin HEAD:main`.

### Environment-scoped variables

Deploy variables are **environment-scoped**: `AWS_DEPLOY_ROLE_ARN`, `APP_RUNNER_SERVICE_ARN`, `CLOUDFRONT_DISTRIBUTION_ID`, `ECR_REPOSITORY_NAME` and `FRONTEND_S3_BUCKET` live on the `production` GitHub Environment, not the repository, so a `staging` push cannot silently pick up the production role. The workflows already declare `environment:`; a staging deploy needs a `staging` GitHub Environment (only `production` exists) with the same variables defined for the staging account.

| Workflow | Variables | Secrets |
|---|---|---|
| `backend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `ECR_REPOSITORY_NAME`, `APP_RUNNER_SERVICE_ARN` | `TFC_API_TOKEN` |
| `frontend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `FRONTEND_S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `CWS_EXTENSION_ID` | `TFC_API_TOKEN` |
| `chrome-extension-deploy.yml` | `CWS_CLIENT_ID`, `CWS_EXTENSION_ID` | `CWS_CLIENT_SECRET`, `CWS_REFRESH_TOKEN` |

The backend and frontend deploys poll the HCP Terraform runs API with `TFC_API_TOKEN` and wait for the workspace to reach a terminal state before touching App Runner or S3 — that poll is what prevents the App Runner `OPERATION_IN_PROGRESS` error when Terraform is mid-apply. A staging deploy must poll the staging workspace, not `ws-oh1VvpTBPxmcrSYD`.

### A staging branch does not imply staging infrastructure

`terraform/` is a single HCP workspace, `CarModPicker`, pinned in the `cloud` block in `versions.tf`. `var.environment` already validates `production | staging` and feeds `local.prefix`, but no staging workspace exists yet and `apprunner.tf` still hardcodes `APP_ENVIRONMENT = "production"`. Declare CarModPicker's staging profile (`none` / `reduced` / `full`) before assuming there is anything in 748861776298 to deploy to. Staging is never auto-provisioned to mirror production.

---

## Key Conventions

- **Alembic migrations:** Always use `alembic revision --autogenerate`. Never write migration files by hand.
- **pytest:** Always pass `-n auto` for parallel execution. Tests use SQLite in-memory — no Postgres required.
- **New CRUD endpoints:** Extend `BaseEndpointRouter` + `BaseCRUDService`; register with `EndpointRegistry` in `main.py`.
- The backend CORS config explicitly allows `chrome-extension://` origins and `null` (for service workers).
