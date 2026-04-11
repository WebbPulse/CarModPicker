output "aws_account_id" {
  description = "AWS account ID Terraform is deploying into"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS region being deployed to"
  value       = data.aws_region.current.name
}

output "ecr_repository_url" {
  description = "ECR repository URL for the backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "app_runner_service_url" {
  description = "Default App Runner service URL (before custom domain is active)"
  value       = "https://${aws_apprunner_service.backend.service_url}"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (host:port)"
  value       = aws_db_instance.main.endpoint
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

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deployments"
  value       = aws_iam_role.github_actions_deploy.arn
}
