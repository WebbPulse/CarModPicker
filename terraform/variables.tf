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

