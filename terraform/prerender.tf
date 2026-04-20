# ---------------------------------------------------------------------------
# Prerender.io — Lambda@Edge integration for bot traffic
#
# When var.prerender_token is set, CloudFront routes bot requests to
# service.prerender.io, which runs a headless browser against the SPA and
# returns fully-rendered HTML. Real users go straight to S3 as before.
#
# Feature gate: every resource in this file is conditional on
# var.prerender_token != "". Set the variable in TFC workspace vars to turn
# the integration on; clear it to tear everything down.
#
# Lambda@Edge quirks we work around:
#  - No environment variables → the token is baked into index.js via
#    templatefile at plan time.
#  - Origin rewrite is only allowed in origin-request triggers → the viewer-
#    request trigger only tags the request with a cache-partitioning header;
#    the origin-request trigger does the actual origin swap.
#  - Must live in us-east-1 regardless of primary region → every resource
#    here pins `provider = aws.us_east_1`.
# ---------------------------------------------------------------------------

locals {
  prerender_enabled = var.prerender_token != ""
}

data "archive_file" "prerender_lambda" {
  count       = local.prerender_enabled ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/build/prerender-lambda.zip"

  source {
    filename = "index.js"
    content = templatefile("${path.module}/lambda/prerender.js.tftpl", {
      prerender_token = var.prerender_token
    })
  }
}

resource "aws_iam_role" "prerender_lambda" {
  count    = local.prerender_enabled ? 1 : 0
  provider = aws.us_east_1
  name     = "${local.prefix}-prerender-edge"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        Service = ["lambda.amazonaws.com", "edgelambda.amazonaws.com"]
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "prerender_lambda_basic" {
  count      = local.prerender_enabled ? 1 : 0
  provider   = aws.us_east_1
  role       = aws_iam_role.prerender_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "prerender" {
  count    = local.prerender_enabled ? 1 : 0
  provider = aws.us_east_1

  function_name = "${local.prefix}-prerender-edge"
  role          = aws_iam_role.prerender_lambda[0].arn
  handler       = "index.handler"
  runtime       = "nodejs20.x"
  memory_size   = 128
  timeout       = 5
  publish       = true

  filename         = data.archive_file.prerender_lambda[0].output_path
  source_code_hash = data.archive_file.prerender_lambda[0].output_base64sha256
}

# Cache key must include CloudFront-Is-Bot so prerendered responses for bots
# are not served back to real users (and vice versa). query_string_behavior
# is "all" because prerender needs the full URL — /search?q=foo and
# /parts?make=honda are genuinely different pages.
resource "aws_cloudfront_cache_policy" "frontend_bot_aware" {
  count = local.prerender_enabled ? 1 : 0

  name    = "${local.prefix}-frontend-bot-aware"
  comment = "Partitions cache by bot flag + query string for the prerender.io integration."

  default_ttl = 86400
  max_ttl     = 31536000
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    enable_accept_encoding_brotli = true
    enable_accept_encoding_gzip   = true

    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "whitelist"
      headers {
        items = ["CloudFront-Is-Bot"]
      }
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

