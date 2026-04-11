resource "aws_route53_zone" "carmodpicker" {
  name = "carmodpicker.com"
}

# Apex → S3 redirect bucket (carmodpicker.com → www.carmodpicker.com)
resource "aws_route53_record" "apex_a" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "carmodpicker.com"
  type    = "A"

  alias {
    name                   = "s3-website-us-west-2.amazonaws.com"
    zone_id                = "Z3BJ6K6RIION7M" # S3 hosted zone ID for us-west-2
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

# MX record for Google Workspace email
resource "aws_route53_record" "mx" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "carmodpicker.com"
  type    = "MX"
  ttl     = 60
  records = ["1 SMTP.GOOGLE.COM."]
}

# SES DKIM verification records
resource "aws_route53_record" "ses_dkim_1" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "whak5n4x5w7sfqfrp5rfpcuzseee6i6r._domainkey.carmodpicker.com"
  type    = "CNAME"
  ttl     = 60
  records = ["whak5n4x5w7sfqfrp5rfpcuzseee6i6r.dkim.amazonses.com"]
}

resource "aws_route53_record" "ses_dkim_2" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "pgc356f5j4c6v6efvxocs73gtmklyv6g._domainkey.carmodpicker.com"
  type    = "CNAME"
  ttl     = 60
  records = ["pgc356f5j4c6v6efvxocs73gtmklyv6g.dkim.amazonses.com"]
}

resource "aws_route53_record" "ses_dkim_3" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "4manrayokzig5dbsj5j2yncnrveannx7._domainkey.carmodpicker.com"
  type    = "CNAME"
  ttl     = 60
  records = ["4manrayokzig5dbsj5j2yncnrveannx7.dkim.amazonses.com"]
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
