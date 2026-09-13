# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

## Project Overview

CarModPicker manages car modifications: users track cars, build lists with parts, a global parts catalog, and forum-style build logs. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) backend, React 19 (TypeScript) frontend, deployed on AWS as Lambda container images behind an HTTP API with DynamoDB. Infrastructure is Terraform (`terraform/`), applied by HCP Terraform.

---

## Commands

### Backend (`backend/`)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Local services (Docker): DynamoDB Local on :8001, MinIO on :9000
docker-compose up -d
docker-compose down
python scripts/create_dynamo_tables.py     # create the app's tables locally (idempotent)
python scripts/export_dynamo_tables.py     # regenerate terraform/dynamodb_tables.json

# Tests: always -n auto. moto in-memory DynamoDB, so no services are required.
pytest -n auto
pytest -n auto --cov=app --cov-report=term-missing
pytest -n auto path/to/test_file.py
pytest -n auto -k "test_name"
# Rate limiting is off in tests; set ENABLE_RATE_LIMITING=true to exercise it.

ruff format .
ruff check .
pyright
bandit -r app
```

Per-domain images: one `backend/Dockerfile`, nine images, selected by `DOMAIN`. The dependency install resolves through CodeArtifact and the base image lives in the Artifacts account, so mint a token and log in to that ECR first.

```bash
export CODEARTIFACT_AUTH_TOKEN="$(aws codeartifact get-authorization-token \
  --domain webbpulse --domain-owner 432410731887 \
  --region us-west-2 --query authorizationToken --output text)"
aws ecr get-login-password --region us-west-2 \
  | docker login --username AWS --password-stdin \
    432410731887.dkr.ecr.us-west-2.amazonaws.com

scripts/build_image.sh media    # identity, users, catalog, vehicles, build-lists,
                                # build-logs, moderation, media, admin
scripts/run_image.sh media      # serves on :8080 against DynamoDB Local
curl localhost:8080/health      # liveness, no I/O; what the adapter polls
curl localhost:8080/ready       # readiness, reads DynamoDB
```

### Frontend (`frontend/`)

The private `@webbpulse/*` packages are published only to org CodeArtifact, so `npm ci` fails with a 401 until you have a token:

```bash
AWS_PROFILE=WebbPulse-Artifacts/AdministratorAccess AWS_REGION=us-west-2 \
  aws codeartifact login --tool npm --domain webbpulse \
  --domain-owner 432410731887 --repository npm --namespace @webbpulse
```

Run that from the repository root, not from `frontend/`: inside a package the CLI overwrites that package's tracked `.npmrc`. The token lands in `~/.npmrc` and lasts 12 hours; committed `frontend/.npmrc` holds only the scope-to-registry line. A read-only SSO profile cannot mint the token, because managed `ReadOnlyAccess` omits `sts:GetServiceBearerToken`.

```bash
npm run dev            # port 4000, proxies /api to the backend
npm run dev:staging    # staging API
npm run dev:production # production API (dev:prod is an alias)
npm run build          # tsc -b && vite build, then prerender
npm run lint
npm run format         # prettier --write
npm run format:check   # what CI runs
npm run type-check     # tsc -b --noEmit
npm test               # vitest watch
npm run test:run       # what CI runs
npm run test:coverage
```

### Chrome Extension (`chrome-extension/`)

```bash
npm run build       # production build to dist/
npm run watch       # rebuild on change, then reload in chrome://extensions/
npm run type-check
npm test            # vitest run
```

---

## Architecture

```
Browser / Chrome Extension
  -> React frontend (port 4000, dev proxy /api -> 8000)
  -> FastAPI backend (port 8000, prefix /api; Lambda + HTTP API in AWS)
  -> DynamoDB (DynamoDB Local in Docker locally)
```

Two composition roots sit over one set of routers.

- **Root A, `app/composition/`**: every domain in one process. `wiring.py` holds the `Domain` descriptor and the shared app building (CORS, rate limiting, error handlers, the root routes); `domains.py` names the nine domains and, for each, the routers it owns, its prefixes and tags, and whether it needs `SECRET_KEY`; `app.py` composes all nine.
- **Root B, `app/entrypoints/`**: one module per deployed function. The nine domains (`identity`, `users`, `catalog`, `vehicles`, `build_lists`, `build_logs`, `moderation`, `media`, `admin`) plus four stream consumers (`catalog_votes_consumer`, `catalog_part_purge_consumer`, `admin_price_alerts_consumer`, `users_delete_consumer`), which reuse their domain's image. Each builds an application carrying one domain plus the root routes.
- **`main.py`**: a thin wrapper over `composition/app.py`, the import path used by local dev, the test suite and Root A in the route-contract tests. It is not a deployment path.

`domains.py` loads routers through a callable, so importing a descriptor imports no endpoint module. That keeps a domain image to one domain; `backend/tests/entrypoints/` asserts it in a fresh interpreter with no AWS credentials.

Layers under `backend/app/`:

- **`api/endpoints/`**: one module per router (`users`, `app_settings`, `car_generations`, `parts`, `part_manufacturers`, `part_price_alerts`, `categories`, `retailers`, `build_lists`, `build_list_parts`, `build_list_phases`, `build_list_labor_estimates`, `build_logs`, `votes`, `reports`, `images`, `search`, `crawled_pages`, `bug_reports`, plus the `admin/` package). There is no `auth.py`: all of `/api/auth` is the `webbpulse` package's router, which is why `identity` declares no routers of its own.
- **`api/schemas/`** Pydantic v2 request and response schemas; **`api/services/`** business logic called by endpoints; **`api/middleware/`** rate limiting, content-length guard, error handlers; **`core/`** config, logging, email templates (React Email HTML via SES), seed data.
- **`api/dependencies/`**: `auth.py` holds `get_current_user`, `get_optional_current_user`, `get_current_admin_user`, `get_current_superuser`; `repositories.py` cuts per-domain `RepositoryBundle`s.
- **`api/utils/`**: `BaseDynamoEndpointRouter` (generic CRUD over `BaseDynamoCRUDService`), `EndpointRegistry`, pagination, authorization, subscription checks.
- **`db/dynamo/`**: `tables.py` (every table and GSI, one `TableSpec` each), `repository.py` (generic `DynamoRepository[TModel]`), one module per domain holding Pydantic item models and repositories, and `registry.py` cataloguing every repository as module, class and table name.

**RepositoryBundle:** a bundle carries only the repositories its domain declares in `app/composition/domains.py`, builds each on first access, and raises `RepositoryNotInBundle` for anything outside the set, so a `media` process never constructs a `users` repository. `Repositories` remains the annotation every route uses; `bind_repositories` binds the right bundle per application.

Endpoints read and write through repositories injected via `get_repositories()`; simple domains use `BaseDynamoEndpointRouter` rather than hand-rolled routes. Votes and reports are polymorphic over `entity_type` / `entity_id`.

**Auth:** `/api/auth` is served entirely by the `webbpulse.identity` package on the `identity` function, which signs RS256 in KMS and carries no `SECRET_KEY`. The other domains verify the HS256 path in `api/dependencies/auth.py`; expiry is configurable 15 minutes to 7 days per user. bcrypt passwords, optional TOTP 2FA and WebAuthn; email verification is required before login. Email goes via SES with IAM role auth.

**Images:** uploaded to a private S3 bucket via boto3 and served through presigned URLs; Pillow does the processing.

**Root routes:** `GET /health` is liveness and always 200. `GET /ready` returns 503 until DynamoDB answers a `DescribeTable` on the users table.

**Secrets:** each function reads the `<prefix>/app` JSON secret, resolved lazily by `app/core/config.py` when `APP_SECRETS_ARN` is set. An environment variable of the same name wins, so local dev and tests never call AWS. Importing the app makes no Secrets Manager call; `Settings.require_secrets(...)` is the point-of-use check and `check_signing_key` runs in the lifespan.

### Frontend (`frontend/src/`)

- **`pages/`**: route-level components, lazy-loaded. **`components/`**: shared UI. **`contexts/`**: auth and user state. **`hooks/`**: custom hooks.
- **`api/`**: one client module per backend domain, all through `api/client.ts`, which adapts `@webbpulse/api-client` to the `{ data }` shape call sites read and rejects with `ApiError` on a non-2xx. `utils/apiError.ts` is only the `unknown`-to-`ApiError` narrowing.
- **`config/app.ts`**: startup config validated by `@webbpulse/config`. The `VITE_BACKEND` dev switch is consulted only when `DEV` is true, so it cannot repoint a production bundle.
- React Router 7, Tailwind CSS 4. Subscription tiers gate features and ad display.

### Chrome Extension (`chrome-extension/src/`)

Content scripts scrape product data from retailer pages and POST to the backend API. `manifest.json`, `background.ts` and `popup.html/css` need an extension reload in `chrome://extensions/`; content, popup and options scripts pick up on the next page load or popup reopen.

---

## Branching and deploys

```
feature/* --PR--> staging --PR--> main
                    |               |
                    v               v
          AWS 748861776298   AWS 734702670403
             (staging)          (production)
```

- Branch new work from `staging`, not `main`, and PR into `staging`. Feature PRs into `staging` are squash-merged.
- **Release PRs from `staging` into `main` are merged with `gh pr merge --merge`, NEVER squashed.** A squashed release rewrites the commits `staging` still holds, so the next release PR opens with phantom conflicts. If a release PR is squashed by mistake, back-merge `main` into `staging` immediately.
- Never commit directly to `main` or `staging`. Never force-push either. Stacked PRs bottom out on `staging`.
- Hotfixes branch from `main` and PR into `main`, then are immediately back-merged `main` into `staging`. Skipping the back-merge is how the branches silently diverge.
- Both accounts are `us-west-2`. The Terraform Cloud org is `WebbPulse`.

Rulesets cover `main` and `staging`: pull request required, force-push and deletion blocked, and the `all-checks-passed` check from `ci.yml` required, so CI is blocking on both. Repository admins can bypass rulesets, so they stop mistakes rather than a determined admin. The real gate is the HCP Terraform manual apply on production: a merge cannot change AWS, only an apply can.

`docs/prod-promotion-plan.md` is the live production promotion runbook.

### Workflows

Four workflows in `.github/workflows/`: one CI workflow and three deploy workflows.

| Workflow | Trigger | Paths |
|---|---|---|
| `ci.yml` | `pull_request` to `main`, `staging` | none on the trigger; the workflow filters paths itself |
| `deploy-backend.yml` | `push` to `main`, `staging`, plus `workflow_dispatch` | `backend/**`, `.github/workflows/deploy-backend.yml` |
| `frontend-deploy.yml` | `push` to `main`, `staging`, plus `workflow_dispatch` | `frontend/**`, `.github/workflows/frontend-deploy.yml` |
| `chrome-extension-deploy.yml` | `push` to `main`, plus `workflow_dispatch` | `chrome-extension/**`, `.github/workflows/chrome-extension-deploy.yml` |

The deploy workflows are fully independent: a backend merge never rebuilds the frontend.

**`ci.yml`** has no `paths:` on its trigger: a first `changes` job runs `dorny/paths-filter`, and its `backend`, `frontend`, `chrome-extension` and `scripts` outputs gate every later job. `backend` and `frontend` call the org reusable `python-ci.yml@v2` and `typescript-ci.yml@v2`; `frontend-audit-and-imports` adds `npm audit` and `madge --circular`; `chrome-extension` builds and checks `host_permissions`; `scripts` covers the repository-root `scripts/`. `all-checks-passed` needs every other job and runs `if: always()`, failing on any `failure` or `cancelled`. A skipped job passes, which is what lets a frontend-only PR satisfy the required check.

**`deploy-backend.yml`** is the only path to changing Lambda code: `resolve-env`, `build-images`, `image-map`, `existing-functions`, `deploy-images`, `smoke-domains`, `verify-route-cuts`. It builds the nine domain images from `backend/Dockerfile` for `linux/arm64` and points each function at a digest; there is no zip in the chain, and the four consumers share their domain's image. `existing-functions` filters to functions that actually exist, so a partial estate skips what is missing instead of failing on `ResourceNotFoundException`. `smoke-domains` requires a 200 from a synthetic `GET /health` per domain; `verify-route-cuts` runs `scripts/verify_route_cut.sh`.

**`frontend-deploy.yml`** calls the org reusable `spa-deploy.yml@v2.3.0`, which polls HCP Terraform with `TFC_API_TOKEN` and waits for the workspace to be terminal before touching S3, so a deploy cannot race an in-flight apply. `main` polls `CarModPicker`, `staging` polls `CarModPicker-staging`.

**`chrome-extension-deploy.yml`** stays `main`-only: it publishes to the Chrome Web Store and there is no staging listing. It patch-bumps `manifest.json`, tags `chrome-extension-vX.Y.Z`, cuts a Release and uploads via the CWS API. A `gate` job releases only on `workflow_dispatch` or when `CHROME_EXTENSION_AUTO_RELEASE` is `true`, and it is unset today, so a push holds. It then pushes the tag to `main` directly, the one sanctioned exception to "never commit directly to `main`", and opens a bookkeeping PR back to `staging`.

### Environment-scoped variables

Deploy variables live on the `production` and `staging` GitHub Environments, not the repository, so a `staging` push cannot pick up the production role. Values come from the matching workspace's Terraform outputs; `terraform/README.md` maps each variable to its output.

| Workflow | Variables | Secrets |
|---|---|---|
| `ci.yml` | `CI_AWS_ROLE_ARN`, `CODEARTIFACT_DOMAIN_OWNER` (both repository) | none |
| `deploy-backend.yml` | `AWS_DEPLOY_ROLE_ARN` (environment); `CODEARTIFACT_DOMAIN_OWNER`, `BACKEND_IMAGE_BUILD_ENABLED`, `BACKEND_IMAGE_DEPLOY_ENABLED` (repository) | none |
| `frontend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `FRONTEND_S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `VITE_API_URL`, `CWS_EXTENSION_ID` (environment); `CODEARTIFACT_DOMAIN_OWNER` (repository) | `TFC_API_TOKEN` |
| `chrome-extension-deploy.yml` | `CWS_CLIENT_ID`, `CWS_EXTENSION_ID`, `CHROME_EXTENSION_AUTO_RELEASE` (all on `production`) | `CWS_CLIENT_SECRET`, `CWS_REFRESH_TOKEN` (on `production`) |

`CI_AWS_ROLE_ARN` is the one AWS role a pull request can reach, since `AWS_DEPLOY_ROLE_ARN` sits on Environments whose branch policies admit only `staging` and `main`. CI needs it only to mint a CodeArtifact token for `webbpulse` and `@webbpulse/*`; it holds those reads and `sts:GetServiceBearerToken` and nothing else, deliberately not the deploy role.

Both deploy chains open with a `resolve-env` job because a job calling a reusable workflow with `uses:` may not carry an `environment:` key, so the environment-scoped values are read there and passed through job outputs. `deploy-backend.yml` needs no `TFC_API_TOKEN`: its Terraform wait is `aws lambda wait function-updated-v2` around each `update-function-code`.

### Terraform

`terraform/` is one root module applied by two HCP workspaces: `CarModPicker` (production, bound to `main`, pinned in the `cloud` block in `versions.tf`) and `CarModPicker-staging` (bound to `staging`, `environment = staging`). `var.environment` feeds `local.prefix`, `local.domain_name` and every environment-dependent decision. A `staging` branch does not imply staging infrastructure.

Lambda code is not Terraform's. Each of the nine domain functions and four stream consumers is created from `var.bootstrap_image_tag` with `image_uri` on `ignore_changes`, and `deploy-backend.yml` owns every update after that.

---

## Key Conventions

- **Tables:** declare every table and index in `backend/app/db/dynamo/tables.py`, then run `python scripts/export_dynamo_tables.py` so `terraform/dynamodb_tables.json` matches. `tests/db/test_dynamo_tables_json_up_to_date.py` fails on drift. There are no migrations; schema changes are additive attributes on Pydantic item models.
- **pytest:** always `-n auto`. Tests use moto's in-memory DynamoDB, so no services are required.
- **New CRUD endpoints:** extend `BaseDynamoEndpointRouter` plus `BaseDynamoCRUDService`, then add the router to its domain's loader in `backend/app/composition/domains.py` with its prefix and tags. Both composition roots pick it up from there.
- **Route changes:** a new route changes the routing table, so regenerate `backend/tests/fixtures/route_contract.json` and bump the count for that domain in `backend/tests/entrypoints/test_route_split.py`. The diff on the fixture is the review artifact.
- **CORS:** the allow list is built in one place, `Settings.allowed_origins_list`, and applied by `add_shared_middleware` in `backend/app/composition/wiring.py`, so both roots and all nine entrypoints share it. Chrome extension access is by explicit id: `CHROME_EXTENSION_IDS` becomes `chrome-extension://<id>` origins. There is no `chrome-extension://.*` regex and no `null` origin.
- **Absolute URLs in emails and sitemaps:** never hardcode a host. `settings.frontend_base_url` is the SPA origin and `settings.api_base_url` is this API's origin; both derive from `APP_ENVIRONMENT` and are overridable with `FRONTEND_URL` / `API_URL`. Hardcoding is how staging came to mail production verification links.

## Gotchas

- Squash-merging a `staging` to `main` release PR produces phantom conflicts on the next release. Use `gh pr merge --merge`, and back-merge `main` into `staging` if it already happened.
- Run `aws codeartifact login --tool npm` from the repository root, never from `frontend/`, or it rewrites the committed `frontend/.npmrc`.
- A read-only SSO profile cannot mint a CodeArtifact token: managed `ReadOnlyAccess` omits `sts:GetServiceBearerToken`.
- `var.bootstrap_image_tag` is load-bearing at create time and gates `local.domain_functions_enabled`, so it must name a tag that still resolves in every declared domain's repository before an apply that creates functions.
- Every `ci.yml` paths-filter also matches `.github/workflows/ci.yml`, so editing CI reruns the whole matrix.
- `frontend/package.json` has both `dev:production` and `dev:prod`; they are the same command.
- Chrome extension reloads are manual for `manifest.json`, `background.ts` and `popup.html/css`.
