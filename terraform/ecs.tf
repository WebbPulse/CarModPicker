# ---------------------------------------------------------------------------
# ECS Fargate — Crawler task
#
# The crawler runs as an on-demand Fargate task instead of a background
# asyncio task in App Runner. This gives true "spin-up, run, tear-down"
# lifecycle: billing stops the moment the container exits, and an App Runner
# restart or scale event cannot kill an in-progress crawl.
#
# Network: public subnet + assigned public IP. No NAT Gateway required —
# the same egress pattern used for RDS (publicly accessible, auth + SSL).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# ECS Cluster (Fargate-only, no EC2 capacity)
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "crawler" {
  name = "${local.prefix}-crawler"

  setting {
    name  = "containerInsights"
    value = "disabled" # awslogs driver covers per-task logging; Container Insights adds cost.
  }

  tags = { Name = "${local.prefix}-crawler" }
}

resource "aws_ecs_cluster_capacity_providers" "crawler" {
  cluster_name       = aws_ecs_cluster.crawler.name
  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}


# ---------------------------------------------------------------------------
# CloudWatch Log Group (30-day retention; crawler tasks are ephemeral)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "crawler" {
  name              = "/ecs/${local.prefix}-crawler"
  retention_in_days = 30

  tags = { Name = "${local.prefix}-crawler" }
}


# ---------------------------------------------------------------------------
# IAM — ECS Task Execution Role
# Used by the ECS control plane to: pull the image from ECR, inject
# DATABASE_URL from Secrets Manager, and write logs to CloudWatch.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.prefix}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.prefix}-ecs-task-execution" }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_secrets" {
  name = "secrets-manager-read"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.database_url.arn,
        aws_secretsmanager_secret.secret_key.arn,
      ]
    }]
  })
}


# ---------------------------------------------------------------------------
# IAM — ECS Task Role
# Used by the container at runtime: S3 for HTML archive, SES for job emails.
# Does NOT need Secrets Manager — DATABASE_URL is injected by the exec role.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name = "${local.prefix}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.prefix}-ecs-task" }
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "s3-buckets"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:HeadObject"]
        Resource = [
          "${aws_s3_bucket.user_images.arn}/*",
          "${aws_s3_bucket.crawl_data.arn}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:HeadBucket"]
        Resource = [aws_s3_bucket.user_images.arn, aws_s3_bucket.crawl_data.arn]
      },
    ]
  })
}

resource "aws_iam_role_policy" "ecs_task_ses" {
  name = "ses-send"
  role = aws_iam_role.ecs_task.id

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


# ---------------------------------------------------------------------------
# Security Group — Crawler task
# Outbound only: internet (HTTP/S for crawling), RDS port 5432, AWS APIs.
# No inbound rules needed; the task initiates all connections.
# ---------------------------------------------------------------------------
resource "aws_security_group" "crawler_task" {
  name        = "${local.prefix}-crawler-task-sg"
  description = "ECS Fargate crawler task - outbound only"
  vpc_id      = aws_vpc.main.id

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.prefix}-crawler-task-sg" }
}


# ---------------------------------------------------------------------------
# ECS Task Definition
# Image: same ECR image as App Runner. Entry point overridden to the ECS
# runner module. Per-run params (adapters, limits, job_id, etc.) are injected
# as environment variable overrides at RunTask time by App Runner.
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "crawler" {
  family                   = "${local.prefix}-crawler"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.crawler_ecs_cpu
  memory                   = var.crawler_ecs_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "crawler"
    image     = "${aws_ecr_repository.backend.repository_url}:latest"
    command   = ["python", "-m", "app.crawlers.ecs_runner"]
    essential = true

    # Static environment — same values App Runner gets, minus auth secrets.
    # Per-run values (adapters, job_id, etc.) are injected at RunTask time.
    environment = [
      { name = "APP_ENVIRONMENT",     value = "production" },
      { name = "RAILWAY_ENVIRONMENT", value = "production" },
      { name = "USER_IMAGES_BUCKET",  value = aws_s3_bucket.user_images.bucket },
      { name = "CRAWL_BUCKET",        value = aws_s3_bucket.crawl_data.bucket },
      { name = "AWS_REGION",          value = var.aws_region },
      { name = "S3_ENDPOINT_URL",     value = "" },
      { name = "EMAIL_FROM",          value = var.email_from },
      { name = "EMAIL_ENABLED",       value = "true" },
    ]

    secrets = [
      {
        name      = "DATABASE_URL"
        valueFrom = aws_secretsmanager_secret.database_url.arn
      },
      # Suppress "SECRET_KEY is empty in production" warning — the crawler
      # doesn't use JWTs but shares config.py with the API server.
      {
        name      = "SECRET_KEY"
        valueFrom = aws_secretsmanager_secret.secret_key.arn
      },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.crawler.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = { Name = "${local.prefix}-crawler" }
}
