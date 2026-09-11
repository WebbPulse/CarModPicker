
locals {
  stream_consumer_dlqs = keys(local.dynamodb_stream_view_types)

  work_queue_consumer_timeout = 29

  work_queues = {
    part-purge = {
      description = "Seam 2, split plan row 28. Fan out of deletes after a part is tombstoned, drained by build-lists, moderation and admin."
    }
    user-delete = {
      description = "Seam 1, split plan row 30. Fan out of deletes after a user is tombstoned, drained by every domain that owns a table the cascade touches."
    }
  }
}

resource "aws_sqs_queue" "stream_dlq" {
  for_each = toset(local.stream_consumer_dlqs)

  name = "${local.prefix}-${replace(each.key, "_", "-")}-stream-dlq"

  sqs_managed_sse_enabled = true

  message_retention_seconds = 1209600

  tags = { Name = "${local.prefix}-${replace(each.key, "_", "-")}-stream-dlq" }
}

resource "aws_sqs_queue" "work_dlq" {
  for_each = local.work_queues

  name                    = "${local.prefix}-${each.key}-dlq"
  sqs_managed_sse_enabled = true

  message_retention_seconds = 1209600

  tags = { Name = "${local.prefix}-${each.key}-dlq" }
}

resource "aws_sqs_queue" "work" {
  for_each = local.work_queues

  name                    = "${local.prefix}-${each.key}"
  sqs_managed_sse_enabled = true

  message_retention_seconds = 345600

  visibility_timeout_seconds = local.work_queue_consumer_timeout * 6

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.work_dlq[each.key].arn

    maxReceiveCount = 5
  })

  tags = { Name = "${local.prefix}-${each.key}" }
}

locals {
  dlq_alarm_queues = concat(
    [for key in sort(local.stream_consumer_dlqs) : aws_sqs_queue.stream_dlq[key].name],
    [for key in sort(keys(local.work_queues)) : aws_sqs_queue.work_dlq[key].name],
  )
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name        = "${local.prefix}-dlq-depth"
  alarm_description = "Messages waiting in any of the ${length(local.dlq_alarm_queues)} dead letter queues: ${join(", ", local.dlq_alarm_queues)}. A non empty dead letter queue means a stream consumer or a cleanup handler gave up on work it was given, so a delete or a price alert has been dropped rather than applied."

  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  evaluation_periods = 1

  treat_missing_data = "notBreaching"

  alarm_actions = [module.alarms.sns_topic_arn]
  ok_actions    = [module.alarms.sns_topic_arn]

  metric_query {
    id          = "depth"
    expression  = join(" + ", [for i, _ in local.dlq_alarm_queues : "m${i}"])
    label       = "Dead letter queue depth"
    return_data = true
  }

  dynamic "metric_query" {
    for_each = { for i, name in local.dlq_alarm_queues : "m${i}" => name }

    content {
      id          = metric_query.key
      label       = metric_query.value
      return_data = false

      metric {
        namespace   = "AWS/SQS"
        metric_name = "ApproximateNumberOfMessagesVisible"
        dimensions  = { QueueName = metric_query.value }
        period      = 300
        stat        = "Maximum"
      }
    }
  }

  tags = { Name = "${local.prefix}-dlq-depth" }
}
