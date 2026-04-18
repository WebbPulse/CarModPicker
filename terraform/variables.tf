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
  description = "CPU units for the ECS crawler task (256 = 0.25 vCPU)"
  type        = string
  default     = "256"
}

variable "crawler_ecs_memory" {
  description = "Memory in MB for the ECS crawler task"
  type        = string
  default     = "512"
}
