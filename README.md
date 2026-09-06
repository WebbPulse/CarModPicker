# CarModPicker

A web app for tracking car modifications. Users manage cars and build lists, attach parts to phased builds, and log progress in forum-style threads. A companion Chrome extension captures parts from retailer pages.

**Stack:** FastAPI (Python 3.13) · React 19 (TypeScript) · DynamoDB · AWS (Lambda + HTTP API)

**License:** MIT

---

## Structure

```
backend/          FastAPI app and DynamoDB table definitions
frontend/         React + Vite + Tailwind CSS 4
chrome-extension/ Captures part data from retailer pages
terraform/        AWS infrastructure
```

---

## Development

**Prerequisites:** Python 3.13, Node 20+, Docker (for DynamoDB Local and MinIO)

### Backend

```bash
cd backend
docker-compose up -d                          # DynamoDB Local (:8001) + MinIO (:9000)
python scripts/create_dynamo_tables.py        # create the app's tables (needs DYNAMODB_ENDPOINT_URL in .env)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Tests (moto in-memory DynamoDB, no services required)
pytest -n auto
pytest -n auto --cov=app --cov-report=term-missing

# Linting
black --config pyproject.toml .
isort .
pyright
bandit -r app
```

### Frontend

```bash
cd frontend
npm install
npm run dev           # port 4000, proxies /api to backend
npm run build
npm run lint
npm run type-check
npm test
```

### Chrome extension

```bash
cd chrome-extension
npm run build         # → dist/
npm run watch
```
