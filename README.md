# CarModPicker

A web app for tracking car modifications. Users manage cars and build lists, browse a global parts catalog, and log builds in forum-style threads. A companion Chrome extension scrapes parts from retailer pages.

**Stack:** FastAPI (Python 3.13) · React 19 (TypeScript) · PostgreSQL · AWS (App Runner + RDS)

---

## Structure

```
backend/          FastAPI app, Alembic migrations, crawler infrastructure
frontend/         React + Vite + Tailwind CSS 4
chrome-extension/ Chrome extension for scraping parts from retailer pages
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

# Tests
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

---

## Crawlers

Per-retailer scrapers that populate the global parts catalog. Run from `backend/`:

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=wheels
python -m app.crawlers --adapter a90shop --limit 10
```

See `backend/app/crawlers/README.md` for full usage and how to add a new retailer adapter.
