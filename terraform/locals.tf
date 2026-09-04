locals {
  project = "carmodpicker"

  # Use as a prefix for all resource names: "${local.prefix}-vpc", etc.
  prefix = "${local.project}-${var.environment}"

  # Applied to every resource via provider default_tags.
  # Add resource-specific tags inline where needed.
  common_tags = {
    Project     = local.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  legacy_stack  = var.environment == "production" && coalesce(var.legacy_stack_enabled, true)
  custom_domain = coalesce(var.custom_domain_enabled, var.environment == "production" || var.staging_profile == "full")

  domain_name       = var.environment == "production" ? var.domain_name : "staging.${var.domain_name}"
  active_domain     = local.custom_domain ? local.domain_name : var.domain_name
  parent_delegation = var.environment == "staging" && local.custom_domain

  email_from = coalesce(var.email_from, "no-reply@${local.active_domain}")

  frontend_url = local.custom_domain ? "https://www.${local.domain_name}" : "https://${aws_cloudfront_distribution.frontend.domain_name}"
  api_url      = local.custom_domain && var.api_target == "lambda" ? "https://api.${local.domain_name}" : aws_apigatewayv2_api.api.api_endpoint

  dev_origins     = ["http://localhost", "http://localhost:3000", "http://localhost:4000"]
  allowed_origins = var.environment == "production" ? "" : join(",", concat(local.dev_origins, local.custom_domain ? ["https://${local.domain_name}", "https://www.${local.domain_name}"] : [local.frontend_url]))
}
