# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CarModPicker is a full-stack web application for managing car modifications. Users can track their cars, create build lists with parts, browse a global parts catalog, and log their builds in forum-style threads. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) backend + React 19 (TypeScript) frontend, deployed on AWS as Lambda + HTTP API + DynamoDB (the legacy App Runner + RDS PostgreSQL stack still runs in production until cutover). Infrastructure managed with Terraform (`terraform/`).

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

Six workflows in `.github/workflows/`, three CI and three deploy, each scoped by path.

| Workflow | Trigger | Paths |
|---|---|---|
| `backend-ci.yml` | `pull_request` → `main` | `backend/**` |
| `frontend-ci.yml` | `pull_request` → `main` | `frontend/**` |
| `chrome-extension-ci.yml` | `pull_request` → `main` | `chrome-extension/**` |
| `backend-deploy.yml` | `push` → `main`, `staging` | `backend/**` |
| `frontend-deploy.yml` | `push` → `main`, `staging` | `frontend/**` |
| `chrome-extension-deploy.yml` | `push` → `main` | `chrome-extension/**` |

The three deploy workflows are fully independent — a backend merge never rebuilds the frontend.

`backend-deploy.yml` and `frontend-deploy.yml` pick their GitHub Environment from the branch (`main` → `production`, otherwise `staging`) and read every deploy-time value from that Environment. The backend deploy builds a Lambda zip (`requirements-lambda.txt` resolved for manylinux x86_64 / Python 3.13, plus `app/`), uploads it to the artifacts bucket keyed by commit SHA, waits for HCP Terraform to go idle, then runs `update-function-code` and `publish-version`. The Docker/ECR/App Runner steps still run only while `APP_RUNNER_SERVICE_ARN` is set on the Environment.

**Still to change:** the three CI workflows only run on PRs into `main`; PRs into `staging` run no checks until `staging` is added to their `pull_request: branches:`.

**`chrome-extension-deploy.yml` stays `main`-only.** It publishes to the Chrome Web Store, not to AWS: patch-bump `manifest.json`, tag `chrome-extension-vX.Y.Z`, cut a GitHub Release, upload and publish the zip via the CWS API. A browser extension has no staging-account equivalent and there is no staging store listing, so a `staging` trigger would have nothing to deploy to. It is also the one sanctioned exception to "never commit directly to `main`" — it pushes its own version bump with `git push origin HEAD:main`.

### Environment-scoped variables

Deploy variables are **environment-scoped**: they live on the `production` and `staging` GitHub Environments, not the repository, so a `staging` push cannot silently pick up the production role. Nothing deploy-related is hardcoded in the workflows any more — the workspace id and the API URL are Environment variables too. Values come from the matching workspace's Terraform outputs (`terraform/README.md` maps each variable to its output).

| Workflow | Variables | Secrets |
|---|---|---|
| `backend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `TFC_WORKSPACE_ID`, `LAMBDA_FUNCTION_NAME`, `LAMBDA_ARTIFACTS_BUCKET`; production only: `ECR_REPOSITORY_NAME`, `APP_RUNNER_SERVICE_ARN` | `TFC_API_TOKEN` |
| `frontend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `TFC_WORKSPACE_ID`, `FRONTEND_S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `VITE_API_URL`, `CWS_EXTENSION_ID` | `TFC_API_TOKEN` |
| `chrome-extension-deploy.yml` | `CWS_CLIENT_ID`, `CWS_EXTENSION_ID` | `CWS_CLIENT_SECRET`, `CWS_REFRESH_TOKEN` |

The backend and frontend deploys poll the HCP Terraform runs API with `TFC_API_TOKEN` and wait for the workspace named by `TFC_WORKSPACE_ID` to reach a terminal state before touching Lambda, App Runner or S3 — that poll is what stops a code update racing an in-flight configuration change. Production polls `ws-oh1VvpTBPxmcrSYD`; staging polls `CarModPicker-staging`.

### A staging branch does not imply staging infrastructure

`terraform/` is one root module applied by two HCP workspaces: `CarModPicker` (production, bound to `main`, pinned in the `cloud` block in `versions.tf`) and `CarModPicker-staging` (bound to `staging`, `environment = staging`, `staging_profile = reduced`). `var.environment` feeds `local.prefix` and every environment-dependent decision.

The staging profile is `reduced`: DynamoDB, Lambda, HTTP API, CloudFront, S3 and SES, with no custom domain — the frontend lives on the CloudFront hostname and the API on the `execute-api` endpoint. `full` would add a hosted zone and certificates for `var.domain_name`. `none` is rejected. Staging can never build the legacy stack: `local.legacy_stack` is hard-wired to `environment == "production"`, so RDS and App Runner do not exist in 748861776298 whatever `legacy_stack_enabled` says. Staging is never auto-provisioned to mirror production.

### The Lambda migration stack

Production runs App Runner + RDS and Lambda + DynamoDB side by side until cutover. Three variables on the production workspace steer it: `legacy_stack_enabled` (default on; every legacy resource carries a `moved` block, so turning it on is a no-op and turning it off is a destroy), `api_target` (`legacy` keeps `api.carmodpicker.com` on App Runner, `lambda` flips the Route53 record to the HTTP API), and `custom_domain_enabled`. The full sequence is in `terraform/README.md` under "Production cutover".

The Lambda's code is not Terraform's: the function is created from a placeholder zip with `ignore_changes` on the package, and `backend-deploy.yml` owns every update after that. Its secrets come from the `<prefix>/app` JSON secret, read at import by `backend/app/core/secrets.py` when `APP_SECRETS_ARN` is set. DynamoDB tables are declared once, in `backend/app/db/dynamo/tables.py`; `backend/scripts/export_dynamo_tables.py` renders them to `terraform/dynamodb_tables.json` and `tests/db/test_dynamo_tables_json_up_to_date.py` fails when the two drift.

---

## Key Conventions

- **Alembic migrations:** Always use `alembic revision --autogenerate`. Never write migration files by hand.
- **pytest:** Always pass `-n auto` for parallel execution. Tests use SQLite in-memory — no Postgres required.
- **New CRUD endpoints:** Extend `BaseEndpointRouter` + `BaseCRUDService`; register with `EndpointRegistry` in `main.py`.
- The backend CORS config explicitly allows `chrome-extension://` origins and `null` (for service workers).
