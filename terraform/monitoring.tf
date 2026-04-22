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
# CloudWatch Alarms — 5 alarms (free tier: 10 standard-resolution alarms)
# ---------------------------------------------------------------------------

# App Runner: more than 10 HTTP 5xx responses in a 5-minute window.
# 5xxStatusResponses is the correct App Runner metric name (Http5xxCount does not exist).
resource "aws_cloudwatch_metric_alarm" "apprunner_5xx" {
  alarm_name        = "${local.prefix}-apprunner-5xx"
  alarm_description = "Elevated App Runner 5xx error rate"
  namespace         = "AWS/AppRunner"
  metric_name       = "5xxStatusResponses"
  dimensions = {
    ServiceName = "${local.prefix}-backend"
    ServiceID   = aws_apprunner_service.backend.service_id
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

# ---------------------------------------------------------------------------
# Crawler parse-failure composite alarm (Phase 2 / OBS-03)
#
# Aggregate-across-all-adapters alarm: fires when, in the last hour,
# ParseFailures / (Ingested + ParseFailures) > 0.5 on RunType=live metrics
# emitted into the CarModPicker/Crawlers namespace by plan 02-03's EMF helper.
#
# NaN-via-0 small-sample suppression (D-23): when combined samples < 10 the
# expression returns 0 — idle adapters stay quiet, matches runner.py total>=10
# drift threshold in plan 03's SAFE-07 characterization window.
#
# Landmines pinned:
#   7  — NO top-level `period` attribute (terraform-provider-aws#29398).
#        period lives ONLY inside each metric_query.metric {} block.
#   8  — NaN-via-0 (not NaN) so GreaterThanThreshold comparison is portable.
#   9  — datapoints_to_alarm (1) <= evaluation_periods (1).
#   10 — GreaterThanThreshold is strict > (NOT GreaterThanOrEqualToThreshold).
#
# SNS deviation (D-24): reuses aws_sns_topic.alarms (email-protocol subs to
# tyler@webbpulse.com + tylert2610@gmail.com). REQUIREMENTS OBS-03 says
# "SNS -> SES"; operator experience is identical. Captured in 02-HUMAN-UAT.md.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "crawler_parse_failure_composite" {
  alarm_name        = "${local.prefix}-crawler-parse-failure-composite"
  alarm_description = "Parse-failure rate >50% across all live-mode crawlers. Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"

  comparison_operator = "GreaterThanThreshold" # strict > (Landmine 10)
  evaluation_periods  = 1
  datapoints_to_alarm = 1 # 1 of 1 (Landmine 9)
  threshold           = 0.5
  treat_missing_data  = "notBreaching" # idle adapters stay quiet

  # NO top-level `period` — bug terraform-provider-aws#29398 / Landmine 7.
  # period lives only inside each metric_query.metric {} block below.

  metric_query {
    id = "ingested"
    metric {
      metric_name = "Ingested"
      namespace   = "CarModPicker/Crawlers"
      period      = 3600 # 1 hour — matches hourly crawl cadence
      stat        = "Sum"
      dimensions = {
        Environment = var.environment
        RunType     = "live" # exclude rescrape (D-21)
      }
    }
  }

  metric_query {
    id = "failures"
    metric {
      metric_name = "ParseFailures"
      namespace   = "CarModPicker/Crawlers"
      period      = 3600
      stat        = "Sum"
      dimensions = {
        Environment = var.environment
        RunType     = "live"
      }
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF((ingested + failures) < 10, 0, failures / (ingested + failures))"
    label       = "Parse failure rate (suppressed below 10 samples)"
    return_data = true # exactly one query has return_data=true
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  # TODO(phase-3): convert composite alarm to per-adapter via:
  #   for_each = toset(setsubtract(file("${path.module}/adapter_names.txt"), var.disabled_parse_alarms))
  # after CRAWL-01/02 adapter auto-discovery lands; add AdapterName dimension
  # to each metric_query.metric.dimensions map. Cost: 114 alarms x $0.10/mo = $11.40/mo.
}
