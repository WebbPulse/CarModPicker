resource "aws_route53_zone" "carmodpicker" {
  name = "carmodpicker.com"
}

# Apex → CloudFront (redirect to www is done by the CloudFront viewer-request
# function so we don't need a separate S3 website bucket to handle it).
resource "aws_route53_record" "apex_a" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "carmodpicker.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# www → CloudFront distribution
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "www.carmodpicker.com"
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}

# api → App Runner service URL
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "api.carmodpicker.com"
  type    = "CNAME"
  ttl     = 60
  records = [aws_apprunner_service.backend.service_url]
}

# Apex TXT records. Route53 stores all TXT records at the same name in a
# single RRSet, so SPF and domain-verification strings share one resource.
resource "aws_route53_record" "spf" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "carmodpicker.com"
  type    = "TXT"
  ttl     = 300
  records = [
    "v=spf1 include:amazonses.com ~all",
    "google-site-verification=kJMc_JNCEf4utqVGE2_00H14I1TUKJKUakLPbvq13_8",
  ]
}

# Google Search Console domain ownership verification for www.carmodpicker.com
resource "aws_route53_record" "www_google_site_verification" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "www.carmodpicker.com"
  type    = "TXT"
  ttl     = 300
  records = ["google-site-verification=kJMc_JNCEf4utqVGE2_00H14I1TUKJKUakLPbvq13_8"]
}

# SES DKIM verification records
resource "aws_route53_record" "ses_dkim" {
  count   = 3
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "${aws_sesv2_email_identity.domain.dkim_signing_attributes[0].tokens[count.index]}._domainkey.carmodpicker.com"
  type    = "CNAME"
  ttl     = 60
  records = ["${aws_sesv2_email_identity.domain.dkim_signing_attributes[0].tokens[count.index]}.dkim.amazonses.com"]
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
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "bounce.carmodpicker.com"
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.us-west-2.amazonses.com"]
}

resource "aws_route53_record" "ses_mail_from_spf" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "bounce.carmodpicker.com"
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com ~all"]
}

# DMARC policy record
resource "aws_route53_record" "dmarc" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "_dmarc.carmodpicker.com"
  type    = "TXT"
  ttl     = 60
  records = ["v=DMARC1; p=none;"]
}

# App Runner custom domain validation records (Stage 2 — now active)
# These CNAMEs let App Runner verify ownership of api.carmodpicker.com.
# count=2 because App Runner always emits exactly 2 validation records; using
# for_each here is blocked by Terraform since the keys are unknown until apply.
resource "aws_route53_record" "apprunner_validation" {
  count = 2

  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = tolist(aws_apprunner_custom_domain_association.api.certificate_validation_records)[count.index].name
  type    = tolist(aws_apprunner_custom_domain_association.api.certificate_validation_records)[count.index].type
  ttl     = 60
  records = [tolist(aws_apprunner_custom_domain_association.api.certificate_validation_records)[count.index].value]
}
