# ---------------------------------------------------------------------------
# SES Configuration Set
# A properly-named config set for all transactional mail.
# The console-created "my-first-configuration-set" is left unmanaged and can
# be deleted from the AWS console after Terraform associates the domain with
# this one.
# ---------------------------------------------------------------------------
resource "aws_sesv2_configuration_set" "transactional" {
  configuration_set_name = "carmodpicker-transactional"

  reputation_options {
    reputation_metrics_enabled = true
  }

  sending_options {
    sending_enabled = true
  }

  vdm_options {
    dashboard_options {
      engagement_metrics = "ENABLED"
    }
    guardian_options {
      optimized_shared_delivery = "ENABLED"
    }
  }

  tags = { Name = "${local.prefix}-transactional" }
}

# ---------------------------------------------------------------------------
# SES Domain Identity
# carmodpicker.com is already verified in AWS. The three Easy DKIM CNAME
# records are already managed in route53.tf. Importing this resource into
# Terraform state lets us keep the identity in sync and associate it with
# the config set above.
# Import: terraform import aws_sesv2_email_identity.domain carmodpicker.com
# ---------------------------------------------------------------------------
resource "aws_sesv2_email_identity" "domain" {
  email_identity         = "carmodpicker.com"
  configuration_set_name = aws_sesv2_configuration_set.transactional.configuration_set_name

  dkim_signing_attributes {
    next_signing_key_length = "RSA_2048_BIT"
  }

  tags = { Name = "${local.prefix}-ses-domain" }
}

# ---------------------------------------------------------------------------
# Custom MAIL FROM domain
# Sets the envelope sender to bounce.carmodpicker.com so SPF aligns with
# carmodpicker.com under DMARC (fixes the "MAIL FROM not aligned" warning).
# The matching MX + SPF records are in route53.tf.
# ---------------------------------------------------------------------------
resource "aws_sesv2_email_identity_mail_from_attributes" "domain" {
  email_identity         = aws_sesv2_email_identity.domain.email_identity
  mail_from_domain       = "bounce.carmodpicker.com"
  behavior_on_mx_failure = "USE_DEFAULT_VALUE"
}

# ---------------------------------------------------------------------------
# Account-level VDM attributes (engagement metrics + optimised delivery).
# Import: terraform import aws_sesv2_account_vdm_attributes.main aws_sesv2_account_vdm_attributes
# ---------------------------------------------------------------------------
resource "aws_sesv2_account_vdm_attributes" "main" {
  vdm_enabled = "ENABLED"

  dashboard_attributes {
    engagement_metrics = "ENABLED"
  }

  guardian_attributes {
    optimized_shared_delivery = "ENABLED"
  }
}
