resource "aws_route53_zone" "carmodpicker" {
  name = "carmodpicker.com"
}

# Apex → S3 redirect bucket (carmodpicker.com → www.carmodpicker.com)
resource "aws_route53_record" "apex_a" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "carmodpicker.com"
  type    = "A"

  alias {
    name                   = "s3-website-us-west-1.amazonaws.com"
    zone_id                = "Z2F56UZL2M1ACD" # S3 hosted zone ID for us-west-1
    evaluate_target_health = false
  }
}

# www → Railway frontend
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "www.carmodpicker.com"
  type    = "CNAME"
  ttl     = 300
  records = ["jo3zzwr7.up.railway.app"]
}

resource "aws_route53_record" "railway_verify_www" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "_railway-verify.www.carmodpicker.com"
  type    = "TXT"
  ttl     = 300
  records = ["railway-verify=ea13a6f8d9a24d8af26da62167f9c217c8b88294ee24d1fdd1a0b9a129d34664"]
}

# api → Railway backend
resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "api.carmodpicker.com"
  type    = "CNAME"
  ttl     = 300
  records = ["8lx3zk49.up.railway.app"]
}

resource "aws_route53_record" "railway_verify_api" {
  zone_id = aws_route53_zone.carmodpicker.zone_id
  name    = "_railway-verify.api.carmodpicker.com"
  type    = "TXT"
  ttl     = 300
  records = ["railway-verify=bd2396189656a92092ba7bdc8c8a1e3ecae3fc523fa11d3eaa670c309e018a2a"]
}
