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
# BLOCKED: depends on aws_cloudfront_distribution.frontend (blocked in cloudfront.tf).
# Uncomment once the ACM cert is ISSUED and CloudFront is deployed.
#resource "aws_route53_record" "www" {
#  zone_id = aws_route53_zone.carmodpicker.zone_id
#  name    = "www.carmodpicker.com"
#  type    = "A"
#
#  alias {
#    name                   = aws_cloudfront_distribution.frontend.domain_name
#    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
#    evaluate_target_health = false
#  }
#}

# api → App Runner service URL
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "api.carmodpicker.com"
  type    = "CNAME"
  ttl     = 60
  records = [aws_apprunner_service.backend.service_url]
}

# App Runner custom domain validation records
# aws_apprunner_custom_domain_association exposes certificate_validation_records
# that must be added to DNS for App Runner to activate the custom domain.
#
# IMPORTANT: These records use for_each keys derived from App Runner's certificate
# validation records, which are unknown until after aws_apprunner_custom_domain_association
# is created. In a VCS-driven workflow this requires two applies:
#   Stage 1: Push with this block commented out → apply creates the association
#   Stage 2: Uncomment this block → push → apply adds the DNS validation records
#



#resource "aws_route53_record" "apprunner_validation" {
#  for_each = {
#    for r in aws_apprunner_custom_domain_association.api.certificate_validation_records :
#    r.name => r
#  }
#
#  zone_id = aws_route53_zone.carmodpicker.zone_id
#  name    = each.value.name
#  type    = each.value.type
#  ttl     = 60
#  records = [each.value.value]
#}
