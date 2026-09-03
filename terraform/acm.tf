# CloudFront requires ACM certificates in us-east-1.
resource "aws_acm_certificate" "carmodpicker" {
  count = local.custom_domain ? 1 : 0

  provider          = aws.us_east_1
  domain_name       = var.domain_name
  validation_method = "DNS"

  subject_alternative_names = [
    "*.${var.domain_name}",
  ]

  lifecycle {
    create_before_destroy = true
  }
}

moved {
  from = aws_acm_certificate.carmodpicker
  to   = aws_acm_certificate.carmodpicker[0]
}

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in flatten(aws_acm_certificate.carmodpicker[*].domain_validation_options) : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]

  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "carmodpicker" {
  count = local.custom_domain ? 1 : 0

  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.carmodpicker[0].arn
  validation_record_fqdns = [for record in aws_route53_record.acm_validation : record.fqdn]
}

moved {
  from = aws_acm_certificate_validation.carmodpicker
  to   = aws_acm_certificate_validation.carmodpicker[0]
}

# API Gateway custom domains need a regional certificate in the API's own region.
resource "aws_acm_certificate" "api" {
  count = local.custom_domain ? 1 : 0

  domain_name       = "api.${var.domain_name}"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "acm_api_validation" {
  for_each = {
    for dvo in flatten(aws_acm_certificate.api[*].domain_validation_options) : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.carmodpicker[0].zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]

  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "api" {
  count = local.custom_domain ? 1 : 0

  certificate_arn         = aws_acm_certificate.api[0].arn
  validation_record_fqdns = [for record in aws_route53_record.acm_api_validation : record.fqdn]
}
