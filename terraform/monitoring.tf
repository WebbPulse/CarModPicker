
locals {
  alarm_lambda_function_names = concat(
    [
      for name in local.lambda_domain_names : module.lambda_domain[name].function_name
      if contains(keys(local.lambda_domains), name)
    ],
    [
      for name in sort(keys(local.lambda_stream_consumers)) :
      module.lambda_stream_consumer[name].function_name
    ],
  )

  alarm_error_log_groups = merge(
    { for name in keys(local.lambda_domains) : name => module.lambda_domain[name].log_group_name },
    {
      for name in keys(local.lambda_stream_consumers) :
      "consumer-${name}" => module.lambda_stream_consumer[name].log_group_name
    },
  )

  telemetry_error_loggers = ["opentelemetry.*", "webbpulse.otel"]

  application_error_filter_pattern = format(
    "{ $.level = \"ERROR\" && %s }",
    join(" && ", [for l in local.telemetry_error_loggers : "$.logger != \"${l}\""]),
  )

  telemetry_error_filter_pattern = format(
    "{ $.level = \"ERROR\" && (%s) }",
    join(" || ", [for l in local.telemetry_error_loggers : "$.logger = \"${l}\""]),
  )
}

module "alarms" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/api-alarms"
  version = "~> 2.14"

  name_prefix         = local.prefix
  notification_emails = ["tyler@webbpulse.com", "tylert2610@gmail.com"]

  http_api_id = module.api.api_id

  lambda_function_names      = local.alarm_lambda_function_names
  lambda_aggregate_alarm     = length(local.alarm_lambda_function_names) > 0
  lambda_aggregate_threshold = 0

  dynamodb_aggregate_alarm = true
  dynamodb_tables          = {}

  error_log_groups = local.alarm_error_log_groups

  error_filter_pattern = local.application_error_filter_pattern

  rate_limit_fail_open_alarm = true

  rate_limit_fail_open_log_groups = local.alarm_error_log_groups
}

resource "aws_cloudwatch_log_metric_filter" "telemetry_errors" {
  for_each = local.alarm_error_log_groups

  name           = "${local.prefix}-${each.key}-telemetry-errors"
  log_group_name = each.value
  pattern        = local.telemetry_error_filter_pattern

  metric_transformation {
    name          = "${local.prefix}-telemetry-export-errors"
    namespace     = "WebbPulse/Application"
    value         = "1"
    default_value = "0"
    unit          = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "telemetry_errors" {
  alarm_name        = "${local.prefix}-telemetry-export-errors"
  alarm_description = "Span export to the X-Ray OTLP endpoint is failing across ${length(local.alarm_error_log_groups)} log groups. Traces are being lost; requests are unaffected. An isolated failure is the shutdown flush losing a race with sandbox teardown and is expected."

  namespace           = "WebbPulse/Application"
  metric_name         = "${local.prefix}-telemetry-export-errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [module.alarms.sns_topic_arn]
  ok_actions    = [module.alarms.sns_topic_arn]

  tags = { Name = "${local.prefix}-telemetry-export-errors" }

  depends_on = [aws_cloudwatch_log_metric_filter.telemetry_errors]
}
