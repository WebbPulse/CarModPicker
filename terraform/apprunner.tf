# ---------------------------------------------------------------------------
# IAM — App Runner Access Role (used by App Runner to pull ECR images and
# inject Secrets Manager values as environment variables at startup)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "apprunner_access" {
  count = local.legacy_stack ? 1 : 0

  name = "${local.prefix}-apprunner-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

moved {
  from = aws_iam_role.apprunner_access
  to   = aws_iam_role.apprunner_access[0]
}

resource "aws_iam_role_policy_attachment" "apprunner_access_ecr" {
  count = local.legacy_stack ? 1 : 0

  role       = aws_iam_role.apprunner_access[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

moved {
  from = aws_iam_role_policy_attachment.apprunner_access_ecr
  to   = aws_iam_role_policy_attachment.apprunner_access_ecr[0]
}

resource "aws_iam_role_policy" "apprunner_access_secrets" {
  count = local.legacy_stack ? 1 : 0

  name = "secrets-manager-read"
  role = aws_iam_role.apprunner_access[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url[0].arn,
        aws_secretsmanager_secret.secret_key.arn,
        aws_secretsmanager_secret.sentry_dsn.arn,
      ]
    }]
  })
}

moved {
  from = aws_iam_role_policy.apprunner_access_secrets
  to   = aws_iam_role_policy.apprunner_access_secrets[0]
}

# ---------------------------------------------------------------------------
# IAM — App Runner Instance Role (used by the running container to call AWS
# services: S3 for image uploads, Secrets Manager for any runtime reads)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "apprunner_instance" {
  count = local.legacy_stack ? 1 : 0

  name = "${local.prefix}-apprunner-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

moved {
  from = aws_iam_role.apprunner_instance
  to   = aws_iam_role.apprunner_instance[0]
}

# App Runner uses the instance role to inject runtime_environment_secrets.
resource "aws_iam_role_policy" "apprunner_instance_secrets" {
  count = local.legacy_stack ? 1 : 0

  name = "secrets-manager-read"
  role = aws_iam_role.apprunner_instance[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url[0].arn,
        aws_secretsmanager_secret.secret_key.arn,
        aws_secretsmanager_secret.sentry_dsn.arn,
      ]
    }]
  })
}

moved {
  from = aws_iam_role_policy.apprunner_instance_secrets
  to   = aws_iam_role_policy.apprunner_instance_secrets[0]
}

resource "aws_iam_role_policy" "apprunner_instance_ses" {
  count = local.legacy_stack ? 1 : 0

  name   = "ses-send"
  role   = aws_iam_role.apprunner_instance[0].id
  policy = data.aws_iam_policy_document.ses_send.json
}

moved {
  from = aws_iam_role_policy.apprunner_instance_ses
  to   = aws_iam_role_policy.apprunner_instance_ses[0]
}

resource "aws_iam_role_policy" "apprunner_instance_s3" {
  count = local.legacy_stack ? 1 : 0

  name = "s3-buckets"
  role = aws_iam_role.apprunner_instance[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:HeadObject",
        ]
        Resource = [
          "${aws_s3_bucket.user_images.arn}/*",
          "${aws_s3_bucket.crawl_data.arn}/*",
        ]
      },
      {
        Effect = "Allow"
        Action = ["s3:ListBucket", "s3:HeadBucket"]
        Resource = [
          aws_s3_bucket.user_images.arn,
          aws_s3_bucket.crawl_data.arn,
        ]
      }
    ]
  })
}

moved {
  from = aws_iam_role_policy.apprunner_instance_s3
  to   = aws_iam_role_policy.apprunner_instance_s3[0]
}

# ---------------------------------------------------------------------------
# App Runner Auto-Scaling Configuration
# min_size=1 / max_size=2 / max_concurrency=50 means a second instance only
# spins up when one instance is handling 50+ simultaneous requests.
# For a hobby project the second instance will rarely (if ever) run.
# ---------------------------------------------------------------------------
resource "aws_apprunner_auto_scaling_configuration_version" "backend" {
  count = local.legacy_stack ? 1 : 0

  auto_scaling_configuration_name = "${local.prefix}-backend"
  min_size                        = 1
  max_size                        = 2
  max_concurrency                 = 50
}

moved {
  from = aws_apprunner_auto_scaling_configuration_version.backend
  to   = aws_apprunner_auto_scaling_configuration_version.backend[0]
}

# ---------------------------------------------------------------------------
# App Runner Service
# ---------------------------------------------------------------------------
resource "aws_apprunner_service" "backend" {
  count = local.legacy_stack ? 1 : 0

  service_name = "${local.prefix}-backend"

  source_configuration {
    auto_deployments_enabled = false # Deployments triggered by the CD pipeline (push to ECR)

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access[0].arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.backend[0].repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        # Non-sensitive runtime configuration
        runtime_environment_variables = { for key, value in {
          DEBUG              = "false"
          APP_ENVIRONMENT    = "production"
          PORT               = "8000"
          USER_IMAGES_BUCKET = aws_s3_bucket.user_images.bucket
          CRAWL_BUCKET       = aws_s3_bucket.crawl_data.bucket
          AWS_REGION         = var.aws_region
          S3_ENDPOINT_URL    = "" # Empty → boto3 uses native AWS S3
          EMAIL_FROM         = var.email_from
          EMAIL_ENABLED      = "true"

          # Observability (Phase 2 / OBS-01 + OBS-02). SENTRY_RELEASE is the
          # git commit SHA baked at Docker build time; SENTRY_SERVICE_NAME tags
          # exceptions with the App Runner process identity; AWS_EMF_ENVIRONMENT
          # forces the aws-embedded-metrics stdout sink (RESEARCH Landmine 4 —
          # required for plan 02-03 EMF emission to reach CloudWatch Logs).
          SENTRY_RELEASE      = var.sentry_release
          SENTRY_SERVICE_NAME = "apprunner-backend"
          AWS_EMF_ENVIRONMENT = "Local"
        } : key => value if value != "" }

        # Sensitive values pulled from Secrets Manager at startup
        runtime_environment_secrets = {
          DATABASE_URL = aws_secretsmanager_secret_version.database_url[0].arn
          SECRET_KEY   = aws_secretsmanager_secret_version.secret_key.arn
          SENTRY_DSN   = aws_secretsmanager_secret_version.sentry_dsn.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.app_runner_cpu
    memory            = var.app_runner_memory
    instance_role_arn = aws_iam_role.apprunner_instance[0].arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 20
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend[0].arn

  tags = { Name = "${local.prefix}-backend" }
}

moved {
  from = aws_apprunner_service.backend
  to   = aws_apprunner_service.backend[0]
}

# NOTE: Two-stage apply required for the custom domain association.
# Stage 1 (this apply): creates the association; App Runner provisions validation records.
# Stage 2: uncomment aws_route53_record.apprunner_validation in route53.tf,
#           then push → apply to add the DNS validation records.
resource "aws_apprunner_custom_domain_association" "api" {
  count = local.legacy_stack && local.custom_domain ? 1 : 0

  service_arn          = aws_apprunner_service.backend[0].arn
  domain_name          = "api.${var.domain_name}"
  enable_www_subdomain = false
}

moved {
  from = aws_apprunner_custom_domain_association.api
  to   = aws_apprunner_custom_domain_association.api[0]
}
