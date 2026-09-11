
locals {
  lambda_domains_declared = {
    media = {
      secrets        = true
      s3             = true
      s3_delete_only = false
      ses            = false
      memory         = 512
      tables         = ["image_source_mappings", "rate-limits"]
      read_tables    = ["users", "car_generations", "parts", "build_lists"]
    }
    build-logs = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      tables         = ["build_log_posts", "rate-limits"]
      read_tables    = ["users", "build_lists", "build_logs"]
    }
    moderation = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      tables         = ["votes", "reports", "bug_reports", "rate-limits"]
      read_tables    = ["users", "build_lists", "car_generations", "parts"]
    }
    vehicles = {
      secrets        = false
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      tables         = ["rate-limits"]
      read_tables = [
        "car_generations",
        "car_models",
        "car_makes",
        "build_lists",
        "users",
        "parts",
        "part_manufacturers",
      ]
    }
    admin = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = false
      memory         = 256
      tables = [
        "part_price_alerts",
        "car_makes",
        "car_models",
        "car_generations",
        "categories",
        "part_manufacturers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_lists",
        "votes",
        "reports",
        "rate-limits",
      ]
      read_tables = [
        "users",
        "oauth_accounts",
        "webauthn_credentials",
        "build_list_phases",
        "build_logs",
        "image_source_mappings",
      ]
    }
    build-lists = {
      secrets        = true
      s3             = true
      s3_delete_only = true
      ses            = false
      memory         = 1024
      tables = [
        "build_lists",
        "build_list_parts",
        "build_list_phases",
        "build_list_labor_estimates",
        "build_logs",
        "build_log_posts",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "part_price_alerts",
        "rate-limits",
      ]
      read_tables = [
        "users",
        "app_settings",
        "car_generations",
        "categories",
        "part_manufacturers",
        "retailers",
        "votes",
      ]
    }
    identity = {
      secrets        = true
      s3             = false
      s3_delete_only = false
      ses            = true
      memory         = 512
      tables         = ["users", "oauth_accounts", "webauthn_credentials", "rate-limits"]
      read_tables    = []
    }
    catalog = {
      secrets        = true
      s3             = true
      s3_delete_only = true
      ses            = false
      memory         = 1024
      tables = [
        "parts",
        "part_manufacturers",
        "retailers",
        "categories",
        "part_cars",
        "part_listings",
        "part_price_history",
        "rate-limits",
      ]
      read_tables = [
        "users",
        "votes",
        "car_makes",
        "car_models",
        "car_generations",
      ]
    }
    users = {
      secrets        = true
      s3             = true
      s3_delete_only = false
      ses            = false
      memory         = 512
      tables         = ["users", "app_settings", "rate-limits"]
      read_tables    = ["oauth_accounts"]
    }
  }

  domain_functions_enabled = var.bootstrap_image_tag != ""

  lambda_domains = local.domain_functions_enabled ? local.lambda_domains_declared : {}

  dynamodb_domain_write_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:BatchWriteItem",
    "dynamodb:ConditionCheckItem",
    "dynamodb:DeleteItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:TransactGetItems",
    "dynamodb:TransactWriteItems",
    "dynamodb:UpdateItem",
  ]

  dynamodb_domain_read_actions = [
    "dynamodb:BatchGetItem",
    "dynamodb:DescribeTable",
    "dynamodb:GetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
  ]

  lambda_domain_write_arns = {
    for name, domain in local.lambda_domains : name => flatten([
      for table in domain.tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_domain_read_arns = {
    for name, domain in local.lambda_domains : name => flatten([
      for table in domain.read_tables : [
        module.dynamodb.table_arns[table],
        "${module.dynamodb.table_arns[table]}/index/*",
      ]
    ])
  }

  lambda_domain_environment = {
    for name, domain in local.lambda_domains : name => merge(
      {
        DEBUG                 = "false"
        APP_ENVIRONMENT       = var.environment
        DYNAMODB_TABLE_PREFIX = local.prefix

        RATE_LIMITS_TABLE = module.dynamodb.table_names["rate-limits"]

        FRONTEND_URL    = local.frontend_url
        ALLOWED_ORIGINS = local.allowed_origins

        WEBBPULSE_OTEL_SAMPLE_RATIO        = var.environment == "production" ? "0.1" : "1.0"
        OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "https://xray.${var.aws_region}.amazonaws.com/v1/traces"
      },
      domain.secrets ? { APP_SECRETS_ARN = module.app_secrets.arns["app"] } : {},
      domain.ses ? {
        EMAIL_FROM    = local.email_from
        EMAIL_ENABLED = "true"
      } : {},
      domain.s3 ? {
        USER_IMAGES_BUCKET = aws_s3_bucket.user_images.bucket
      } : {},

      name == "identity" ? merge({
        IDENTITY_ENVIRONMENT       = var.environment
        IDENTITY_PRODUCT_NAME      = "CarModPicker"
        IDENTITY_RP_NAME           = "CarModPicker"
        IDENTITY_SUPPORT_EMAIL     = "support@${local.active_domain}"
        IDENTITY_FRONTEND_BASE_URL = local.frontend_url

        IDENTITY_EMAIL_FROM            = local.email_from
        IDENTITY_SES_CONFIGURATION_SET = aws_sesv2_configuration_set.transactional.configuration_set_name

        IDENTITY_REGISTRATION_ENABLED = "true"

        IDENTITY_PASSKEYS_ENABLED      = tostring(var.passkeys_enabled)
        IDENTITY_PASSKEYS_PASSWORDLESS = tostring(var.passkeys_passwordless)

        IDENTITY_WEBAUTHN_ORIGINS = local.identity_webauthn_origins

        IDENTITY_OAUTH_REDIRECT_URIS = local.identity_oauth_redirect_uris
        IDENTITY_GOOGLE_CLIENT_ID    = var.oauth_google_client_id
        IDENTITY_GITHUB_CLIENT_ID    = var.oauth_github_client_id
        },

      module.identity.identity_environment) : {},
    )
  }
}

variable "bootstrap_image_tag" {
  description = "Image tag used as the seed for every per-domain function, as pushed to ECR by the container image build in deploy-backend.yml. Lambda pulls and optimises the image when it creates the function, so a tag that does not resolve fails the create: the tag named here must already exist in the repository of every domain in local.lambda_domains_declared before the apply. It is only ever a seed, because image_uri is on the lambda-function module's ignore_changes list, so the deploy step's UpdateFunctionCode is not undone by the next plan and this value never needs changing again. The empty string is the bootstrap value for a fresh account that has no images yet: it resolves local.lambda_domains and local.routed_lambda_domains to empty, so the apply builds the repositories and everything else and creates no domain function and cuts no route. See the Promoting to a fresh account section of docs/migration/split-plan.md."
  type        = string
  default     = ""

  validation {
    condition     = var.bootstrap_image_tag == "" || can(regex("^sha-[0-9a-f]{40}$", var.bootstrap_image_tag))
    error_message = "bootstrap_image_tag must be sha- followed by a full 40 character commit sha, which is the tag the container image build pushes, or the empty string to bootstrap an account whose ECR repositories hold no images yet."
  }
}

module "lambda_domain" {
  for_each = local.lambda_domains

  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/lambda-function"
  version = "~> 2.1"

  function_name = "${local.prefix}-${each.key}"
  role_name     = "${local.prefix}-lambda-${each.key}"

  package_type = "Image"

  architectures = ["arm64"]
  memory_size   = each.value.memory

  timeout = 29

  code = {
    image_uri = "${module.registry.repository_urls[each.key]}:${var.bootstrap_image_tag}"
  }

  environment_variables = local.lambda_domain_environment[each.key]

  log_retention_days           = 7
  log_format                   = "JSON"
  application_log_level        = "INFO"
  system_log_level             = "INFO"
  set_logging_config_log_group = true

  tracing_mode             = "Active"
  attach_xray_write_policy = true

  tags = { Name = "${local.prefix}-${each.key}" }
}

resource "aws_iam_role_policy" "lambda_domain" {
  for_each = local.lambda_domains

  name = "${each.key}-runtime"
  role = module.lambda_domain[each.key].role_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid      = "WriteOwnLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${module.lambda_domain[each.key].log_group_arn}:*"
        },
        {
          Sid      = "WriteSpansToTheXRayOTLPEndpoint"
          Effect   = "Allow"
          Action   = ["xray:PutSpans", "xray:PutSpansForIndexing"]
          Resource = "*"
        },
      ],
      length(local.lambda_domain_write_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadWriteOwnTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_write_actions
          Resource = local.lambda_domain_write_arns[each.key]
        },
      ] : [],
      length(local.lambda_domain_read_arns[each.key]) > 0 ? [
        {
          Sid      = "ReadSharedTables"
          Effect   = "Allow"
          Action   = local.dynamodb_domain_read_actions
          Resource = local.lambda_domain_read_arns[each.key]
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
      each.value.s3 ? [
        {
          Sid    = each.value.s3_delete_only ? "DeleteUserImageObjects" : "ReadWriteUserImageObjects"
          Effect = "Allow"
          Action = each.value.s3_delete_only ? [
            "s3:DeleteObject",
            ] : [
            "s3:PutObject",
            "s3:GetObject",
            "s3:DeleteObject",
          ]
          Resource = ["${aws_s3_bucket.user_images.arn}/*"]
        },
        {
          Sid      = "ListTheUserImagesBucket"
          Effect   = "Allow"
          Action   = ["s3:ListBucket"]
          Resource = [aws_s3_bucket.user_images.arn]
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
