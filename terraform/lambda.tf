data "aws_iam_policy_document" "ses_send" {
  statement {
    actions = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = [
      "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*",
      "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:configuration-set/${aws_sesv2_configuration_set.transactional.configuration_set_name}",
    ]
  }
}

data "aws_iam_policy_document" "user_images_rw" {
  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:HeadObject",
    ]
    resources = ["${aws_s3_bucket.user_images.arn}/*"]
  }

  statement {
    actions   = ["s3:ListBucket", "s3:HeadBucket"]
    resources = [aws_s3_bucket.user_images.arn]
  }
}

data "aws_iam_policy_document" "dynamodb_tables_rw" {
  statement {
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:ConditionCheckItem",
      "dynamodb:DeleteItem",
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:UpdateItem",
    ]
    resources = [
      "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${local.prefix}-*",
      "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${local.prefix}-*/index/*",
    ]
  }
}

data "aws_iam_policy_document" "lambda_api_runtime" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.app.arn]
  }

  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.lambda_api.arn}:*"]
  }

  statement {
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_api" {
  name               = "${local.prefix}-lambda-api"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "lambda_api_dynamodb" {
  name   = "dynamodb-tables"
  role   = aws_iam_role.lambda_api.id
  policy = data.aws_iam_policy_document.dynamodb_tables_rw.json
}

resource "aws_iam_role_policy" "lambda_api_ses" {
  name   = "ses-send"
  role   = aws_iam_role.lambda_api.id
  policy = data.aws_iam_policy_document.ses_send.json
}

resource "aws_iam_role_policy" "lambda_api_s3" {
  name   = "s3-user-images"
  role   = aws_iam_role.lambda_api.id
  policy = data.aws_iam_policy_document.user_images_rw.json
}

resource "aws_iam_role_policy" "lambda_api_runtime" {
  name   = "runtime"
  role   = aws_iam_role.lambda_api.id
  policy = data.aws_iam_policy_document.lambda_api_runtime.json
}

resource "aws_cloudwatch_log_group" "lambda_api" {
  name              = "/aws/lambda/${local.prefix}-api"
  retention_in_days = 14
}

data "archive_file" "lambda_placeholder" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_placeholder"
  output_path = "${path.module}/.terraform/lambda_placeholder.zip"
}

locals {
  lambda_environment = { for key, value in {
    DEBUG                 = "false"
    APP_ENVIRONMENT       = var.environment
    PORT                  = "8000"
    USER_IMAGES_BUCKET    = aws_s3_bucket.user_images.bucket
    S3_ENDPOINT_URL       = ""
    EMAIL_FROM            = var.email_from
    EMAIL_ENABLED         = "true"
    SENTRY_RELEASE        = var.sentry_release
    SENTRY_SERVICE_NAME   = "lambda-api"
    AWS_EMF_ENVIRONMENT   = "Local"
    RUN_STARTUP_TASKS     = "false"
    DYNAMODB_TABLE_PREFIX = local.prefix
    APP_SECRETS_ARN       = aws_secretsmanager_secret.app.arn
    FRONTEND_URL          = local.frontend_url
    ALLOWED_ORIGINS       = local.custom_domain ? "" : "http://localhost,http://localhost:3000,http://localhost:4000,${local.frontend_url}"
  } : key => value if value != "" }
}

resource "aws_lambda_function" "api" {
  function_name = "${local.prefix}-api"
  role          = aws_iam_role.lambda_api.arn
  runtime       = "python3.13"
  architectures = ["x86_64"]
  handler       = "app.lambda_handler.handler"
  memory_size   = 1024
  timeout       = 29

  filename         = data.archive_file.lambda_placeholder.output_path
  source_code_hash = data.archive_file.lambda_placeholder.output_base64sha256

  environment {
    variables = local.lambda_environment
  }

  tracing_config {
    mode = "Active"
  }

  logging_config {
    log_format            = "JSON"
    application_log_level = "INFO"
    system_log_level      = "INFO"
  }

  lifecycle {
    ignore_changes = [filename, source_code_hash, s3_bucket, s3_key, s3_object_version]
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda_api,
    aws_iam_role_policy.lambda_api_runtime,
  ]

  tags = { Name = "${local.prefix}-api" }
}
