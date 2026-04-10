variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-west-1"
}

variable "environment" {
  description = "Deployment environment (prod, staging)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["prod", "staging"], var.environment)
    error_message = "environment must be 'prod' or 'staging'"
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

variable "sendgrid_api_key" {
  description = "SendGrid API key for transactional email"
  type        = string
  sensitive   = true
}

variable "sendgrid_verify_email_template_id" {
  description = "SendGrid template ID for email verification"
  type        = string
  default     = ""
}

variable "sendgrid_reset_password_template_id" {
  description = "SendGrid template ID for password reset"
  type        = string
  default     = ""
}

variable "email_from" {
  description = "Sender address for transactional email"
  type        = string
  default     = "no-reply@carmodpicker.com"
}
