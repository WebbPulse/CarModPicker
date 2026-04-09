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
        aws_secretsmanager_secret.sendgrid_api_key.arn,
        aws_secretsmanager_secret.sendgrid_verify_template.arn,
        aws_secretsmanager_secret.sendgrid_reset_template.arn,
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
          RAILWAY_ENVIRONMENT = "production"
          PORT                = "8000"
          BUCKET              = aws_s3_bucket.user_images.bucket
          AWS_REGION          = var.aws_region
          S3_ENDPOINT_URL     = "" # Empty → boto3 uses native AWS S3
          EMAIL_FROM          = var.email_from
        }

        # Sensitive values pulled from Secrets Manager at startup
        runtime_environment_secrets = {
          DATABASE_URL                       = aws_secretsmanager_secret_version.database_url.arn
          SECRET_KEY                         = aws_secretsmanager_secret_version.secret_key.arn
          SENDGRID_API_KEY                   = aws_secretsmanager_secret_version.sendgrid_api_key.arn
          SENDGRID_VERIFY_EMAIL_TEMPLATE_ID  = aws_secretsmanager_secret_version.sendgrid_verify_template.arn
          SENDGRID_RESET_PASSWORD_TEMPLATE_ID = aws_secretsmanager_secret_version.sendgrid_reset_template.arn
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

  tags = { Name = "${local.prefix}-backend" }
}

resource "aws_apprunner_custom_domain_association" "api" {
  service_arn          = aws_apprunner_service.backend.arn
  domain_name          = "api.carmodpicker.com"
  enable_www_subdomain = false
}
