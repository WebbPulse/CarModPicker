# ---------------------------------------------------------------------------
# AWS myApplications — Service Catalog AppRegistry
# Provides a unified console view of all application resources,
# cost breakdown, security findings, and operational data.
# ---------------------------------------------------------------------------
resource "aws_servicecatalogappregistry_application" "carmodpicker" {
  name        = local.prefix
  description = "CarModPicker web application"
}

# ---------------------------------------------------------------------------
# Resource Group — tag-based auto-discovery
# Surfaces all Project=carmodpicker resources in the console and feeds
# the myApplications view.
# ---------------------------------------------------------------------------
resource "aws_resourcegroups_group" "carmodpicker" {
  name        = local.prefix
  description = "All CarModPicker managed resources"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [
        {
          Key    = "Project"
          Values = ["carmodpicker"]
        }
      ]
    })
  }
}

# ---------------------------------------------------------------------------
# Cost Anomaly Detection — alerts on unexpected spend spikes (free)
# Monitors per AWS service; daily digest when any anomaly >= $10.
# ---------------------------------------------------------------------------
resource "aws_ce_anomaly_monitor" "carmodpicker" {
  name              = local.prefix
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
}

resource "aws_ce_anomaly_subscription" "carmodpicker" {
  name      = local.prefix
  frequency = "DAILY"

  monitor_arn_list = [aws_ce_anomaly_monitor.carmodpicker.arn]

  subscriber {
    type    = "EMAIL"
    address = "tyler@webbpulse.com"
  }

  subscriber {
    type    = "EMAIL"
    address = "tylert2610@gmail.com"
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      match_options = ["GREATER_THAN_OR_EQUAL"]
      values        = ["10"]
    }
  }
}

# ---------------------------------------------------------------------------
# Budget alerts — first 2 budgets per account are free
# ---------------------------------------------------------------------------
resource "aws_budgets_budget" "warn" {
  name         = "${local.prefix}-monthly-warn"
  budget_type  = "COST"
  limit_amount = "30"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["tyler@webbpulse.com", "tylert2610@gmail.com"]
  }
}

resource "aws_budgets_budget" "critical" {
  name         = "${local.prefix}-monthly-critical"
  budget_type  = "COST"
  limit_amount = "60"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = ["tyler@webbpulse.com", "tylert2610@gmail.com"]
  }
}
