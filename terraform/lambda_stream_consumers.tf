
locals {
  lambda_stream_consumers_declared = {
    catalog-votes-consumer = {
      image_repository = "catalog"
      stream_table     = "votes"
      command          = ["python", "-m", "app.entrypoints.catalog_votes_consumer"]

      work_queue = null

      memory = 256

      timeout = 60

      secrets = false

      tables      = ["parts"]
      read_tables = ["votes"]

      ses = false
    }

    admin-price-alerts-consumer = {
      image_repository = "admin"
      stream_table     = "part_listings"
      command          = ["python", "-m", "app.entrypoints.admin_price_alerts_consumer"]

      work_queue = null

      memory = 256

      timeout = 60

      secrets = true

      ses = true

      tables      = ["part_price_alerts"]
      read_tables = ["parts", "retailers", "users"]
    }

    catalog-part-purge-consumer = {
      image_repository = "catalog"
      stream_table     = "parts"
      work_queue       = "part-purge"
      command          = ["python", "-m", "app.entrypoints.catalog_part_purge_consumer"]

      memory = 256

      timeout = 29

      secrets = false
      ses     = false

      tables      = ["build_list_parts", "votes", "reports", "part_price_alerts"]
      read_tables = []
    }

    users-delete-consumer = {
      image_repository = "users"
      stream_table     = "users"
      work_queue       = "user-delete"
      command          = ["python", "-m", "app.entrypoints.users_delete_consumer"]

      memory = 256

      timeout = 29

      secrets = false
      ses     = false

      tables = [
        "oauth_accounts",
        "webauthn_credentials",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "part_price_alerts",
        "build_lists",
        "build_list_parts",
        "build_list_phases",
        "build_list_labor_estimates",
        "build_logs",
        "build_log_posts",
        "votes",
        "reports",
      ]
      read_tables = []
    }
  }

  lambda_stream_consumers = local.domain_functions_enabled ? local.lambda_stream_consumers_declared : {}

  lambda_stream_consumer_write_arns = {
    for name, consumer in local.lambda_stream_consumers : name => flatten([
      for table in consumer.tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_stream_consumer_read_arns = {
    for name, consumer in local.lambda_stream_consumers : name => flatten([
      for table in consumer.read_tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_stream_consumer_environment = {
    for name, consumer in local.lambda_stream_consumers : name => merge({
      DEBUG                 = "false"
      APP_ENVIRONMENT       = var.environment
      DYNAMODB_TABLE_PREFIX = local.prefix

      WEBBPULSE_OTEL_SAMPLE_RATIO        = var.environment == "production" ? "0.1" : "1.0"
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com/v1/traces"

      AWS_LWA_PASS_THROUGH_PATH = "/events"

      AWS_LWA_ERROR_STATUS_CODES = "500-599"
      },
      consumer.work_queue != null ? {
        "${upper(replace(consumer.work_queue, "-", "_"))}_QUEUE_URL" = aws_sqs_queue.work[consumer.work_queue].id
      } : {},
      consumer.ses ? {
        EMAIL_FROM    = local.email_from
        EMAIL_ENABLED = "true"

        FRONTEND_URL = local.frontend_url

        APP_SECRETS_ARN = module.app_secrets.arns["app"]
    } : {})
  }
}

module "lambda_stream_consumer" {
  for_each = local.lambda_stream_consumers

  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-function"
  version = "~> 2.1"

  function_name = "${local.prefix}-${each.key}"
  role_name     = "${local.prefix}-lambda-${each.key}"

  package_type = "Image"

  image_config = {
    command = each.value.command
  }

  architectures = ["arm64"]
  memory_size   = each.value.memory
  timeout       = each.value.timeout

  code = {
    image_uri = "${module.registry.repository_urls[each.value.image_repository]}:${var.bootstrap_image_tag}"
  }

  environment_variables = local.lambda_stream_consumer_environment[each.key]

  log_retention_days           = 7
  log_format                   = "JSON"
  application_log_level        = "INFO"
  system_log_level             = "INFO"
  set_logging_config_log_group = true

  tracing_mode             = "Active"
  attach_xray_write_policy = true

  tags = { Name = "${local.prefix}-${each.key}" }
}

resource "aws_iam_role_policy" "lambda_stream_consumer" {
  for_each = local.lambda_stream_consumers

  name = "${each.key}-runtime"
  role = module.lambda_stream_consumer[each.key].role_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid      = "WriteOwnLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${module.lambda_stream_consumer[each.key].log_group_arn}:*"
        },
        {
          Sid      = "WriteSpansToTheXRayOTLPEndpoint"
          Effect   = "Allow"
          Action   = ["xray:PutSpans", "xray:PutSpansForIndexing"]
          Resource = "*"
        },
        {
          Sid    = "ReadTheTableStream"
          Effect = "Allow"
          Action = [
            "dynamodb:DescribeStream",
            "dynamodb:GetRecords",
            "dynamodb:GetShardIterator",
          ]
          Resource = [module.dynamodb.stream_arns[each.value.stream_table]]
        },
        {
          Sid      = "ListStreams"
          Effect   = "Allow"
          Action   = ["dynamodb:ListStreams"]
          Resource = "*"
        },
        {
          Sid      = "WriteFailedBatchesToTheDeadLetterQueue"
          Effect   = "Allow"
          Action   = ["sqs:SendMessage"]
          Resource = [aws_sqs_queue.stream_dlq[each.value.stream_table].arn]
        },
      ],
      each.value.work_queue != null ? [
        {
          Sid    = "DrainAndFeedTheWorkQueue"
          Effect = "Allow"
          Action = [
            "sqs:SendMessage",
            "sqs:ReceiveMessage",
            "sqs:DeleteMessage",
            "sqs:GetQueueAttributes",
          ]
          Resource = [aws_sqs_queue.work[each.value.work_queue].arn]
        },
      ] : [],
      length(local.lambda_stream_consumer_write_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadWriteOwnTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_write_actions
          Resource = local.lambda_stream_consumer_write_arns[each.key]
        },
      ] : [],
      length(local.lambda_stream_consumer_read_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadSharedTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_read_actions
          Resource = local.lambda_stream_consumer_read_arns[each.key]
        },
      ] : [],
      each.value.secrets ? [
        {
          Sid      = "ReadTheAppSecret"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = [module.app_secrets.arns["app"]]
        },
      ] : [],
      each.value.ses ? [
        {
          Sid    = "SendTransactionalMail"
          Effect = "Allow"
          Action = ["ses:SendEmail"]
          Resource = [
            "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:identity/*",
            "arn:aws:ses:${var.aws_region}:${data.aws_caller_identity.current.account_id}:configuration-set/${aws_sesv2_configuration_set.transactional.configuration_set_name}",
          ]
        },
      ] : [],
    )
  })
}

resource "aws_lambda_event_source_mapping" "stream_consumer" {
  for_each = local.lambda_stream_consumers

  event_source_arn  = module.dynamodb.stream_arns[each.value.stream_table]
  function_name     = module.lambda_stream_consumer[each.key].function_arn
  starting_position = "LATEST"

  batch_size = 100

  maximum_batching_window_in_seconds = 5

  bisect_batch_on_function_error = true

  maximum_retry_attempts = 2

  maximum_record_age_in_seconds = 3600

  function_response_types = ["ReportBatchItemFailures"]

  destination_config {
    on_failure {
      destination_arn = aws_sqs_queue.stream_dlq[each.value.stream_table].arn
    }
  }

  depends_on = [aws_iam_role_policy.lambda_stream_consumer]
}

resource "aws_lambda_event_source_mapping" "work_queue_consumer" {
  for_each = {
    for name, consumer in local.lambda_stream_consumers : name => consumer
    if consumer.work_queue != null
  }

  event_source_arn = aws_sqs_queue.work[each.value.work_queue].arn
  function_name    = module.lambda_stream_consumer[each.key].function_arn

  batch_size = 10

  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 2
  }

  depends_on = [aws_iam_role_policy.lambda_stream_consumer]
}
