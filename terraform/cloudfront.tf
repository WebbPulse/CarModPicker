locals {
  csp_api_origin = local.custom_domain ? "https://api.${local.domain_name}" : "https://*.execute-api.${var.aws_region}.amazonaws.com"
}

module "frontend" {
  source  = "terraform.webbpulse.com/WebbPulse/platform-modules/aws//modules/spa-frontend"
  version = "~> 2.37"

  name                       = "${local.prefix}-frontend"
  origin_access_control_name = "${local.prefix}-frontend-oac"
  origin_id                  = "${local.prefix}-frontend-s3"
  bucket_policy_sid          = "AllowCloudFrontOAC"

  aliases             = local.custom_domain ? ["www.${local.domain_name}", local.domain_name] : []
  acm_certificate_arn = module.certificate.certificate_arn

  viewer_request_function = {
    domain         = local.active_domain
    canonical_host = "www"
  }

  origin_request_policy_id = "88a5eaf4-2fd4-4709-b370-b4c650ea3fcf" # CORS-S3Origin

  security_headers = {
    content_security_policy = {
      mode = "report_only"
      script_src = [
        "'sha256-sZ74JUQgeZ+Iaq5vidBOBxmSTBiyZoshbNQK1H7GpU4='",
        "https://accounts.google.com/gsi/client",
        "https://pagead2.googlesyndication.com",
        "https://*.googlesyndication.com",
        "https://*.adtrafficquality.google",
        "https://fundingchoicesmessages.google.com",
      ]
      connect_src = [
        local.csp_api_origin,
        "https://accounts.google.com/gsi/",
        "https://*.google.com",
        "https://*.googlesyndication.com",
        "https://*.doubleclick.net",
        "https://*.adtrafficquality.google",
      ]
      frame_src = [
        "https://accounts.google.com/gsi/",
        "https://*.doubleclick.net",
        "https://*.googlesyndication.com",
        "https://www.google.com",
        "https://*.adtrafficquality.google",
        "https://fundingchoicesmessages.google.com",
      ]
      style_src = ["https://accounts.google.com/gsi/style"]
      img_src   = ["https:"]
    }
  }

  distribution_tags = { Name = "${local.prefix}-frontend" }

  access_gate = local.staging_gate_enabled ? {
    key_group_id                                           = module.staging_access_gate[0].key_group_id
    viewer_request_function_arn                            = module.staging_access_gate[0].viewer_request_function_arn
    login_origin_domain_name                               = module.staging_access_gate[0].login_origin_domain_name
    login_origin_access_control_id                         = module.staging_access_gate[0].login_origin_access_control_id
    auth_path_pattern                                      = module.staging_access_gate[0].auth_path_pattern
    cache_policy_id_caching_disabled                       = module.staging_access_gate[0].cache_policy_id_caching_disabled
    origin_request_policy_id_all_viewer_except_host_header = module.staging_access_gate[0].origin_request_policy_id_all_viewer_except_host_header

    login_origin_id = "${local.prefix}-access-gate-login"
  } : null

  create_dns_records = local.custom_domain
  zone_id            = module.staging_dns.zone_id
  dns_records = {
    www  = "www.${local.domain_name}"
    apex = local.domain_name
  }
}

moved {
  from = aws_cloudfront_function.frontend_uri_rewrite
  to   = module.frontend.aws_cloudfront_function.viewer_request[0]
}
