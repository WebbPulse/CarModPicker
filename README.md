# CarModPicker

A web app for tracking car modifications. Users manage cars and build lists, attach parts to phased builds, and log progress in forum-style threads. A companion Chrome extension captures parts from retailer pages.

**Stack:** FastAPI (Python 3.13) · React 19 (TypeScript) · PostgreSQL · AWS (App Runner + RDS)

**License:** MIT

---

## Structure

```
backend/          FastAPI app, Alembic migrations
frontend/         React + Vite + Tailwind CSS 4
chrome-extension/ Captures part data from retailer pages
terraform/        AWS infrastructure
scripts/          Utility scripts
```

---

## Development

**Prerequisites:** Python 3.13, Node 20+, Docker (for local PostgreSQL)

### Backend

```bash
cd backend
docker-compose up -d                          # start PostgreSQL
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# Migrations (always autogenerate, never write manually)
alembic revision --autogenerate -m "description"
alembic upgrade head

# Tests (SQLite in-memory, no Postgres required)
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
