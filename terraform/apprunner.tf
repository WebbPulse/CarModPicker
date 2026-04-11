# ---------------------------------------------------------------------------
# IAM — App Runner Access Role (used by App Runner to pull ECR images and
# inject Secrets Manager values as environment variables at startup)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "apprunner_access" {
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

resource "aws_iam_role_policy_attachment" "apprunner_access_ecr" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_iam_role_policy" "apprunner_access_secrets" {
  name = "secrets-manager-read"
  role = aws_iam_role.apprunner_access.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.secret_key.arn,
      ]
    }]
  })
}

# ---------------------------------------------------------------------------
# IAM — App Runner Instance Role (used by the running container to call AWS
# services: S3 for image uploads, Secrets Manager for any runtime reads)
# ---------------------------------------------------------------------------
resource "aws_iam_role" "apprunner_instance" {
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

# App Runner uses the instance role to inject runtime_environment_secrets.
resource "aws_iam_role_policy" "apprunner_instance_secrets" {
  name = "secrets-manager-read"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.secret_key.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_instance_ses" {
  name = "ses-send"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ses:SendEmail", "ses:SendRawMessage"]
      Resource = [
        "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/carmodpicker.com",
        "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:configuration-set/carmodpicker-transactional",
      ]
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_instance_s3" {
  name = "s3-user-images"
  role = aws_iam_role.apprunner_instance.id

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
        Resource = "${aws_s3_bucket.user_images.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:HeadBucket"]
        Resource = aws_s3_bucket.user_images.arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# App Runner Auto-Scaling Configuration
# min_size=1 / max_size=2 / max_concurrency=50 means a second instance only
# spins up when one instance is handling 50+ simultaneous requests.
# For a hobby project the second instance will rarely (if ever) run.
# ---------------------------------------------------------------------------
resource "aws_apprunner_auto_scaling_configuration_version" "backend" {
  auto_scaling_configuration_name = "${local.prefix}-backend"
  min_size        = 1
  max_size        = 2
  max_concurrency = 50
}

# ---------------------------------------------------------------------------
# App Runner Service
# ---------------------------------------------------------------------------
resource "aws_apprunner_service" "backend" {
  service_name = "${local.prefix}-backend"

  source_configuration {
    auto_deployments_enabled = false # Deployments triggered by the CD pipeline (push to ECR)

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.backend.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        # Non-sensitive runtime configuration
        runtime_environment_variables = {
          DEBUG               = "false"
          APP_ENVIRONMENT = "production"
          PORT                = "8000"
          BUCKET              = aws_s3_bucket.user_images.bucket
          AWS_REGION          = var.aws_region
          S3_ENDPOINT_URL     = "" # Empty → boto3 uses native AWS S3
          EMAIL_FROM          = var.email_from
        }

        # Sensitive values pulled from Secrets Manager at startup
        runtime_environment_secrets = {
          DATABASE_URL = aws_secretsmanager_secret_version.database_url.arn
          SECRET_KEY   = aws_secretsmanager_secret_version.secret_key.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.app_runner_cpu
    memory            = var.app_runner_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 20
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.backend.arn

  tags = { Name = "${local.prefix}-backend" }
}

# NOTE: Two-stage apply required for the custom domain association.
# Stage 1 (this apply): creates the association; App Runner provisions validation records.
# Stage 2: uncomment aws_route53_record.apprunner_validation in route53.tf,
#           then push → apply to add the DNS validation records.
resource "aws_apprunner_custom_domain_association" "api" {
  service_arn          = aws_apprunner_service.backend.arn
  domain_name          = "api.carmodpicker.com"
  enable_www_subdomain = false
}
