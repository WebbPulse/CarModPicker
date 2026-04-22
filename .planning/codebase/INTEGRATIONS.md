# External Integrations

**Analysis Date:** 2026-04-22

## APIs & External Services

**Google OAuth:**
- Google Sign-In for account creation and linking
  - SDK/Client: `google-auth` 2.45.0 (backend), `@react-oauth/google` 0.13.5 (frontend)
  - Frontend sends ID token to `POST /api/auth/google/signin` (`backend/app/api/endpoints/auth.py`)
  - Backend verifies token with `GOOGLE_CLIENT_ID` (hardcoded in `backend/app/core/config.py`)
  - Env var: `GOOGLE_CLIENT_ID` (not a secret, embedded in frontend)

**Cloudflare/FlareSolverr:**
- Tier 2 browser crawler for bypassing Cloudflare managed JS challenges
  - Client: `curl_cffi` 0.15.0 (Tier 1 - TLS impersonation)
  - Service: FlareSolverr instance (external service)
  - Configured in `backend/app/core/config.py`:
    - `FLARESOLVERR_URL` - Base URL of FlareSolverr instance (e.g., http://flaresolverr:8191)
    - `FLARESOLVERR_MAX_TIMEOUT_MS` - Per-request timeout (default 60000ms)
    - `FLARESOLVERR_SESSION_NAME` - Reused session across requests (default "carmodpicker-crawler")
  - Used by adapters with `FETCHER_TIER="browser"` in `backend/app/crawlers/adapters/`
  - When unconfigured, browser-tier adapters fail with clear error (no fallback)

## Data Storage

**Databases:**
- **PostgreSQL 16** (RDS in production, Docker locally)
  - Connection: `DATABASE_URL` env var (production via Secrets Manager, dev via `.env`)
  - Client: SQLAlchemy 2.0.41 ORM (`backend/app/api/models/`)
  - Database name: "carmodpicker"
  - User: "carmodpicker" (password in Secrets Manager)
  - Connection string requires `ssl_mode=require` in production
  - Tables: 22+ (users, cars, parts, build_lists, crawler_schedules, background_jobs, etc.)
  - See `backend/alembic/versions/` for migration history

**File Storage:**
- **AWS S3** (production) or MinIO (local dev)
  - Client: boto3 1.42.91 (`backend/app/api/services/storage_service.py`)
  - Buckets:
    - `carmodpicker-prod-user-images` - User uploads (private, presigned URLs for serving)
    - `carmodpicker-prod-crawl-html` - Crawler HTML snapshots
  - Configuration (`backend/app/core/config.py`):
    - `USER_IMAGES_BUCKET` / `S3_BUCKET_NAME` - User image bucket
    - `CRAWL_BUCKET` - Crawler HTML bucket
    - `S3_ENDPOINT_URL` / `AWS_ENDPOINT_URL` - Custom endpoint (MinIO locally)
    - `AWS_REGION` / `AWS_DEFAULT_REGION` - Region selection
    - Credentials: Empty on App Runner (uses instance IAM role), can override with `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
  - Image constraints: max 10 MB, extensions: jpg, jpeg, png, gif, webp
  - Presigned URLs expire after 24 hours (configurable via `PRESIGNED_URL_EXPIRATION`)

**Caching:**
- None configured; rate limiting uses in-memory tracking (`backend/app/api/middleware/rate_limiter.py`)
- Note: For production scaling, consider Redis for distributed rate limiting

## Authentication & Identity

**Auth Provider:** Custom + Third-party integrations
- **JWT (HS256):**
  - Secret: `SECRET_KEY` env var (required in production, via Secrets Manager)
  - Algorithm: HS256 (HMAC), not ECDSA
  - Token expiry: `ACCESS_TOKEN_EXPIRE_MINUTES` (user-configurable, clamped to 15–10080 minutes / 7 days)
  - Implementation: `python-jose[cryptography]` 3.5.0
  - Endpoint: `POST /api/auth/login` sends username + password

**Password Security:**
- Hashing: bcrypt 4.3.0
- Implementation: `backend/app/api/endpoints/auth.py`

**TOTP 2FA:**
- Framework: `pyotp` 2.9.0
- QR code generation: `qrcode[pil]` 7.4.2
- Setup endpoint: `POST /api/auth/totp/setup` (returns secret + QR code)
- Verification endpoint: `POST /api/auth/totp/verify`
- Implementation: `backend/app/api/endpoints/auth.py`

**WebAuthn/Passkeys:**
- Framework: `webauthn` 2.5.2 (backend), `@simplewebauthn/browser` 11.0.0 (frontend)
- RP ID: "localhost" (dev), "staging.carmodpicker.com" (staging), "carmodpicker.com" (prod)
- RP Name: "CarModPicker"
- Allowed origins: http://localhost:4000, https://carmodpicker.com, https://staging.carmodpicker.com (configured in `backend/app/core/config.py`)
- Registration: `POST /api/auth/webauthn/register/begin` and `POST /api/auth/webauthn/register/complete`
- Authentication: `POST /api/auth/webauthn/authenticate/begin` and `POST /api/auth/webauthn/authenticate/complete`
- Implementation: `backend/app/api/endpoints/auth.py`, `backend/app/api/schemas/webauthn.py`

**Google OAuth:**
- Frontend sends ID token from `@react-oauth/google` widget
- Backend validates with Google's public key using `google-auth`
- Endpoint: `POST /api/auth/google/signin`, `POST /api/auth/google/signup`, `POST /api/auth/google/connect`
- User linking: Multiple OAuth accounts can link to one user

**Email Verification:**
- Required before login is allowed
- Endpoint: `POST /api/auth/verify-email`

## Email & Notifications

**Email Service:** AWS SES
- Configuration set: `carmodpicker-transactional` (terraform: `terraform/ses.tf`)
- Domain identity: carmodpicker.com (DKIM verified in Route 53)
- Custom MAIL FROM domain: bounce.carmodpicker.com (SPF alignment)
- Client: boto3 1.42.91 (sesv2 API)
- Implementation: `backend/app/core/email.py`
- Configuration:
  - `EMAIL_ENABLED` - Enable/disable email sending (false by default, set true in production)
  - `EMAIL_FROM` - Sender address (e.g., noreply@carmodpicker.com)
  - `AWS_REGION` - SES region

**Email Templates:**
- Location: `backend/app/core/email_templates/` (compiled HTML from React Email)
- Types:
  - Email verification (`verify_email.html`)
  - Password reset (`reset_password.html`)
  - Background job notifications (crawler run results)
- Sent via: `_send()` function in `backend/app/core/email.py`

**SES Event Notifications:**
- SNS topic: `carmodpicker-{APP_ENVIRONMENT}-ses-notifications`
- Events monitored: BOUNCE, COMPLAINT, DELIVERY_DELAY
- Subscription: tyler@webbpulse.com (requires confirmation from AWS)
- Terraform: `terraform/ses.tf`

## Rate Limiting

**Framework:** Custom in-memory rate limiter
- Implementation: `backend/app/api/middleware/rate_limiter.py`
- Enabled by default; disable with `ENABLE_RATE_LIMITING=false`
- Limits (configurable in `backend/app/core/config.py`):
  - Default: 60 req/min, 1000 req/hour
  - GET requests: 200 req/min, 20000 req/hour
  - Auth endpoints: 10 req/min, 100 req/hour
  - Admin endpoints: 30 req/min, 300 req/hour
- Tracking: Per-IP address, separate buckets for minute/hour windows
- Response: 429 Too Many Requests when limit exceeded
- Note: For distributed deployments, migrate to Redis

## CI/CD & Deployment

**Hosting:**
- **Backend:** AWS App Runner (managed containers)
  - Image: Pushed to ECR by GitHub Actions
  - Service name: `carmodpicker-{APP_ENVIRONMENT}`
  - Port: 8000 (internal), exposed via CloudFront
  - Environment: Set via App Runner env vars (injected by Terraform)

- **Frontend:** AWS CloudFront + S3
  - Distribution: CloudFront CDN (terraform: `terraform/cloudfront.tf`)
  - Origin: S3 bucket for static site
  - Custom domain: carmodpicker.com, staging.carmodpicker.com
  - CloudFront functions: `terraform/cloudfront_functions/` for request/response transforms

**CI Pipeline:**
- GitHub Actions (`.github/workflows/`)
- Builds:
  - Backend: Docker image → ECR
  - Frontend: npm build → S3 (prerender with puppeteer)
  - Chrome extension: npm build → dist/
- IAM: GitHub Actions role for ECR push, S3 deployment (`terraform/iam_github_actions.tf`)

**Secrets Management:**
- AWS Secrets Manager (`terraform/secretsmanager.tf`)
- Secrets injected as env vars on App Runner at runtime
- List includes: `DATABASE_URL`, `SECRET_KEY`, `EMAIL_FROM`, etc.

**Database Migrations:**
- Tool: Alembic (SQLAlchemy migrations)
- Location: `backend/alembic/versions/`
- Migration command: `alembic revision --autogenerate -m "description"`
- Upgrade: `alembic upgrade head`
- Manual edits: Never; always use autogenerate

## Monitoring & Observability

**Error Tracking:** 
- None detected (no Sentry, LogRocket, etc.)
- Error handling: Custom middleware in `backend/app/api/middleware/error_handler.py`

**Logs:**
- Backend: Structured JSON logging via `python-json-logger` 4.1.0
- Output: CloudWatch (configured in RDS terraform: `terraform/rds.tf`)
- Log exports: PostgreSQL logs and upgrade logs
- Request context: Correlation ID + user ID via `RequestContextFilter` (`backend/app/core/log_context.py`)
- Log level: INFO by default

**Monitoring & Alerts:**
- CloudWatch metrics and alarms (terraform: `terraform/monitoring.tf`)
- Performance Insights: Enabled on RDS (7-day free retention)

## Webhooks & Callbacks

**Incoming:**
- Chrome Extension POST `/api/crawled-pages/scrape` - Extension submits scraped product data
- Chrome Extension POST `/api/crawled-pages/html` - Extension submits full page HTML
- EventBridge Scheduler callback → `POST /api/cron/run-crawler-schedule` - Crawler scheduling
  - Auth: `X-Admin-Cron-Key` header (shared secret in `CRON_SECRET_KEY`)

**Outgoing:**
- None detected (no third-party webhooks configured)

## Background Jobs & Scheduling

**Crawler Scheduling:**
- Framework: AWS EventBridge Scheduler (terraform: `terraform/scheduler.tf`)
- Execution modes:
  1. Local background task (async in-process)
  2. ECS Fargate task (durable, spin-up/run/teardown)
- Configuration:
  - `CRAWLER_ECS_CLUSTER` - ECS cluster name
  - `CRAWLER_ECS_TASK_DEFINITION` - Task definition ARN
  - `CRAWLER_ECS_SUBNETS` - Public subnets for Fargate
  - `CRAWLER_ECS_SECURITY_GROUP` - Security group for Fargate
  - `SCHEDULER_GROUP_NAME` - EventBridge scheduler group
  - `SCHEDULER_CRAWLER_SCHEDULE_NAME` - Name prefix for per-adapter schedules
  - `SCHEDULER_TARGET_EVENT_BUS_ARN` - Event bus ARN
  - `SCHEDULER_TARGET_ROLE_ARN` - IAM role for PutEvents
- Job tracking: `background_jobs` table in PostgreSQL
- Service: `backend/app/api/services/crawler_schedule_service.py`

**Job Status Tracking:**
- Table: `background_jobs` (ORM: `backend/app/api/models/background_job.py`)
- Fields: id, job_type, status, worker_instance_id, created_at, started_at, completed_at, error
- Status values: pending, running, completed, failed, cancelled
- Cleanup: Startup sweep to mark orphan jobs (failed workers) as failed

## Environment Configuration

**Required env vars (production):**
- `DATABASE_URL` - PostgreSQL connection string (Secrets Manager)
- `SECRET_KEY` - JWT signing key (Secrets Manager)
- `EMAIL_FROM` - SES sender address (Secrets Manager)
- `GOOGLE_CLIENT_ID` - Google OAuth client ID (hardcoded, not secret)
- `AWS_REGION` - Region for S3 and SES
- `USER_IMAGES_BUCKET` - S3 bucket for images
- `CRAWL_BUCKET` - S3 bucket for crawler HTML
- `CRON_SECRET_KEY` - Shared secret for EventBridge callbacks

**Optional env vars (with defaults):**
- `APP_ENVIRONMENT` - "development", "staging", or "production" (default: "development")
- `DEBUG` - Enable FastAPI debug mode (default: false)
- `ENABLE_RATE_LIMITING` - Enable rate limiting (default: true)
- `FLARESOLVERR_URL` - FlareSolverr endpoint (empty by default, disables Tier 2)
- `CRAWLER_SERVICE_ACCOUNT_USERNAME` - Crawler account name (default: "crawler")
- `MAX_IMAGE_SIZE_MB` - Max upload size (default: 10)
- `PRESIGNED_URL_EXPIRATION` - URL expiry in seconds (default: 86400 = 24 hours)

**Secrets location:**
- Production: AWS Secrets Manager (injected at runtime by Terraform)
- Development: `.env` file (not committed, created locally)
- Local S3: MinIO (via docker-compose, credentials: minioadmin / minioadmin)

---

*Integration audit: 2026-04-22*
