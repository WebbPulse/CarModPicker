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

variable "crawler_delay_sec" {
  description = "Seconds between requests per crawler adapter (passed in the schedule input)"
  type        = number
  default     = 5
}

# Crawler run schedule
# State is always DISABLED on first apply; use the admin UI to enable it.
# The expression set here is the initial value; it can also be changed from
# the admin UI without a Terraform apply (lifecycle.ignore_changes in scheduler.tf).
variable "crawler_cron_schedule" {
  description = "Initial EventBridge Scheduler cron expression for crawler runs (UTC). Editable from the admin UI after first apply."
  type        = string
  default     = "cron(0 2 1 * ? *)" # 2 AM UTC on the 1st of each month
}

# Archive rescrape is intentionally excluded — it is always triggered manually
# from the admin UI and should never run on a schedule.

# ---------------------------------------------------------------------------
# ECS Fargate — Crawler task compute
# ---------------------------------------------------------------------------
variable "crawler_ecs_cpu" {
  description = "CPU units for the ECS crawler task (256 = 0.25 vCPU)"
  type        = string
  default     = "256"
}

variable "crawler_ecs_memory" {
  description = "Memory in MB for the ECS crawler task"
  type        = string
  default     = "512"
}
