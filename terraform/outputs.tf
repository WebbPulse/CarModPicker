output "aws_account_id" {
  description = "AWS account ID Terraform is deploying into"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region being deployed to"
  value       = data.aws_region.current.name
}

output "ecr_repository_url" {
  description = "ECR repository URL for the backend image (legacy stack only)"
  value       = one(aws_ecr_repository.backend[*].repository_url)
}

output "app_runner_service_url" {
  description = "Default App Runner service URL (legacy stack only)"
  value       = local.legacy_stack ? "https://${aws_apprunner_service.backend[0].service_url}" : null
}

output "app_runner_service_arn" {
  description = "App Runner service ARN (legacy stack only)"
  value       = one(aws_apprunner_service.backend[*].arn)
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (host:port, legacy stack only)"
  value       = one(aws_db_instance.main[*].endpoint)
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (needed for cache invalidations)"
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_bucket" {
  description = "S3 bucket name for the frontend SPA"
  value       = aws_s3_bucket.frontend.bucket
}

output "frontend_url" {
  description = "Public origin of the SPA (custom domain, or the CloudFront hostname)"
  value       = local.frontend_url
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deployments"
  value       = aws_iam_role.github_actions_deploy.arn
}

output "api_invoke_url" {
  description = "HTTP API default endpoint"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "api_url" {
  description = "Public API origin the frontend should call (VITE_API_URL)"
  value       = local.api_url
}

output "lambda_function_name" {
  description = "Lambda API function name"
  value       = aws_lambda_function.api.function_name
}

output "lambda_function_arn" {
  description = "Lambda API function ARN"
  value       = aws_lambda_function.api.arn
}

output "lambda_artifacts_bucket" {
  description = "S3 bucket the deploy workflow uploads Lambda zips to"
  value       = aws_s3_bucket.lambda_artifacts.bucket
}

output "dynamodb_table_names" {
  description = "DynamoDB table names keyed by table suffix"
  value       = { for suffix, table in aws_dynamodb_table.tables : suffix => table.name }
}
