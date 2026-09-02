# ---------------------------------------------------------------------------
# Resource Group — tag-based auto-discovery
# Surfaces all Project=carmodpicker resources in the console.
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

# ---------------------------------------------------------------------------
# Resource Groups tag-sync role — extra permissions
#
# AWS auto-creates a `tag-sync-role-<region>-<suffix>` role (one per account +
# region) the first time tag-sync is enabled on a Resource Group. The role
# propagates the AppRegistry `awsApplication` tag to resources that match the
# Resource Group query, so they show up under myApplications.
#
# AWS attaches the managed policy
# `ResourceGroupsTaggingAPITagUntagSupportedResources`, but that policy is
# missing `apprunner:*` and `servicecatalog:*` tag actions, so tag-sync is
# denied when trying to tag our App Runner service + autoscaling config, and
# the AppRegistry application + attribute group. CloudTrail shows recurring
# `AccessDenied` TagResource events from `TagSyncTaskProcessor`.
#
# Fix: attach an inline policy granting the missing permissions. The role also
# services a sibling project (webbpulse-production), so the policy name is
# project-scoped to avoid collisions if the same fix is applied there.
#
# The role name has an AWS-generated suffix; if tag-sync is ever disabled and
# re-enabled the suffix will change and this data lookup will fail loudly,
# which is the desired behavior.
# ---------------------------------------------------------------------------
data "aws_iam_role" "tag_sync" {
  name = "tag-sync-role-${var.aws_region}-k73y7vmb"
}

resource "aws_iam_role_policy" "tag_sync_apprunner_servicecatalog" {
  name = "${local.prefix}-tag-sync-extras"
  role = data.aws_iam_role.tag_sync.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "apprunner:TagResource",
          "apprunner:UntagResource",
          "servicecatalog:TagResource",
          "servicecatalog:UntagResource",
        ]
        Resource = "*"
      },
    ]
  })
}
