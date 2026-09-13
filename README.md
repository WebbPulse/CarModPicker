# CarModPicker

A web app for tracking car modifications. Users manage cars and build lists, attach parts to phased builds, and log progress in forum-style threads. A companion Chrome extension captures parts from retailer pages.

**Stack:** FastAPI (Python 3.13) · React 19 (TypeScript) · DynamoDB · AWS (Lambda container images + HTTP API), with Terraform for infrastructure.

**License:** MIT

---

## Structure

```
backend/          FastAPI app, nine per-domain Lambda images, DynamoDB table definitions
frontend/         React + Vite + Tailwind CSS 4
chrome-extension/ Captures part data from retailer pages
terraform/        AWS infrastructure, applied by HCP Terraform
docs/             Runbooks and reference notes
```

---

## Quickstart

**Prerequisites:** Python 3.13, Node 22+, Docker (DynamoDB Local and MinIO), and an AWS login that can mint a CodeArtifact token. Both the backend and the frontend depend on private `@webbpulse` packages, so see the CodeArtifact login steps in [CLAUDE.md](CLAUDE.md) before installing.

### Backend

```bash
cd backend
docker-compose up -d                    # DynamoDB Local (:8001) + MinIO (:9000)
python scripts/create_dynamo_tables.py  # create the app's tables (needs DYNAMODB_ENDPOINT_URL in .env)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
pytest -n auto            # always -n auto; moto in-memory DynamoDB, no services needed
ruff format . && ruff check . && pyright && bandit -r app
```

### Frontend

```bash
cd frontend
npm ci
npm run dev               # port 4000, proxies /api to the backend
npm run build
npm run lint
npm run type-check
npm run test:run
```

### Chrome extension

```bash
cd chrome-extension
npm ci
npm run build             # → dist/, then load unpacked in chrome://extensions/
npm run watch
```

---

## Releasing

Branch from `staging`, PR into `staging`, then release with a PR from `staging` into `main`. Release PRs are merged with `gh pr merge --merge` and **never squashed**. `main` deploys to the production AWS account, `staging` to the staging account; AWS changes still need a manual HCP Terraform apply.

---

## Docs

- [CLAUDE.md](CLAUDE.md) is the orientation doc: commands, architecture, the deploy flow, environment variables, conventions and gotchas.
- [docs/prod-promotion-plan.md](docs/prod-promotion-plan.md) is the live production promotion runbook.
- [docs/RATE_LIMITING.md](docs/RATE_LIMITING.md), [docs/PARALLEL_TESTING.md](docs/PARALLEL_TESTING.md) and [docs/security/](docs/security/) cover those areas.
- [terraform/README.md](terraform/README.md) maps each deploy variable to its Terraform output.
