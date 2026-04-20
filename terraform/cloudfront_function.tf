# CloudFront Function: rewrite directory-style paths to their index.html so
# prerendered SPA routes resolve against S3 keys like "about/index.html".
#
# Rules:
#   /              → untouched (CloudFront default_root_object handles this)
#   /foo/          → /foo/index.html
#   /foo           → /foo/index.html          (extensionless, treated as directory)
#   /foo.js        → untouched                (real asset)
#
# Paths that point at SPA routes we did NOT prerender (e.g. /parts/123) will
# rewrite to /parts/123/index.html, S3 will 404, and CloudFront's
# custom_error_response falls back to /index.html — same SPA-shell behavior
# as before, no regression.

resource "aws_cloudfront_function" "frontend_uri_rewrite" {
  name    = "${local.prefix}-frontend-uri-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Append /index.html to extensionless paths so prerendered routes resolve."
  publish = true
  code    = file("${path.module}/cloudfront_functions/uri_rewrite.js")
}
