
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

module "work_queue" {
  for_each = local.work_queues

  source  = "terraform.webbpulse.com/WebbPulse/platform-modules/aws//modules/sqs-queue"
  version = "~> 2.39"

  name = "${local.prefix}-${each.key}"

  visibility_timeout_seconds = local.work_queue_consumer_timeout * 6
  consumer_timeout_seconds   = local.work_queue_consumer_timeout
}

moved {
  from = aws_sqs_queue.work["part-purge"]
  to   = module.work_queue["part-purge"].aws_sqs_queue.this
}

moved {
  from = aws_sqs_queue.work_dlq["part-purge"]
  to   = module.work_queue["part-purge"].aws_sqs_queue.dead_letter
}

moved {
  from = aws_sqs_queue.work["user-delete"]
  to   = module.work_queue["user-delete"].aws_sqs_queue.this
}

moved {
  from = aws_sqs_queue.work_dlq["user-delete"]
  to   = module.work_queue["user-delete"].aws_sqs_queue.dead_letter
}
