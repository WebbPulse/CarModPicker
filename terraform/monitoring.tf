# ---------------------------------------------------------------------------
# SNS Topic — shared alarm notification target
# Both email addresses must confirm their subscription after the first apply.
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alarms" {
  name = "${local.prefix}-alarms"
}

resource "aws_sns_topic_subscription" "alarms_tyler_webb" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = "tyler@webbpulse.com"
}

resource "aws_sns_topic_subscription" "alarms_tyler_gmail" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = "tylert2610@gmail.com"
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups — pre-created with 14-day retention so logs do not
# accumulate forever (the default is never-expire).
#
# App Runner automatically writes to these paths; no extra IAM config needed.
# The service_id is resolved from existing Terraform state.
#
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "apprunner_application" {
  count = local.legacy_stack ? 1 : 0

  name              = "/aws/apprunner/${local.prefix}-backend/${aws_apprunner_service.backend[0].service_id}/application"
  retention_in_days = 14
}

moved {
  from = aws_cloudwatch_log_group.apprunner_application
  to   = aws_cloudwatch_log_group.apprunner_application[0]
}

resource "aws_cloudwatch_log_group" "apprunner_system" {
  count = local.legacy_stack ? 1 : 0

  name              = "/aws/apprunner/${local.prefix}-backend/${aws_apprunner_service.backend[0].service_id}/system"
  retention_in_days = 14
}

moved {
  from = aws_cloudwatch_log_group.apprunner_system
  to   = aws_cloudwatch_log_group.apprunner_system[0]
}

# RDS log group names are static (known at plan time).
resource "aws_cloudwatch_log_group" "rds_postgresql" {
  count = local.legacy_stack ? 1 : 0

  name              = "/aws/rds/instance/${local.prefix}-postgres/postgresql"
  retention_in_days = 14
}

moved {
  from = aws_cloudwatch_log_group.rds_postgresql
  to   = aws_cloudwatch_log_group.rds_postgresql[0]
}

resource "aws_cloudwatch_log_group" "rds_upgrade" {
  count = local.legacy_stack ? 1 : 0

  name              = "/aws/rds/instance/${local.prefix}-postgres/upgrade"
  retention_in_days = 14
}

moved {
  from = aws_cloudwatch_log_group.rds_upgrade
  to   = aws_cloudwatch_log_group.rds_upgrade[0]
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms — legacy App Runner + RDS
# ---------------------------------------------------------------------------

# App Runner: more than 10 HTTP 5xx responses in a 5-minute window.
# 5xxStatusResponses is the correct App Runner metric name (Http5xxCount does not exist).
resource "aws_cloudwatch_metric_alarm" "apprunner_5xx" {
  count = local.legacy_stack ? 1 : 0

  alarm_name        = "${local.prefix}-apprunner-5xx"
  alarm_description = "Elevated App Runner 5xx error rate"
  namespace         = "AWS/AppRunner"
  metric_name       = "5xxStatusResponses"
  dimensions = {
    ServiceName = "${local.prefix}-backend"
    ServiceID   = aws_apprunner_service.backend[0].service_id
  }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

moved {
  from = aws_cloudwatch_metric_alarm.apprunner_5xx
  to   = aws_cloudwatch_metric_alarm.apprunner_5xx[0]
}

# RDS: CPU above 80% for 15 consecutive minutes (3 × 5-min periods).
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  count = local.legacy_stack ? 1 : 0

  alarm_name          = "${local.prefix}-rds-cpu"
  alarm_description   = "RDS CPU utilization above 80%"
  namespace           = "AWS/RDS"
  metric_name         = "CPUUtilization"
  dimensions          = { DBInstanceIdentifier = "${local.prefix}-postgres" }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

moved {
  from = aws_cloudwatch_metric_alarm.rds_cpu
  to   = aws_cloudwatch_metric_alarm.rds_cpu[0]
}

# RDS: free storage drops below 2 GB (reported in bytes by CloudWatch).
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
  count = local.legacy_stack ? 1 : 0

  alarm_name          = "${local.prefix}-rds-free-storage"
  alarm_description   = "RDS free storage below 2 GB"
  namespace           = "AWS/RDS"
  metric_name         = "FreeStorageSpace"
  dimensions          = { DBInstanceIdentifier = "${local.prefix}-postgres" }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 2147483648 # 2 GB in bytes
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

moved {
  from = aws_cloudwatch_metric_alarm.rds_free_storage
  to   = aws_cloudwatch_metric_alarm.rds_free_storage[0]
}

# RDS: database connections above 15 for 10 minutes (db.t4g.micro soft cap ~40).
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  count = local.legacy_stack ? 1 : 0

  alarm_name          = "${local.prefix}-rds-connections"
  alarm_description   = "RDS connection count elevated"
  namespace           = "AWS/RDS"
  metric_name         = "DatabaseConnections"
  dimensions          = { DBInstanceIdentifier = "${local.prefix}-postgres" }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 15
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

moved {
  from = aws_cloudwatch_metric_alarm.rds_connections
  to   = aws_cloudwatch_metric_alarm.rds_connections[0]
}

# RDS: freeable memory below 50 MB (reported in bytes by CloudWatch).
resource "aws_cloudwatch_metric_alarm" "rds_freeable_memory" {
  count = local.legacy_stack ? 1 : 0

  alarm_name          = "${local.prefix}-rds-freeable-memory"
  alarm_description   = "RDS freeable memory below 50 MB"
  namespace           = "AWS/RDS"
  metric_name         = "FreeableMemory"
  dimensions          = { DBInstanceIdentifier = "${local.prefix}-postgres" }
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 52428800 # 50 MB in bytes
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

moved {
  from = aws_cloudwatch_metric_alarm.rds_freeable_memory
  to   = aws_cloudwatch_metric_alarm.rds_freeable_memory[0]
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms — Lambda + HTTP API + DynamoDB
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${local.prefix}-lambda-errors"
  alarm_description   = "Lambda API reported invocation errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.api.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${local.prefix}-lambda-throttles"
  alarm_description   = "Lambda API invocations were throttled"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  dimensions          = { FunctionName = aws_lambda_function.api.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.prefix}-api-5xx"
  alarm_description   = "HTTP API returned 5xx responses"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.api.id }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_integration_latency_p99" {
  alarm_name          = "${local.prefix}-api-integration-latency-p99"
  alarm_description   = "HTTP API p99 integration latency above 10 s"
  namespace           = "AWS/ApiGateway"
  metric_name         = "IntegrationLatency"
  dimensions          = { ApiId = aws_apigatewayv2_api.api.id }
  extended_statistic  = "p99"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  for_each = aws_dynamodb_table.tables

  alarm_name          = "${each.value.name}-throttles"
  alarm_description   = "DynamoDB read or write throttle events on ${each.value.name}"
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]

  metric_query {
    id          = "throttles"
    expression  = "reads + writes"
    label       = "ThrottleEvents"
    return_data = true
  }

  metric_query {
    id = "reads"
    metric {
      namespace   = "AWS/DynamoDB"
      metric_name = "ReadThrottleEvents"
      dimensions  = { TableName = each.value.name }
      stat        = "Sum"
      period      = 300
    }
  }

  metric_query {
    id = "writes"
    metric {
      namespace   = "AWS/DynamoDB"
      metric_name = "WriteThrottleEvents"
      dimensions  = { TableName = each.value.name }
      stat        = "Sum"
      period      = 300
    }
  }
}
