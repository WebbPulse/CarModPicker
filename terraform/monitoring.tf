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
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "apprunner_application" {
  name              = "/aws/apprunner/${local.prefix}-backend/${aws_apprunner_service.backend.service_id}/application"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "apprunner_system" {
  name              = "/aws/apprunner/${local.prefix}-backend/${aws_apprunner_service.backend.service_id}/system"
  retention_in_days = 14
}

# RDS log group names are static (known at plan time).
resource "aws_cloudwatch_log_group" "rds_postgresql" {
  name              = "/aws/rds/instance/${local.prefix}-postgres/postgresql"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "rds_upgrade" {
  name              = "/aws/rds/instance/${local.prefix}-postgres/upgrade"
  retention_in_days = 14
}

# ---------------------------------------------------------------------------
# CloudWatch Alarms — 6 alarms (free tier: 10 standard-resolution alarms)
# ---------------------------------------------------------------------------

# App Runner: fire if healthy instances drop below 1 for 2 consecutive minutes.
# treat_missing_data = "breaching" so a complete metrics blackout is also an alarm.
resource "aws_cloudwatch_metric_alarm" "apprunner_healthy_instances" {
  alarm_name          = "${local.prefix}-apprunner-healthy-instances"
  alarm_description   = "App Runner has no healthy instances"
  namespace           = "AWS/AppRunner"
  metric_name         = "HealthyInstanceCount"
  dimensions          = { ServiceName = "${local.prefix}-backend" }
  statistic           = "Minimum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

# App Runner: more than 10 HTTP 5xx responses in a 5-minute window.
resource "aws_cloudwatch_metric_alarm" "apprunner_5xx" {
  alarm_name          = "${local.prefix}-apprunner-5xx"
  alarm_description   = "Elevated App Runner 5xx error rate"
  namespace           = "AWS/AppRunner"
  metric_name         = "Http5xxCount"
  dimensions          = { ServiceName = "${local.prefix}-backend" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}

# RDS: CPU above 80% for 15 consecutive minutes (3 × 5-min periods).
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
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

# RDS: free storage drops below 2 GB (reported in bytes by CloudWatch).
resource "aws_cloudwatch_metric_alarm" "rds_free_storage" {
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

# RDS: database connections above 15 for 10 minutes (db.t4g.micro soft cap ~40).
resource "aws_cloudwatch_metric_alarm" "rds_connections" {
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

# RDS: freeable memory below 50 MB (reported in bytes by CloudWatch).
resource "aws_cloudwatch_metric_alarm" "rds_freeable_memory" {
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
