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
# Crawler HTML snapshots — internal pipeline data, never served to users
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "crawl_data" {
  bucket = "${local.prefix}-crawl-data"
}

resource "aws_s3_bucket_public_access_block" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id

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

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowCloudFrontOAC"
      Effect = "Allow"
      Principal = {
        Service = "cloudfront.amazonaws.com"
      }
      Action   = "s3:GetObject"
      Resource = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.frontend.arn
        }
      }
    }]
  })
}

