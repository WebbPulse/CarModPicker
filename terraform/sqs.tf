
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
