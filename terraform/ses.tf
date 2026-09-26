module "ses" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/ses-identity"
  version = "~> 2.27"

  configuration_set_name = "carmodpicker-transactional"

  domain           = local.custom_domain ? local.domain_name : null
  sender_address   = local.custom_domain ? null : local.email_from
  mail_from_domain = local.custom_domain ? "bounce.${local.domain_name}" : null

  vdm_options_enabled           = true
  manage_account_vdm_attributes = true

  notification_topic_arn = aws_sns_topic.ses_notifications.arn

  verified_recipients = try(module.config.values.ses_verified_recipients, [])

  tags           = { Name = "${local.prefix}-transactional" }
  recipient_tags = { Name = "${local.prefix}-ses-recipient" }
}

moved {
  from = aws_sesv2_configuration_set.transactional
  to   = module.ses.aws_sesv2_configuration_set.this
}

moved {
  from = aws_sesv2_email_identity.domain[0]
  to   = module.ses.aws_sesv2_email_identity.domain[0]
}

moved {
  from = aws_sesv2_email_identity.sender[0]
  to   = module.ses.aws_sesv2_email_identity.sender[0]
}

moved {
  from = aws_sesv2_email_identity_mail_from_attributes.domain[0]
  to   = module.ses.aws_sesv2_email_identity_mail_from_attributes.domain[0]
}

moved {
  from = aws_sesv2_email_identity_feedback_attributes.domain[0]
  to   = module.ses.aws_sesv2_email_identity_feedback_attributes.domain[0]
}

moved {
  from = aws_sesv2_configuration_set_event_destination.sns
  to   = module.ses.aws_sesv2_configuration_set_event_destination.notifications[0]
}

moved {
  from = aws_sesv2_account_vdm_attributes.main
  to   = module.ses.aws_sesv2_account_vdm_attributes.this[0]
}

moved {
  from = aws_sesv2_email_identity.recipient
  to   = module.ses.aws_sesv2_email_identity.recipient
}

resource "aws_sns_topic" "ses_notifications" {
  name = "${local.prefix}-ses-notifications"
  tags = { Name = "${local.prefix}-ses-notifications" }
}

resource "aws_sns_topic_policy" "ses_notifications" {
  arn = aws_sns_topic.ses_notifications.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSESPublish"
      Effect    = "Allow"
      Principal = { Service = "ses.amazonaws.com" }
      Action    = "SNS:Publish"
      Resource  = aws_sns_topic.ses_notifications.arn
      Condition = {
        StringEquals = { "AWS:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "ses_email" {
  topic_arn = aws_sns_topic.ses_notifications.arn
  protocol  = "email"
  endpoint  = "tyler@webbpulse.com"
}
