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

variable "legacy_stack_enabled" {
  description = "Provision the RDS + App Runner stack. null = enabled in production, never in staging."
  type        = bool
  default     = null
  nullable    = true
}

variable "api_target" {
  description = "Which backend api.<domain_name> points at: 'legacy' (App Runner) or 'lambda' (HTTP API)."
  type        = string
  default     = "legacy"

  validation {
    condition     = contains(["legacy", "lambda"], var.api_target)
    error_message = "api_target must be 'legacy' or 'lambda'."
  }
}

variable "custom_domain_enabled" {
  description = "Provision Route53, ACM and custom hostnames. null = production or staging_profile 'full'."
  type        = bool
  default     = null
  nullable    = true
}

variable "domain_name" {
  description = "Apex domain served by this environment"
  type        = string
  default     = "carmodpicker.com"
}

variable "api_throttle_burst_limit" {
  description = "HTTP API $default stage throttling burst limit"
  type        = number
  default     = 50
}

variable "api_throttle_rate_limit" {
  description = "HTTP API $default stage steady-state requests per second"
  type        = number
  default     = 25
}

# Database
variable "db_password" {
  description = "Master password for the RDS PostgreSQL instance. Required only when the legacy stack is enabled."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
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


variable "staging_profile" {
  description = "How much of the stack this environment provisions. 'none' means the environment is switched off and must not be built. Set on the workspace by the WebbPulse-Organization workspace factory."
  type        = string
  default     = "full"

  validation {
    condition     = contains(["none", "reduced", "full"], var.staging_profile)
    error_message = "staging_profile must be one of 'none', 'reduced', or 'full'."
  }

  validation {
    condition     = var.staging_profile != "none"
    error_message = "Refusing to plan: staging_profile is 'none', so this environment is switched off and no resources should be created in it. To stand this environment up, change staging_profile to 'reduced' or 'full' on the workspace in WebbPulse-Organization/bootstrap/locals.tf."
  }
}
