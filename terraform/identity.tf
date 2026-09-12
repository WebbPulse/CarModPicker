
locals {
  identity_issuer = "https://${local.custom_domain ? "api.${local.domain_name}" : replace(local.api_url, "https://", "")}/api/auth"

  identity_audience = "carmodpicker-${var.environment}-api"

  identity_registrable_domain = local.domain_name

  identity_signing_key_arns = module.identity.signing_key_arns

  identity_oauth_redirect_uris = jsonencode(["${local.identity_issuer}/oauth/callback"])

  identity_webauthn_origins = jsonencode([local.frontend_url])
}

module "identity" {
  source = "app.terraform.io/WebbPulse/platform-modules/aws//modules/identity"

  version = "~> 2.10"

  name_prefix        = local.prefix
  issuer             = local.identity_issuer
  audience           = local.identity_audience
  registrable_domain = local.identity_registrable_domain

  identity_role_name = module.lambda_domain["identity"].role_id
  identity_role_arn  = module.lambda_domain["identity"].role_arn

  attach_role_policies = true

  point_in_time_recovery = true

  deletion_protection = var.environment == "production"

  table_policy_actions = local.dynamodb_domain_write_actions

  name_tag = true
}

output "identity_issuer" {
  description = "The identity issuer. Byte identical to the iss claim, to the issuer member of the discovery document, and from row 8 to the JWT authorizer's configured issuer. Verify after row 5 with: curl https://<api host>/api/auth/.well-known/openid-configuration"
  value       = local.identity_issuer
}

output "identity_audience" {
  description = "The aud claim the identity function will stamp on every access token, and the audience the row 8 authorizer will require."
  value       = local.identity_audience
}

output "identity_signing_key_arns" {
  description = "The identity signing keys, active signer first. A single key today; a second entry is a rotation in progress."
  value       = local.identity_signing_key_arns
}

output "identity_signing_key_alias" {
  description = "Alias of the active identity signing key. Points at the same key as the first entry of identity_signing_key_arns."
  value       = module.identity.signing_key_alias
}

output "identity_table_names" {
  description = "Logical name to physical name for the six identity tables the module creates. The application derives the same strings from DYNAMODB_TABLE_PREFIX rather than reading this, so it is here for a reviewer checking an apply rather than for a consumer."
  value       = module.identity.table_names
}
