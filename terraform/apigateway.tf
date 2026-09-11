
locals {
  routed_lambda_domains_declared = ["media", "build-logs", "moderation", "vehicles", "admin", "build-lists", "identity", "catalog", "users"]

  routed_lambda_domains = [
    for name in local.routed_lambda_domains_declared : name
    if contains(keys(local.lambda_domains), name)
  ]

  lambda_domain_path_prefixes = {
    media       = ["/api/images"]
    build-logs  = ["/api/build-logs"]
    moderation  = ["/api/votes", "/api/reports", "/api/bug-reports"]
    vehicles    = ["/api/car-generations", "/api/search"]
    admin       = ["/api/crawled-pages", "/api/part-price-alerts", "/api/admin/db-ops", "/api/admin/stats"]
    build-lists = ["/api/build-lists", "/api/build-list-parts", "/api/build-list-phases", "/api/build-list-labor-estimates"]
    identity    = ["/api/auth"]
    catalog     = ["/api/parts", "/api/part-manufacturers", "/api/categories", "/api/retailers"]
    users       = ["/api/users", "/api/app-settings"]
  }

  lambda_domain_generated_route_keys = merge([
    for name in local.routed_lambda_domains : {
      for key in flatten([
        for prefix in local.lambda_domain_path_prefixes[name] : [
          "ANY ${prefix}",
          "ANY ${prefix}/{proxy+}",
        ]
      ]) : key => { integration = name }
    }
  ]...)

  identity_jwt_route_keys = {
    "POST /api/auth/password"   = { integration = "identity", require_identity_jwt = true }
    "POST /api/auth/logout-all" = { integration = "identity", require_identity_jwt = true }

    "POST /api/auth/totp/enrol"     = { integration = "identity", require_identity_jwt = true }
    "POST /api/auth/totp/activate"  = { integration = "identity", require_identity_jwt = true }
    "POST /api/auth/totp/disable"   = { integration = "identity", require_identity_jwt = true }
    "POST /api/auth/recovery-codes" = { integration = "identity", require_identity_jwt = true }
    "POST /api/auth/step-up"        = { integration = "identity", require_identity_jwt = true }

    "POST /api/auth/passkeys/register/options"  = { integration = "identity", require_identity_jwt = true }
    "POST /api/auth/passkeys/register/verify"   = { integration = "identity", require_identity_jwt = true }
    "GET /api/auth/passkeys"                    = { integration = "identity", require_identity_jwt = true }
    "PATCH /api/auth/passkeys/{credential_id}"  = { integration = "identity", require_identity_jwt = true }
    "DELETE /api/auth/passkeys/{credential_id}" = { integration = "identity", require_identity_jwt = true }

    "POST /api/auth/oauth/{provider}/link"   = { integration = "identity", require_identity_jwt = true }
    "GET /api/auth/oauth/links"              = { integration = "identity", require_identity_jwt = true }
    "DELETE /api/auth/oauth/{provider}/link" = { integration = "identity", require_identity_jwt = true }
  }

  domain_identity_jwt_route_paths = {
    admin = [
      "POST /api/admin/db-ops/cars/delete-all",
      "POST /api/admin/db-ops/init/car-generations",
      "POST /api/admin/db-ops/init/part-categories",
      "POST /api/admin/db-ops/part-manufacturers/delete-all",
      "POST /api/admin/db-ops/parts/delete-all",
      "GET /api/admin/stats/table-counts",
      "POST /api/crawled-pages/scrape",
      "POST /api/part-price-alerts",
      "GET /api/part-price-alerts/me",
      "PATCH /api/part-price-alerts/{alert_id}",
      "DELETE /api/part-price-alerts/{alert_id}",
    ]

    "build-lists" = [
      "PUT /api/build-list-labor-estimates/{labor_estimate_id}",
      "DELETE /api/build-list-labor-estimates/{labor_estimate_id}",
      "POST /api/build-list-parts/{build_list_id}/create-and-add-part",
      "POST /api/build-list-parts/{build_list_id}/parts/{part_id}",
      "PUT /api/build-list-parts/{build_list_id}/parts/{part_id}",
      "DELETE /api/build-list-parts/{build_list_id}/parts/{part_id}",
      "PUT /api/build-list-parts/{build_list_part_id}",
      "DELETE /api/build-list-parts/{build_list_part_id}",
      "PUT /api/build-list-phases/{phase_id}",
      "DELETE /api/build-list-phases/{phase_id}",
      "POST /api/build-lists",
      "GET /api/build-lists/user/me",
      "POST /api/build-lists/{build_list_id}/append-images",
      "POST /api/build-lists/{build_list_id}/copy",
      "DELETE /api/build-lists/{build_list_id}/images/{image_index}",
      "POST /api/build-lists/{build_list_id}/labor-estimates",
      "POST /api/build-lists/{build_list_id}/phases",
      "PATCH /api/build-lists/{build_list_id}/primary-image",
      "PUT /api/build-lists/{entity_id}",
      "DELETE /api/build-lists/{entity_id}",
    ]

    "build-logs" = [
      "POST /api/build-logs/build-list/{build_list_id}/posts",
      "PUT /api/build-logs/posts/{post_id}",
      "DELETE /api/build-logs/posts/{post_id}",
    ]

    catalog = [
      "POST /api/part-manufacturers",
      "PUT /api/part-manufacturers/{part_manufacturer_id}",
      "DELETE /api/part-manufacturers/{part_manufacturer_id}",
      "POST /api/parts",
      "GET /api/parts/find-by-part-manufacturer-and-part-number",
      "PUT /api/parts/{entity_id}",
      "DELETE /api/parts/{part_id}",
      "POST /api/parts/{part_id}/append-images",
      "DELETE /api/parts/{part_id}/images/{image_index}",
      "POST /api/parts/{part_id}/listings",
      "PATCH /api/parts/{part_id}/primary-image",
      "POST /api/retailers",
      "POST /api/retailers/get-or-create",
      "PUT /api/retailers/{retailer_id}",
      "DELETE /api/retailers/{retailer_id}",
    ]

    media = [
      "GET /api/images/admin/count",
      "GET /api/images/admin/count-by-entity-type",
      "GET /api/images/admin/orphaned",
      "POST /api/images/admin/purge-orphaned",
      "GET /api/images/by-source-url",
      "DELETE /api/images/delete",
      "POST /api/images/fetch-from-url",
      "POST /api/images/upload",
    ]

    moderation = [
      "GET /api/bug-reports/admin/list",
      "GET /api/bug-reports/admin/list-with-details",
      "GET /api/bug-reports/{bug_report_id}",
      "PUT /api/bug-reports/{bug_report_id}",
      "DELETE /api/bug-reports/{bug_report_id}",
      "GET /api/reports/admin/list",
      "GET /api/reports/admin/list-with-details",
      "GET /api/reports/my-reports",
      "POST /api/reports/{entity_type}/{entity_id}",
      "GET /api/reports/{report_id}",
      "PUT /api/reports/{report_id}",
      "DELETE /api/reports/{report_id}",
      "GET /api/votes/admin/flagged/{entity_type}",
      "POST /api/votes/{entity_type}/{entity_id}",
      "DELETE /api/votes/{entity_type}/{entity_id}",
    ]

    users = [
      "PUT /api/app-settings",
      "GET /api/users/admin/users",
      "PUT /api/users/admin/users/{user_id}",
      "DELETE /api/users/admin/users/{user_id}",
      "GET /api/users/me",
      "POST /api/users/me/profile-picture",
      "DELETE /api/users/me/profile-picture",
      "PUT /api/users/{user_id}",
      "DELETE /api/users/{user_id}",
    ]
  }

  domain_identity_jwt_route_keys = merge([
    for domain, keys in local.domain_identity_jwt_route_paths : {
      for key in keys : key => {
        integration          = domain
        require_identity_jwt = var.domain_jwt_enforced
      }
    }
  ]...)

  domain_anonymous_guard_route_keys = {
    "GET /api/reports/count"     = { integration = "moderation" }
    "GET /api/bug-reports/count" = { integration = "moderation" }
  }

  lambda_domain_route_keys = merge(
    local.lambda_domain_generated_route_keys,
    local.identity_jwt_route_keys,
    local.domain_identity_jwt_route_keys,
    local.domain_anonymous_guard_route_keys,
  )
}

module "api" {
  source = "app.terraform.io/WebbPulse/platform-modules/aws//modules/http-api"

  version = "~> 2.9"

  name        = "${local.prefix}-api"
  description = "CarModPicker ${var.environment} API (Lambda proxy)"

  integrations = {
    for name in local.routed_lambda_domains : name => {
      lambda_function_name = module.lambda_domain[name].function_name
      lambda_invoke_arn    = module.lambda_domain[name].invoke_arn
      timeout_milliseconds = 29000
    }
  }

  default_integration = null

  routes = local.lambda_domain_route_keys

  throttling_burst_limit    = var.api_throttle_burst_limit
  throttling_rate_limit     = var.api_throttle_rate_limit
  access_log_retention_days = 7

  cors_configuration = {
    allow_origins = local.cors_allow_origins
    allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers = [
      "Accept",
      "Authorization",
      "Content-Type",
      "Origin",
      "X-Admin-Cron-Key",
      "X-Requested-With",
    ]
    expose_headers = [
      "Retry-After",
      "X-RateLimit-Limit-Hour",
      "X-RateLimit-Limit-Minute",
      "X-Request-ID",
    ]
    allow_credentials = true
    max_age           = 86400
  }

  disable_execute_api_endpoint = local.staging_gate_enabled
  authorizer_id                = local.staging_gate_enabled ? module.staging_access_gate[0].http_api_authorizer_id : null

  identity_jwt = local.identity_jwt_native_enforced ? {
    issuer   = local.identity_issuer
    audience = local.identity_audience
  } : null

  identity_jwt_depends_on = local.identity_jwt_native_enforced ? [module.lambda_domain["identity"]] : []

  domain_name      = local.custom_domain ? "api.${local.domain_name}" : null
  certificate_arn  = module.api_certificate.certificate_arn
  zone_id          = local.custom_domain ? module.staging_dns.zone_id : null
  domain_name_tags = { Name = "${local.prefix}-api-domain" }
}
