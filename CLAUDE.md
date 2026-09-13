# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CarModPicker is a full-stack web application for managing car modifications. Users can track their cars, create build lists with parts, browse a global parts catalog, and log their builds in forum-style threads. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) backend + React 19 (TypeScript) frontend, deployed on AWS as Lambda + HTTP API + DynamoDB. Infrastructure managed with Terraform (`terraform/`).

---

## Commands

### Backend (`backend/`)

```bash
# Start dev server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Local services (requires Docker): DynamoDB Local on :8001, MinIO on :9000
docker-compose up -d
docker-compose down
python scripts/create_dynamo_tables.py   # create the app's tables in DynamoDB Local (idempotent)
python scripts/backfill_from_postgres.py --dry-run   # one-off Postgres -> DynamoDB copy (needs psycopg2-binary + DATABASE_URL)

# Table definitions live in app/db/dynamo/tables.py; regenerate the Terraform copy after editing
python scripts/export_dynamo_tables.py

# Per-domain container images. One Dockerfile, nine images, selected by DOMAIN.
# The dependency install resolves through CodeArtifact, so mint a token first.
export CODEARTIFACT_AUTH_TOKEN="$(aws codeartifact get-authorization-token \
  --domain webbpulse --domain-owner 432410731887 \
  --region us-west-2 --query authorizationToken --output text)"
# The base image lives in the Artifacts account, so pulling it needs that login.
aws ecr get-login-password --region us-west-2 \
  | docker login --username AWS --password-stdin \
    432410731887.dkr.ecr.us-west-2.amazonaws.com

scripts/build_image.sh media            # domains: identity, users, catalog,
                                        # vehicles, build-lists, build-logs,
                                        # moderation, media, admin
scripts/run_image.sh media              # serves on :8080 against DynamoDB Local
curl localhost:8080/health              # liveness, no I/O; what the adapter polls
curl localhost:8080/ready               # readiness, reads DynamoDB

# Tests — always run with -n auto for parallel execution
# Tests run against moto's in-memory DynamoDB — no services required
pytest -n auto
pytest -n auto --cov=app --cov-report=term-missing
pytest -n auto path/to/test_file.py       # single file
pytest -n auto -k "test_name"             # single test
# Rate limiting is disabled in tests by default; set ENABLE_RATE_LIMITING=true to test it

# Linting / formatting
ruff format .
ruff check .
pyright
bandit -r app
```

### Frontend (`frontend/`)

The frontend depends on the private `@webbpulse/*` packages, which are published
to the org CodeArtifact repository and never to the public registry. `npm ci`
fails with a 401 until you have a token, so log in first:

```bash
AWS_PROFILE=WebbPulse-Artifacts/AdministratorAccess AWS_REGION=us-west-2 \
  aws codeartifact login --tool npm --domain webbpulse \
  --domain-owner 432410731887 --repository npm --namespace @webbpulse
```

Run it from the repository root, not from `frontend/`: inside a package the CLI
writes to that package's `.npmrc`, which is the tracked file. The token lands in
`~/.npmrc` and lasts 12 hours. `frontend/.npmrc` holds only the scope-to-registry
line and is committed. A read-only SSO profile cannot mint the token: the managed
`ReadOnlyAccess` policy omits `sts:GetServiceBearerToken`.

```bash
npm run dev           # dev server on port 4000 (proxies /api to backend)
npm run dev:staging   # use staging API
npm run dev:production # use production API (dev:prod is an alias)
npm run build         # tsc -b && vite build
npm run lint          # eslint
npm run format        # prettier --write
npm run format:check  # prettier --check (what CI runs)
npm run type-check    # tsc -b --noEmit
npm test              # vitest (watch)
npm run test:run      # vitest run (what CI runs)
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
    → FastAPI backend (port 8000, prefix /api; Lambda + HTTP API in AWS)
    → DynamoDB (DynamoDB Local in Docker locally, DynamoDB in AWS)
```

### Backend (`backend/app/`)

- **`main.py`** — The whole-surface application, kept as the import path everything already uses (`uvicorn app.main:app` for local dev, the test suite, and Root A in the route-contract tests). It is a thin wrapper over `app/composition/app.py` and holds no wiring of its own. It is no longer a deployment path: `lambda_handler.py` was deleted with the monolith in row 32 of `docs/migration/split-plan.md`, and nothing in AWS imports `main.py` any more.
- **`composition/`** — Root A, every domain in one process. `wiring.py` holds the `Domain` descriptor and the shared app building (CORS, rate limiting, error handlers, the five root routes); `domains.py` names the nine domains and, for each, the routers it owns, its prefixes and tags, and whether it needs `SECRET_KEY`; `app.py` composes all nine and is what `main.py` serves.
- **`entrypoints/`** — Root B, one module per deployed function: the nine domains (`identity`, `users`, `catalog`, `vehicles`, `build_lists`, `build_logs`, `moderation`, `media`, `admin`) plus four stream consumers (`catalog_votes_consumer`, `catalog_part_purge_consumer`, `admin_price_alerts_consumer`, `users_delete_consumer`), which reuse their domain's image. Each builds an application carrying one domain plus the five root routes. `domains.py` loads routers through a callable so importing a descriptor imports no endpoint module, which is what keeps a domain image to one domain; `backend/tests/entrypoints/` asserts it in a fresh interpreter with no AWS credentials.
- **`api/endpoints/`** — One module per router (`users`, `app_settings`, `car_generations`, `parts`, `part_manufacturers`, `part_price_alerts`, `categories`, `retailers`, `build_lists`, `build_list_parts`, `build_list_phases`, `build_list_labor_estimates`, `build_logs`, `votes`, `reports`, `images`, `search`, `crawled_pages`, `bug_reports`, and the `admin/` package holding `stats` and `db_ops`). There is no `auth.py`: since row 13 the whole of `/api/auth` is the `webbpulse` package's router, which is why the `identity` domain declares no routers of its own.
- **`db/dynamo/`** — DynamoDB layer: `tables.py` (every table and GSI, one `TableSpec` each), `repository.py` (generic `DynamoRepository[TModel]`), and one module per domain (`users`, `catalog`, `build_lists`, `build_logs`, `moderation`, ...) holding the Pydantic item models and their repositories. `registry.py` catalogues all twenty-five repositories as module, class and table names, and `api/dependencies/repositories.py` cuts per-domain `RepositoryBundle`s from it. A bundle carries only the repositories its domain declares in `app/composition/domains.py`, builds each one on first access, and raises `RepositoryNotInBundle` for anything outside the set, so a `media` process never constructs a `users` repository. `Repositories` is still the annotation every route uses; `bind_repositories` binds the right bundle per application.
- **`api/schemas/`** — Pydantic v2 request/response schemas.
- **`api/services/`** — Business logic layer called by endpoints.
- **`api/dependencies/auth.py`** — FastAPI `Depends()` helpers: `get_current_user`, `get_optional_current_user`, `get_current_admin_user`, `get_current_superuser`.
- **`api/middleware/`** — Rate limiting + content-length guard + error handlers.
- **`api/utils/`** — Shared patterns: `BaseDynamoEndpointRouter` (generic CRUD router over `BaseDynamoCRUDService`), `EndpointRegistry` (standardized router registration), pagination, authorization, subscription checks.
- **`core/`** — Config, logging, email templates (React Email HTML, sent via SES), car/category seed data.

**Auth:** JWT (HS256, configurable expiry 15 min–7 days per user preference) + bcrypt passwords + optional TOTP 2FA. Requires email verification before login is allowed. Email sent via AWS SES with IAM role auth.

**Images:** Uploaded to S3 (`carmodpicker-prod-user-images`, private) via boto3; presigned URLs used for serving. Pillow used for processing.

**Special endpoints:**
- `GET /health` — liveness check (always 200)
- `GET /ready` — readiness check (503 until DynamoDB answers a `DescribeTable` on the users table)

### Backend patterns

Endpoints read and write through repositories from `app/db/dynamo/`, injected via `get_repositories()`. Simple domains use `BaseDynamoEndpointRouter` (generic CRUD over `BaseDynamoCRUDService`) rather than hand-rolled route functions; when adding a new domain, add a `TableSpec`, an item model plus repository, and follow that pattern. Votes and reports are polymorphic over `entity_type` / `entity_id` and served by the unified `votes.py` / `reports.py` endpoints backed by `VoteService` / `ReportService` on DynamoDB.

### Frontend (`frontend/src/`)

- **`pages/`** — Route-level components (lazy-loaded).
- **`components/`** — Shared UI components.
- **`api/`** — API client modules (one per backend domain). All of them go
  through `api/client.ts`, which adapts `@webbpulse/api-client` to the
  `{ data }` response shape the call sites read and rejects with `ApiError` on a
  non-2xx. The error envelope is read by `getWebbPulseError` in that package;
  `utils/apiError.ts` is only the `unknown`-to-`ApiError` narrowing around it.
- **`config/app.ts`** — startup configuration, validated by `@webbpulse/config`.
  The `VITE_BACKEND` dev switch and the `/api` suffix are the package's
  `backendTargets` and `apiPathPrefix` options; the switch is consulted only
  when `DEV` is true, so it cannot repoint a production bundle.
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

- Branch new work from `staging`, not `main`. PR into `staging`. Feature pull requests into `staging` are squash-merged.
- Releasing is a pull request from `staging` into `main` — that PR is the release boundary. **Merge a release PR with a merge commit** (`gh pr merge --merge`), never a squash. A squashed release rewrites the commits that `staging` still holds, so the next release PR opens with phantom conflicts; if one is squashed by mistake, back-merge `main` into `staging` immediately.
- Never commit directly to `main` or `staging`. Never force-push either. Stacked PRs bottom out on `staging`.
- Hotfixes branch from `main` and PR into `main`, then are immediately back-merged `main` → `staging`. Skipping the back-merge is how the branches silently diverge.
- Both accounts are `us-west-2`. Terraform Cloud org is `WebbPulse`.

**Protection is enforced by rulesets, with one bypass.** The WebbPulse org is on the GitHub Team plan, and repository rulesets cover both `main` and `staging`: pull request required, force-push and deletion blocked. The repository-admin role can bypass them, so the rulesets stop mistakes, not a determined admin. The real gate is Terraform Cloud manual apply on the production workspace: a merge cannot change AWS, only an apply can. Both rulesets also require the `all-checks-passed` status check from `ci.yml`, so CI is blocking on both branches.

### Workflows

Four workflows in `.github/workflows/`: one CI workflow and three deploy workflows.

| Workflow | Trigger | Paths |
|---|---|---|
| `ci.yml` | `pull_request` → `main`, `staging` | none; the workflow filters paths itself |
| `deploy-backend.yml` | `push` → `main`, `staging`, plus `workflow_dispatch` | `backend/**`, `.github/workflows/deploy-backend.yml` |
| `frontend-deploy.yml` | `push` → `main`, `staging`, plus `workflow_dispatch` | `frontend/**`, `.github/workflows/frontend-deploy.yml` |
| `chrome-extension-deploy.yml` | `push` → `main`, plus `workflow_dispatch` | `chrome-extension/**`, `.github/workflows/chrome-extension-deploy.yml` |

The deploy workflows are fully independent. A backend merge never rebuilds the frontend.

**`ci.yml` is the only CI workflow.** The separate `backend-ci.yml`, `frontend-ci.yml` and `chrome-extension-ci.yml` are gone; if a commit or an old Actions run mentions one, it is describing the world before the consolidation. `ci.yml` carries no `paths:` filter on its trigger, so it starts on every pull request into `main` or `staging` and does the filtering in a first `changes` job with `dorny/paths-filter`, which sets a `backend`, `frontend`, `chrome-extension` and `scripts` output. Every later job is `if:`-gated on the matching output, and each filter also matches `.github/workflows/ci.yml` itself, so editing CI reruns everything.

- `backend` calls the org reusable workflow `WebbPulse/.github/.github/workflows/python-ci.yml@v2` against `backend/`, which owns ruff, pyright, bandit, pip-audit and pytest with coverage, plus the CodeArtifact login `requirements.txt` needs. Test environment values are passed as `test-env-json`.
- `frontend` calls `WebbPulse/.github/.github/workflows/typescript-ci.yml@v2` against `frontend/`, which owns install, lint, format check, test and build plus the CodeArtifact login the `@webbpulse/*` packages need. `typecheck-command` is deliberately empty because `npm run build` already runs `tsc -b`.
- `frontend-audit-and-imports` holds the two frontend checks the reusable workflow has no input for: `npm audit --audit-level=moderate` and `madge --circular`. It installs nothing and assumes no role, since neither needs the private registry.
- `chrome-extension` runs in this repository: type check, unit tests, `npm audit`, build, then it asserts `dist/manifest.json` exists and runs `scripts/check-host-permissions.js` to keep the API hosts in `host_permissions`. It uploads the built `dist/` as an artifact.
- `scripts` covers the repository-root `scripts/` directory: a `bash -n` syntax check on `verify_route_cut.sh` and pytest over `test_expected_route_key.py` and `test_identity_smoke.py`.
- `all-checks-passed` is a final job that needs every other job, runs with `if: always()`, and fails when any upstream job reports `failure` or `cancelled`. A skipped job passes, which is what lets a frontend-only pull request satisfy it without running backend CI.

**CI is blocking.** The `main-protection` and `staging-protection` rulesets both require the `all-checks-passed` status check, so that one context is the gate for both branches. Adding or renaming a job inside `ci.yml` needs no ruleset change as long as `all-checks-passed` still needs it.

**`deploy-backend.yml` is the only backend deploy.** It is the per-domain container image chain: `resolve-env`, `build-images`, `image-map`, `existing-functions`, `deploy-images`, `smoke-domains`, `verify-route-cuts`. It builds the nine domain images from the one `backend/Dockerfile` with `DOMAIN` selecting the entrypoint, pushes them for `linux/arm64`, and points each function at a digest; there is no zip anywhere in the chain any more. `image-map` turns the per-domain build manifests into a function-to-image map and adds the four stream consumers, which share their domain's image. `existing-functions` filters that map down to the functions that actually exist, so an estate part way through the cutover deploys what is there and skips what is not rather than failing on `ResourceNotFoundException`. `deploy-images` calls `WebbPulse/.github/.github/workflows/lambda-image-deploy.yml@v1.3.0`. `smoke-domains` invokes each deployed domain function with a synthetic `GET /health` event and requires a 200, skipping the consumers because they have no API Gateway route. `verify-route-cuts` then runs `scripts/verify_route_cut.sh` for every domain, using the staging access gate origin-verify value from SSM when deploying staging.

Reading git history you will also find `backend-deploy.yml`, whose name differs only in word order and which was a different workflow entirely: the monolith's zip chain, which built `requirements-lambda.txt` for manylinux x86_64 / Python 3.13 plus `app/`, uploaded the zip to `<prefix>-lambda-artifacts` keyed by commit SHA, waited for HCP Terraform to go idle, then ran `update-function-code` and `publish-version` on `carmodpicker-<env>-api`. Row 32 of `docs/migration/split-plan.md` retired the monolith and deleted `backend-deploy.yml` with it.

Both halves of the image chain are gated by repository variables, and both are now `true`, so `deploy-backend.yml` builds and deploys on every qualifying push. `BACKEND_IMAGE_BUILD_ENABLED` gates the build; `BACKEND_IMAGE_DEPLOY_ENABLED` gates the deploy.

**`chrome-extension-deploy.yml` stays `main`-only.** It publishes to the Chrome Web Store, not to AWS: patch-bump `manifest.json`, tag `chrome-extension-vX.Y.Z`, cut a GitHub Release, upload and publish the zip via the CWS API. A browser extension has no staging-account equivalent and there is no staging store listing, so a `staging` trigger would have nothing to deploy to. Two gates sit in front of the release. A `gate` job releases only when the event is a `workflow_dispatch` or the `production` environment variable `CHROME_EXTENSION_AUTO_RELEASE` is `true`; that variable is unset today, so a push holds and only a manual **Run workflow** publishes. A `changes` job then skips the release when nothing but `manifest.json` changed under `chrome-extension/` since the newest `chrome-extension-v*` tag. After publishing it pushes the release tag to `main` directly, the one sanctioned exception to "never commit directly to `main`", and opens a bookkeeping pull request carrying the version bump back to `staging`.

### Environment-scoped variables

Deploy variables are **environment-scoped**: they live on the `production` and `staging` GitHub Environments, not the repository, so a `staging` push cannot silently pick up the production role. Nothing deploy-related is hardcoded in the workflows any more — the API URL is an Environment variable too. Values come from the matching workspace's Terraform outputs (`terraform/README.md` maps each variable to its output). `VITE_API_URL` is `api_url`, which follows the served domain (`https://api.carmodpicker.com`, `https://api.staging.carmodpicker.com`), so it has to be re-copied when a profile flips; `frontend_url`, `domain_name`, `route53_zone_id` and `route53_zone_name_servers` are the other hostname-bearing outputs.

| Workflow | Variables | Secrets |
|---|---|---|
| `deploy-backend.yml` | `AWS_DEPLOY_ROLE_ARN` (environment), `CODEARTIFACT_DOMAIN_OWNER`, `BACKEND_IMAGE_BUILD_ENABLED`, `BACKEND_IMAGE_DEPLOY_ENABLED` (all three repository-level) | none |
| `frontend-deploy.yml` | `AWS_DEPLOY_ROLE_ARN`, `FRONTEND_S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `VITE_API_URL`, `CWS_EXTENSION_ID` (environment), `CODEARTIFACT_DOMAIN_OWNER` (repository) | `TFC_API_TOKEN` (repository) |
| `chrome-extension-deploy.yml` | `CWS_CLIENT_ID`, `CWS_EXTENSION_ID`, `CHROME_EXTENSION_AUTO_RELEASE` (all on `production`) | `CWS_CLIENT_SECRET`, `CWS_REFRESH_TOKEN` (on `production`) |
| `ci.yml` | `CI_AWS_ROLE_ARN`, `CODEARTIFACT_DOMAIN_OWNER` (both repository-level) | none |

**`LAMBDA_FUNCTION_NAME` and `LAMBDA_ARTIFACTS_BUCKET` are unused and should be deleted from the `production` Environment.** They were `backend-deploy.yml`'s, naming the monolith function and the artifacts bucket, and row 32 deleted the workflow, the function and the bucket. Nothing reads either variable now. `TFC_WORKSPACE_ID` is also unused: `frontend-deploy.yml` moved to naming the workspace by name, passing `tfc-organization` and a `tfc-workspace` derived from the branch, so the id variable is dead too. `TFC_API_TOKEN` stays, because the frontend deploy still polls HCP with it.

**`CI_AWS_ROLE_ARN` is repository-scoped, and it is the one AWS role a pull request can reach.** `AWS_DEPLOY_ROLE_ARN` lives on the `staging` and `production` Environments, whose deployment branch policies admit only those branches, so a `pull_request` job cannot read it at all. CI still needs an AWS identity for one thing: `requirements.txt` starts with `webbpulse`, which is published only to CodeArtifact and never to PyPI, so the job has to mint a CodeArtifact token before `pip install` can resolve anything; the frontend job needs the same for `@webbpulse/*`. `CI_AWS_ROLE_ARN` names `carmodpicker-staging-github-actions-ci` (output `github_actions_ci_role_arn`), a role that holds the CodeArtifact reads and `sts:GetServiceBearerToken` and nothing else, and whose trust names the `pull_request` subject plus the `staging` and `main` branch refs rather than a wildcard. It is deliberately not the deploy role: that one holds `lambda:UpdateFunctionCode` and `ecr:PutImage`, and pointing pull request CI at it would let any branch that can open a pull request assume a role that deploys.

`deploy-backend.yml` needs no `TFC_API_TOKEN`. Its Terraform wait is the reusable workflow's `aws lambda wait function-updated-v2` before and after each `update-function-code`, taken once for all functions rather than once per domain, which settles an in-flight apply without polling HCP at all. `AWS_DEPLOY_ROLE_ARN` is environment-scoped like every other deploy role, which is why the chain opens with a `resolve-env` job: a job that calls a reusable workflow with `uses:` may not carry an `environment:` key, so it cannot read an environment-scoped variable and `resolve-env` passes the ARN through a job output instead. `frontend-deploy.yml` opens with a `resolve-env` job for the same reason.

The frontend deploy calls `WebbPulse/.github/.github/workflows/spa-deploy.yml@v2.3.0`, which polls the HCP Terraform runs API with `TFC_API_TOKEN` and waits for the workspace to reach a terminal state before touching S3, which is what stops a code update racing an in-flight configuration change. The workspace is named by the branch: `main` polls `CarModPicker`, `staging` polls `CarModPicker-staging`. The backend deploy no longer polls anything.

### A staging branch does not imply staging infrastructure

`terraform/` is one root module applied by two HCP workspaces: `CarModPicker` (production, bound to `main`, pinned in the `cloud` block in `versions.tf`) and `CarModPicker-staging` (bound to `staging`, `environment = staging`). `var.environment` feeds `local.prefix`, `local.domain_name` and every environment-dependent decision.

The intended staging profile is `full`: the same stack as production, served as `staging.carmodpicker.com` / `www.staging.carmodpicker.com` / `api.staging.carmodpicker.com`. The staging account owns the `staging.carmodpicker.com` hosted zone, and the same apply writes its `NS` delegation into the `carmodpicker.com` zone in the production account through the `aws.parent_dns` provider alias, which assumes `route53_write_role_arn` (scoped to that one record) and targets `parent_route53_zone_id`. WebbPulse-Platform pushes both variables to the workspace; SES uses the domain identity exactly as production does. `reduced` is the fallback while those variables are absent: no custom domain, frontend on the CloudFront hostname, API on the `execute-api` endpoint, SES on a mailbox identity. `none` is rejected. Staging is never auto-provisioned to mirror production.

### The Lambda migration stack

Production was cut over from App Runner + RDS PostgreSQL to Lambda + DynamoDB on 2026-09-06 and the legacy stack has been destroyed; `terraform/README.md` keeps a short record under "Production cutover". The only remaining Postgres artefact is `backend/scripts/backfill_from_postgres.py`, kept for reference.

Lambda code is not Terraform's: each of the nine domain functions and the four stream consumers is created from the image tag in `var.bootstrap_image_tag` with `image_uri` on `ignore_changes`, and `deploy-backend.yml` owns every update after that. The bootstrap tag is a seed only, but it is load-bearing at create time and it also gates `local.domain_functions_enabled`, so it must name a tag that still resolves in every declared domain's repository before a row-cut apply. Its secrets come from the `<prefix>/app` JSON secret, resolved lazily on first read by `backend/app/core/config.py` when `APP_SECRETS_ARN` is set (an environment variable of the same name wins, so local dev and tests never call AWS). Importing the application performs no Secrets Manager call, which is what lets tooling import it without credentials; `Settings.require_secrets(...)` is the point-of-use check, and `check_signing_key` runs in the application lifespan rather than at module scope for the same reason. The fetch, the JSON parse and the per-ARN cache come from `webbpulse.config.load_json_secret`; `backend/app/core/secrets.py` is a thin adapter over it that flattens the object to strings, and its `reset_cache()` clears the shared cache too. DynamoDB tables are declared once, in `backend/app/db/dynamo/tables.py`; `backend/scripts/export_dynamo_tables.py` renders them to `terraform/dynamodb_tables.json` and `tests/db/test_dynamo_tables_json_up_to_date.py` fails when the two drift.

---

## Key Conventions

- **Tables:** Declare every table and index in `backend/app/db/dynamo/tables.py`, then run `python scripts/export_dynamo_tables.py` so `terraform/dynamodb_tables.json` matches (a test fails when they drift). There are no migrations; schema changes are additive attributes on Pydantic item models.
- **pytest:** Always pass `-n auto` for parallel execution. Tests use moto's in-memory DynamoDB — no services required.
- **New CRUD endpoints:** Extend `BaseDynamoEndpointRouter` + `BaseDynamoCRUDService`, then add the router to its domain's loader in `backend/app/composition/domains.py` with the prefix and tags it should carry. Both composition roots pick it up from there. A new route changes the routing table, so regenerate `backend/tests/fixtures/route_contract.json` and bump the count for that domain in `backend/tests/entrypoints/test_route_split.py`; the diff on the fixture is the review artifact.
- **CORS:** the allow list is built in one place, `Settings.allowed_origins_list`, and applied by `add_shared_middleware` in `backend/app/composition/wiring.py`, so both composition roots and all nine entrypoints share it. Chrome extension access is by explicit id: `CHROME_EXTENSION_IDS` (defaulting to the Chrome Web Store id) becomes `chrome-extension://<id>` origins. There is no `chrome-extension://.*` regex and no `null` origin; an MV3 service worker sends `chrome-extension://<id>`, and the extension authenticates with a bearer token rather than cookies.
- **Absolute URLs in emails and sitemaps:** never hardcode a host. `settings.frontend_base_url` is the SPA origin and `settings.api_base_url` is this API's origin; both derive from `APP_ENVIRONMENT` and are overridable with `FRONTEND_URL` / `API_URL`. Hardcoding is how staging came to mail production verification links.
