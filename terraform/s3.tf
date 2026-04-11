# ---------------------------------------------------------------------------
# User image uploads — private, accessed via presigned URLs
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "user_images" {
  bucket = "${local.prefix}-user-images"
}

resource "aws_s3_bucket_public_access_block" "user_images" {
  bucket = aws_s3_bucket.user_images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# Frontend SPA — private origin, served exclusively through CloudFront
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "frontend" {
  bucket = "${local.prefix}-frontend"
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# CloudFront Origin Access Control — allows CloudFront to read the frontend
# bucket without making the bucket itself public.
resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.prefix}-frontend-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# BLOCKED: references aws_cloudfront_distribution.frontend.arn (blocked in cloudfront.tf).
# Uncomment once CloudFront is deployed.
#resource "aws_s3_bucket_policy" "frontend" {
#  bucket = aws_s3_bucket.frontend.id
#  policy = jsonencode({
#    Version = "2012-10-17"
#    Statement = [{
#      Sid    = "AllowCloudFrontOAC"
#      Effect = "Allow"
#      Principal = {
#        Service = "cloudfront.amazonaws.com"
#      }
#      Action   = "s3:GetObject"
#      Resource = "${aws_s3_bucket.frontend.arn}/*"
#      Condition = {
#        StringEquals = {
#          "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
#        }
#      }
#    }]
#  })
#}

# ---------------------------------------------------------------------------
# Apex redirect — carmodpicker.com → https://www.carmodpicker.com
# S3 website hosting requires public access for the redirect to work.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "apex_redirect" {
  bucket = "carmodpicker.com"
}

resource "aws_s3_bucket_website_configuration" "apex_redirect" {
  bucket = aws_s3_bucket.apex_redirect.id

  redirect_all_requests_to {
    host_name = "www.carmodpicker.com"
    protocol  = "https"
  }
}

resource "aws_s3_bucket_public_access_block" "apex_redirect" {
  bucket = aws_s3_bucket.apex_redirect.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}
