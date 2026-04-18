# ---------------------------------------------------------------------------
# EventBridge Scheduler — Cron-triggered admin jobs
#
# Flow: EventBridge Schedule → default Event Bus → EventBridge Rule
#       → API Destination → App Runner admin API
#
# EventBridge Scheduler does not accept api-destination ARNs as a direct
# target. The standard pattern is to route through an event bus:
#   Scheduler puts a structured event on the default bus, an EventBridge rule
#   matches on source/detail-type, and the rule target invokes the API
#   destination (which carries the X-Admin-Cron-Key auth header via the
#   EventBridge Connection).
#
# Auth: EventBridge Connection stores X-Admin-Cron-Key header value from
#       var.cron_secret_key. The same value is set as CRON_SECRET_KEY in
#       App Runner (via Secrets Manager, see secretsmanager.tf).
#
# Archive rescrapes are never triggered automatically — admins run them
# manually from the admin UI.
#
# Per-adapter schedules are managed dynamically by the backend via boto3,
# sourced from the adapter_schedules DB table. Terraform provisions only the
# target plumbing below (connection, API destination, event bus rule, IAM);
# the individual aws_scheduler_schedule resources are created/updated/deleted
# by the backend reconciler. All per-adapter schedules share the default
# scheduler group and share this Target plumbing.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# EventBridge Connection — auth header sent with every invocation
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_connection" "cron" {
  name               = "${local.prefix}-cron"
  description        = "API-key auth for EventBridge Scheduler → App Runner admin endpoints"
  authorization_type = "API_KEY"

  auth_parameters {
    api_key {
      key   = "X-Admin-Cron-Key"
      value = var.cron_secret_key
    }
  }
}


# ---------------------------------------------------------------------------
# API Destination — crawler run
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_api_destination" "crawler_run" {
  name        = "${local.prefix}-crawler-run"
  description = "POST /api/admin/crawlers/run"

  connection_arn                   = aws_cloudwatch_event_connection.cron.arn
  invocation_endpoint              = "https://${aws_apprunner_service.backend.service_url}/api/admin/crawlers/run"
  http_method                      = "POST"
  invocation_rate_limit_per_second = 1
}


# ---------------------------------------------------------------------------
# IAM role — EventBridge Scheduler → Event Bus
# ---------------------------------------------------------------------------
resource "aws_iam_role" "eventbridge_scheduler" {
  name        = "${local.prefix}-eventbridge-scheduler"
  description = "Allows EventBridge Scheduler to put events on the default event bus"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.prefix}-eventbridge-scheduler" }
}

resource "aws_iam_role_policy" "eventbridge_scheduler_put_events" {
  name = "put-events-default-bus"
  role = aws_iam_role.eventbridge_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["events:PutEvents"]
      Resource = ["arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:event-bus/default"]
    }]
  })
}


# ---------------------------------------------------------------------------
# IAM role — EventBridge rule → API destination invocation
# ---------------------------------------------------------------------------
resource "aws_iam_role" "eventbridge_invoke" {
  name        = "${local.prefix}-eventbridge-invoke"
  description = "Allows EventBridge rules to invoke App Runner via API destinations"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.prefix}-eventbridge-invoke" }
}

resource "aws_iam_role_policy" "eventbridge_invoke_api_destination" {
  name = "invoke-api-destinations"
  role = aws_iam_role.eventbridge_invoke.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["events:InvokeApiDestination"]
      Resource = [aws_cloudwatch_event_api_destination.crawler_run.arn]
    }]
  })
}


# ---------------------------------------------------------------------------
# EventBridge rule — matches scheduler events and routes to API destination
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "crawler_run" {
  name        = "${local.prefix}-crawler-run"
  description = "Routes scheduled crawler-run events to the API destination"

  event_pattern = jsonencode({
    source      = ["carmodpicker.scheduler"]
    detail-type = ["crawler-run"]
  })
}

resource "aws_cloudwatch_event_target" "crawler_run" {
  rule      = aws_cloudwatch_event_rule.crawler_run.name
  target_id = "crawler-run-api-destination"
  arn       = aws_cloudwatch_event_api_destination.crawler_run.arn
  role_arn  = aws_iam_role.eventbridge_invoke.arn

  # Extract only $.detail (the payload from the scheduler) as the HTTP body,
  # discarding the EventBridge envelope so the backend receives the same JSON
  # it would receive from a direct invocation.
  input_transformer {
    input_paths    = { detail = "$.detail" }
    input_template = "<detail>"
  }
}


# ---------------------------------------------------------------------------
# Per-adapter schedules are managed by the backend reconciler, not Terraform.
# See app/api/services/adapter_schedule_service.py — each row in the
# adapter_schedules DB table produces one aws_scheduler_schedule named
# "${local.prefix}-crawler-<adapter_name>" in the default scheduler group,
# with Target pointing at the default event bus (above). No schedule resources
# are declared here.
# ---------------------------------------------------------------------------
