# CloudFront requires ACM certificates in us-east-1.
resource "aws_acm_certificate" "carmodpicker" {
  provider          = aws.us_east_1
  domain_name       = "carmodpicker.com"
  validation_method = "DNS"

  subject_alternative_names = [
    "*.carmodpicker.com",
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.carmodpicker.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]

  allow_overwrite = true
}

# BLOCKED: cert stays PENDING_VALIDATION until the domain registrar NS records
# are updated to Route53's name servers (ns-517.awsdns-00.net etc.).
# Uncomment once the ACM certificate status moves to ISSUED.
#resource "aws_acm_certificate_validation" "carmodpicker" {
#  provider                = aws.us_east_1
#  certificate_arn         = aws_acm_certificate.carmodpicker.arn
#  validation_record_fqdns = [for record in aws_route53_record.acm_validation : record.fqdn]
#}
