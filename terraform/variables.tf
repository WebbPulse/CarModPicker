variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "environment must be 'production' or 'staging'"
  }
}

# Database
variable "db_password" {
  description = "Master password for the RDS PostgreSQL instance"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t4g.micro"
}

# App Runner compute
variable "app_runner_cpu" {
  description = "vCPU units for the App Runner service (256 = 0.25 vCPU)"
  type        = string
  default     = "256"
}

variable "app_runner_memory" {
  description = "Memory in MB for the App Runner service"
  type        = string
  default     = "512"
}

# Application secrets (stored in Secrets Manager, values injected via HCP workspace vars)
variable "secret_key" {
  description = "JWT signing secret for the FastAPI backend"
  type        = string
  sensitive   = true
}

variable "email_from" {
  description = "Sender address for transactional email"
  type        = string
  default     = "no-reply@carmodpicker.com"
}

# ---------------------------------------------------------------------------
# Cron / EventBridge Scheduler
# ---------------------------------------------------------------------------

variable "cron_secret_key" {
  description = "Shared secret injected as X-Admin-Cron-Key header by EventBridge Scheduler. Must match CRON_SECRET_KEY in App Runner."
  type        = string
  sensitive   = true
}

variable "crawler_default_category_id" {
  description = "Fallback category ID when part inference cannot determine a category"
  type        = number
  default     = 1
}

# Per-adapter crawler schedules (cron expression, delay, limit, enabled state)
# are managed by the backend from the adapter_schedules DB table. See
# app/api/services/adapter_schedule_service.py.
#
# Archive rescrape is intentionally never scheduled — admins trigger it
# manually from the admin UI.

# ---------------------------------------------------------------------------
# ECS Fargate — Crawler task compute
# ---------------------------------------------------------------------------
variable "crawler_ecs_cpu" {
  description = "CPU units for the ECS crawler task (512 = 0.5 vCPU)"
  type        = string
  default     = "512"
}

variable "crawler_ecs_memory" {
  description = "Memory in MB for the ECS crawler task"
  type        = string
  default     = "2048"
}

# ---------------------------------------------------------------------------
# FlareSolverr — Tier 2 (browser) crawler fetcher
#
# FlareSolverr is a standalone service that wraps a headless Chromium to
# solve Cloudflare managed JS challenges (JEGS, FCP Euro, etc.). The crawler
# posts to it when an adapter declares FETCHER_TIER="browser".
#
# Leave flaresolverr_url empty to keep the Tier 2 path disabled — adapters
# with FETCHER_TIER="browser" will raise a clear "not configured" error at
# first fetch rather than silently falling back to plain HTTP.
#
# To enable: run a FlareSolverr service somewhere reachable from the crawler
# (ECS Fargate service, EC2, or external) and set flaresolverr_url to its
# base URL (e.g. "http://flaresolverr.crawler.local:8191"). See
# backend/app/crawlers/README.md "Deploying FlareSolverr" for concrete steps.
# ---------------------------------------------------------------------------
variable "flaresolverr_url" {
  description = "Base URL of a running FlareSolverr service (empty to disable the browser-tier fetcher)"
  type        = string
  default     = ""
}

variable "flaresolverr_max_timeout_ms" {
  description = "Per-request timeout (ms) passed to FlareSolverr. 60s covers most challenges."
  type        = number
  default     = 60000
}

variable "flaresolverr_session_name" {
  description = "Name of the FlareSolverr session reused across crawler requests (amortizes challenge cost)"
  type        = string
  default     = "carmodpicker-crawler"
}

# ---------------------------------------------------------------------------
# Observability (Phase 2 — OBS-01 Sentry, OBS-02 EMF/alarms)
# ---------------------------------------------------------------------------

variable "sentry_dsn" {
  description = "Sentry DSN for backend error reporting. Empty = Sentry disabled (env-gate handles gracefully). Populated out-of-band via `aws secretsmanager put-secret-value` per D-55."
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentry_release" {
  description = "Sentry release identifier (typically git commit SHA, set by GitHub Actions per D-02)."
  type        = string
  default     = ""
}

variable "disabled_parse_alarms" {
  description = "Adapter names to exclude from per-adapter parse-failure alarms. Unused by Phase 2's composite alarm; declared here so Phase 3's per-adapter for_each conversion is reversible (D-31)."
  type        = list(string)
  default     = []
}

variable "enable_per_adapter_alarms" {
  description = "Master kill-switch for the per-adapter crawler parse-failure alarm fan-out. When set to false, all per-adapter alarms keep their state in CloudWatch but stop publishing ALARM/OK transitions to SNS (and therefore stop paging email subscribers). Use during retailer-wide outages or noisy incidents to prevent an email storm without tearing down the alarm resources themselves."
  type        = bool
  default     = true
}

variable "use_aggregate_crawler_alarm" {
  description = "When true (default), a single aggregate parse-failure alarm replaces the 107 per-adapter alarms (~$0.10/mo vs ~$10.80/mo). Set to false to restore per-adapter alarming."
  type        = bool
  default     = true
}
