resource "aws_route53_zone" "carmodpicker" {
  count = local.custom_domain ? 1 : 0

  name = local.domain_name
}

moved {
  from = aws_route53_zone.carmodpicker
  to   = aws_route53_zone.carmodpicker[0]
}

resource "aws_route53_record" "parent_delegation" {
  count    = local.parent_delegation ? 1 : 0
  provider = aws.parent_dns

  zone_id = var.parent_route53_zone_id
  name    = local.domain_name
  type    = "NS"
  ttl     = 300
  records = aws_route53_zone.carmodpicker[0].name_servers
}

# Apex → CloudFront (redirect to www is done by the CloudFront viewer-request
# function so we don't need a separate S3 website bucket to handle it).
resource "aws_route53_record" "apex_a" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = local.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

moved {
  from = aws_route53_record.apex_a
  to   = aws_route53_record.apex_a[0]
}

# www → CloudFront distribution
resource "aws_route53_record" "www" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "www.${local.domain_name}"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

moved {
  from = aws_route53_record.www
  to   = aws_route53_record.www[0]
}

# api → App Runner service URL
resource "aws_route53_record" "api" {
  count = local.custom_domain && local.legacy_stack && local.api_target == "legacy" ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "api.${local.domain_name}"
  type    = "CNAME"
  ttl     = 60
  records = [aws_apprunner_service.backend[0].service_url]
}

moved {
  from = aws_route53_record.api
  to   = aws_route53_record.api[0]
}

# api → HTTP API custom domain
resource "aws_route53_record" "api_lambda" {
  count = local.custom_domain && local.api_target == "lambda" ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "api.${local.domain_name}"
  type    = "A"

  alias {
    name                   = aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].target_domain_name
    zone_id                = aws_apigatewayv2_domain_name.api[0].domain_name_configuration[0].hosted_zone_id
    evaluate_target_health = false
  }
}

# Apex TXT records. Route53 stores all TXT records at the same name in a
# single RRSet, so SPF and domain-verification strings share one resource.
resource "aws_route53_record" "spf" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = local.domain_name
  type    = "TXT"
  ttl     = 300
  records = [
    "v=spf1 include:amazonses.com ~all",
    "google-site-verification=kJMc_JNCEf4utqVGE2_00H14I1TUKJKUakLPbvq13_8",
  ]
}

moved {
  from = aws_route53_record.spf
  to   = aws_route53_record.spf[0]
}

# Google Search Console domain ownership verification for www.carmodpicker.com
resource "aws_route53_record" "www_google_site_verification" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "www.${local.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["google-site-verification=kJMc_JNCEf4utqVGE2_00H14I1TUKJKUakLPbvq13_8"]
}

moved {
  from = aws_route53_record.www_google_site_verification
  to   = aws_route53_record.www_google_site_verification[0]
}

# SES DKIM verification records
resource "aws_route53_record" "ses_dkim" {
  count   = local.custom_domain ? 3 : 0
  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "${aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens[count.index]}._domainkey.${local.domain_name}"
  type    = "CNAME"
  ttl     = 60
  records = ["${aws_sesv2_email_identity.domain[0].dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
}

moved {
  from = aws_route53_record.ses_dkim_1
  to   = aws_route53_record.ses_dkim[0]
}

moved {
  from = aws_route53_record.ses_dkim_2
  to   = aws_route53_record.ses_dkim[1]
}

moved {
  from = aws_route53_record.ses_dkim_3
  to   = aws_route53_record.ses_dkim[2]
}

# Custom MAIL FROM domain records (SPF alignment for DMARC)
resource "aws_route53_record" "ses_mail_from_mx" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "bounce.${local.domain_name}"
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.${var.aws_region}.amazonses.com"]
}

moved {
  from = aws_route53_record.ses_mail_from_mx
  to   = aws_route53_record.ses_mail_from_mx[0]
}

resource "aws_route53_record" "ses_mail_from_spf" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "bounce.${local.domain_name}"
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com ~all"]
}

moved {
  from = aws_route53_record.ses_mail_from_spf
  to   = aws_route53_record.ses_mail_from_spf[0]
}

# DMARC policy record
resource "aws_route53_record" "dmarc" {
  count = local.custom_domain ? 1 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = "_dmarc.${local.domain_name}"
  type    = "TXT"
  ttl     = 60
  records = ["v=DMARC1; p=none;"]
}

moved {
  from = aws_route53_record.dmarc
  to   = aws_route53_record.dmarc[0]
}

# App Runner custom domain validation records (Stage 2 — now active)
# These CNAMEs let App Runner verify ownership of api.carmodpicker.com.
# count=2 because App Runner always emits exactly 2 validation records; using
# for_each here is blocked by Terraform since the keys are unknown until apply.
resource "aws_route53_record" "apprunner_validation" {
  count = local.custom_domain && local.legacy_stack ? 2 : 0

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = tolist(aws_apprunner_custom_domain_association.api[0].certificate_validation_records)[count.index].name
  type    = tolist(aws_apprunner_custom_domain_association.api[0].certificate_validation_records)[count.index].type
  ttl     = 60
  records = [tolist(aws_apprunner_custom_domain_association.api[0].certificate_validation_records)[count.index].value]
}
