
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

  rate_limit_fail_open_alarm = true

  rate_limit_fail_open_log_groups = local.alarm_error_log_groups
}

moved {
  from = aws_cloudwatch_metric_alarm.telemetry_errors
  to   = module.alarms.aws_cloudwatch_metric_alarm.telemetry_errors[0]
}

moved {
  from = aws_cloudwatch_log_metric_filter.telemetry_errors
  to   = module.alarms.aws_cloudwatch_log_metric_filter.telemetry_errors
}
