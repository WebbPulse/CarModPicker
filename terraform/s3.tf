module "user_images_bucket" {
  source  = "terraform.webbpulse.com/WebbPulse/platform-modules/aws//modules/s3-bucket"
  version = "~> 2.39"

  bucket = "${local.prefix}-user-images"

  lifecycle_rules = {
    "expire-replaced-images" = {
      noncurrent_version_expiration_days     = 30
      abort_incomplete_multipart_upload_days = 7
    }
  }
}

module "crawl_data_bucket" {
  source  = "terraform.webbpulse.com/WebbPulse/platform-modules/aws//modules/s3-bucket"
  version = "~> 2.39"

  bucket = "${local.prefix}-crawl-data"

  lifecycle_rules = {
    "archive-old-snapshots" = {
      transitions                            = [{ days = 90, storage_class = "DEEP_ARCHIVE" }]
      noncurrent_version_expiration_days     = 7
      abort_incomplete_multipart_upload_days = 7
    }
  }
}

moved {
  from = aws_s3_bucket.user_images
  to   = module.user_images_bucket.aws_s3_bucket.this
}

moved {
  from = aws_s3_bucket_public_access_block.user_images
  to   = module.user_images_bucket.aws_s3_bucket_public_access_block.this
}

moved {
  from = aws_s3_bucket.crawl_data
  to   = module.crawl_data_bucket.aws_s3_bucket.this
}

moved {
  from = aws_s3_bucket_public_access_block.crawl_data
  to   = module.crawl_data_bucket.aws_s3_bucket_public_access_block.this
}

moved {
  from = aws_s3_bucket_lifecycle_configuration.crawl_data
  to   = module.crawl_data_bucket.aws_s3_bucket_lifecycle_configuration.this[0]
}
