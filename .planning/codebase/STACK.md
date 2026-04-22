# Technology Stack

**Analysis Date:** 2026-04-22

## Languages

**Primary:**
- Python 3.13 - Backend APIs and data processing (`backend/`)
- TypeScript 5.8.3 - Frontend and Chrome extension type-safe JavaScript (`frontend/`, `chrome-extension/`)
- JavaScript (ES modules) - Build tooling and configuration

**Secondary:**
- SQL - PostgreSQL database queries and migrations
- HCL (Terraform) - Infrastructure as Code (`terraform/`)

## Runtime

**Environment:**
- Python 3.13 (backend)
- Node.js 22 (frontend/chrome extension, specified in `frontend/.nvmrc`)

**Package Managers:**
- pip (Python) - Backend dependency management
- npm (Node.js) - Frontend and extension package management
- Lockfile: `backend/requirements.txt` (pinned versions), `frontend/package-lock.json`, `chrome-extension/package-lock.json`

## Frameworks

**Core:**
- FastAPI 0.128.0 - REST API framework for backend (`backend/app/main.py`)
- React 19.1.0 - Frontend UI library (`frontend/`, `chrome-extension/`)
- React Router 7.6.0 - Client-side routing (`frontend/src/`)

**Build/Dev:**
- Vite 6.3.5 (frontend), 6.4.2 (extension) - JavaScript build and dev server
- Uvicorn 0.34.0 - ASGI server for FastAPI
- TypeScript compiler (tsc) - Type checking and compilation
- SWC (@vitejs/plugin-react-swc 3.9.0) - Fast JSX transpilation

**Testing:**
- pytest 9.0.3 - Python test runner (backend)
- pytest-asyncio 1.3.0 - Async test support
- pytest-xdist 3.8.0 - Parallel test execution (`-n auto`)
- pytest-cov 6.2.1 - Coverage reporting
- vitest 3.2.4 - Vitest test runner (frontend)
- @testing-library/react 16.1.0 - React component testing

**Code Quality:**
- black 26.3.1 - Python code formatter
- isort 6.0.1 - Python import sorting
- mypy 1.17.1 - Python static type checker
- eslint 9.25.0 - JavaScript linting
- prettier 3.5.3 - Code formatter
- pyright - TypeScript-like type checking for Python (via config in `backend/pyproject.toml`)
- bandit - Security scanner for Python

## Key Dependencies

**Critical:**
- SQLAlchemy 2.0.41 - ORM for database models and queries (`backend/app/api/models/`)
- Pydantic 2.11.3 - Request/response validation (`backend/app/api/schemas/`)
- Alembic 1.16.2 - Database migration tool (`backend/alembic/`)
- psycopg2-binary 2.9.10 - PostgreSQL database adapter

**Authentication & Security:**
- python-jose[cryptography] 3.5.0 - JWT token signing/verification (HS256 algorithm)
- bcrypt 4.3.0 - Password hashing
- pyotp 2.9.0 - TOTP 2FA implementation
- webauthn 2.5.2 - WebAuthn/passkey support
- google-auth 2.45.0 - Google OAuth verification
- @simplewebauthn/browser 11.0.0 - Passkey registration/authentication (frontend)
- @react-oauth/google 0.13.5 - Google Sign-In integration (frontend)

**Image Processing & Storage:**
- boto3 1.42.91 - AWS SDK (S3, SES, ECS, EventBridge)
- boto3-stubs[s3,sesv2] 1.42.91 - Type stubs for boto3
- Pillow 12.2.0 - Image processing (resize, validation)

**Web Crawling:**
- beautifulsoup4 4.12.3 - HTML parsing for product data extraction
- requests 2.33.0 - HTTP client for basic scraping
- curl_cffi 0.15.0 - Tier 1 crawler (TLS impersonation to bypass Cloudflare)
- defusedxml 0.7.1 - XML security (prevent XXE attacks)

**UI/Styling:**
- Tailwind CSS 4.1.7 - Utility-first CSS framework
- @tailwindcss/vite 4.1.7 - Tailwind Vite plugin
- react-icons 5.5.0 - Icon library
- react-markdown 10.1.0 - Markdown rendering

**Email:**
- React Email (compiled HTML templates in `backend/app/core/email_templates/`)
- Sent via boto3 SES client

**Development & Testing:**
- httpx 0.28.1 - HTTP client for backend integration tests
- moto[s3] 5.1.22 - S3 mock for testing without AWS
- jsdom 25.0.1 - DOM implementation for frontend tests
- puppeteer 24.41.0 - Browser automation for pre-rendering
- axios 1.15.0 - HTTP client for frontend API calls
- watchdog 6.0.0 - File change detection

**Utilities:**
- python-dotenv 1.2.2 - Load `.env` files
- python-multipart 0.0.26 - Multipart form data parsing
- python-json-logger 4.1.0 - Structured JSON logging
- uuid6 2025.0.1 - UUIDv6/v7 generation
- qrcode[pil] 7.4.2 - QR code generation for TOTP setup

## Configuration

**Environment:**
- `.env` file (not committed) - Local development secrets and config
- AWS Secrets Manager - Production secrets (DATABASE_URL, SECRET_KEY, EMAIL_FROM)
- Environment variables injected by Terraform on App Runner

**Build:**
- `backend/pyproject.toml` - Tool config (black, isort, mypy, bandit)
- `backend/Dockerfile` - Multi-stage build for production image
- `frontend/vite.config.ts` - Vite build config, API proxy setup
- `frontend/eslint.config.js` - ESLint rules
- `backend/alembic.ini` - Database migration settings

**Docker Local Dev:**
- `backend/docker-compose.yml` - PostgreSQL 16 + MinIO (S3 mock)
  - Database: postgres:16 on port 5432
  - S3 mock: minio:latest on ports 9000 (API), 9001 (console)

## Platform Requirements

**Development:**
- Python 3.13
- Node.js 22+ (see `frontend/.nvmrc`)
- Docker & Docker Compose (for local Postgres + MinIO)
- Terraform (for infrastructure changes)

**Production:**
- AWS App Runner - Managed container service for backend
- AWS RDS PostgreSQL 16 - Managed database (storage: 20-100 GB with auto-scaling)
- AWS S3 - Image storage (private buckets)
- AWS SES - Transactional email
- AWS ECS Fargate - Optional crawler task execution
- AWS EventBridge Scheduler - Crawler scheduling
- AWS CloudFront - CDN for frontend distribution
- CloudFlare DNS - Domain management
- Domain: carmodpicker.com with staging.carmodpicker.com

---

*Stack analysis: 2026-04-22*
