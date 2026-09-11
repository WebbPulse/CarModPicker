
data "aws_iam_policy_document" "transaction_search_spans" {
  statement {
    sid    = "TransactionSearchAccess"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["xray.amazonaws.com"]
    }

    actions = ["logs:PutLogEvents"]

    resources = [
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:aws/spans:*",
      "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/application-signals/data:*",
    ]

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:xray:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_cloudwatch_log_resource_policy" "transaction_search_spans" {
  policy_name     = "${local.prefix}-transaction-search-spans"
  policy_document = data.aws_iam_policy_document.transaction_search_spans.json
}

resource "aws_xray_trace_segment_destination" "main" {
  destination = "CloudWatchLogs"

  depends_on = [aws_cloudwatch_log_resource_policy.transaction_search_spans]
}

locals {
  spans_log_groups = var.adopt_spans_log_group ? toset(["aws/spans"]) : toset([])
}

variable "adopt_spans_log_group" {
  description = "Adopt the reserved aws/spans log group into state and hold it at the platform's 7 day retention. X-Ray creates that group itself the first time it writes a span to the CloudWatchLogs destination, and it cannot be created ahead of time because CreateLogGroup rejects names beginning with aws/. An import block whose target does not exist is a plan time error, so a brand new account has to apply once with this false, generate one span, and then set it true. true is correct for every environment where a span has already been written, which is both of ours."
  type        = bool
  default     = true
}

moved {
  from = aws_cloudwatch_log_group.spans
  to   = aws_cloudwatch_log_group.spans["aws/spans"]
}

import {
  for_each = local.spans_log_groups

  to = aws_cloudwatch_log_group.spans[each.key]
  id = each.value
}

resource "aws_cloudwatch_log_group" "spans" {
  for_each = local.spans_log_groups

  name              = each.value
  retention_in_days = 7

  depends_on = [aws_xray_trace_segment_destination.main]
}

resource "aws_xray_indexing_rule" "default" {
  name = "Default"

  rule {
    probabilistic {
      desired_sampling_percentage = 1
    }
  }

  depends_on = [aws_xray_trace_segment_destination.main]
}
