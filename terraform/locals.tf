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

  frontend_url = local.custom_domain ? "https://www.${var.domain_name}" : "https://${aws_cloudfront_distribution.frontend.domain_name}"
  api_url      = local.custom_domain && var.api_target == "lambda" ? "https://api.${var.domain_name}" : aws_apigatewayv2_api.api.api_endpoint
}
