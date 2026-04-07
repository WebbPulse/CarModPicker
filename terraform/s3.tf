resource "aws_s3_bucket" "assets" {
  bucket = "${local.prefix}-assets"
}

# Apex redirect bucket — carmodpicker.com → https://www.carmodpicker.com
# S3 website hosting requires public access block to be open for redirect to work.
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

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket = aws_s3_bucket.assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
