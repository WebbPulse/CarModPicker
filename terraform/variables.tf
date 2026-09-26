variable "aws_region" {
  description = "AWS region to deploy resources into"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Deployment environment (production, staging)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging"], var.environment)
    error_message = "environment must be 'production' or 'staging'"
  }
}

variable "custom_domain_enabled" {
  description = "Provision Route53, ACM and custom hostnames. null = production or staging_profile 'full'."
  type        = bool
  default     = null
  nullable    = true
}

variable "domain_name" {
  description = "Registered apex domain. Production serves it directly; staging serves staging.<domain_name> from a delegated child zone."
  type        = string
  default     = "carmodpicker.com"
}

variable "parent_route53_zone_id" {
  description = "Hosted zone id of <domain_name> in the production account. Staging writes the NS delegation for its child zone into it. Pushed to the staging workspace by WebbPulse-Platform."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.environment != "staging" || !coalesce(var.custom_domain_enabled, var.staging_profile == "full") || var.parent_route53_zone_id != null
    error_message = "parent_route53_zone_id must be set when environment is 'staging' and the custom domain is on: the staging.<domain_name> zone is delegated from the parent zone owned by the production workspace. WebbPulse-Platform pushes it to the workspace."
  }
}

variable "route53_write_role_arn" {
  description = "IAM role in the production account assumed to write the NS delegation record into parent_route53_zone_id. Pushed to the staging workspace by WebbPulse-Platform; null means no cross-account provider is configured."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition     = var.environment != "staging" || !coalesce(var.custom_domain_enabled, var.staging_profile == "full") || var.route53_write_role_arn != null
    error_message = "route53_write_role_arn must be set when environment is 'staging' and the custom domain is on: the NS delegation for staging.<domain_name> is written into the parent zone through that role. WebbPulse-Platform pushes it to the workspace."
  }
}

variable "api_throttle_burst_limit" {
  description = "HTTP API $default stage throttling burst limit"
  type        = number
  default     = 50
}

variable "api_throttle_rate_limit" {
  description = "HTTP API $default stage steady-state requests per second"
  type        = number
  default     = 25
}

variable "email_from" {
  description = "Sender address for transactional email. null = no-reply@ the domain SES is verified for (the served domain with a custom domain, the apex otherwise)."
  type        = string
  default     = null
  nullable    = true
}

variable "staging_profile" {
  description = "How much of the stack this environment provisions. 'none' means the environment is switched off and must not be built. Set on the workspace by the WebbPulse-Organization workspace factory."
  type        = string
  default     = "full"

  validation {
    condition     = contains(["none", "reduced", "full"], var.staging_profile)
    error_message = "staging_profile must be one of 'none', 'reduced', or 'full'."
  }

  validation {
    condition     = var.staging_profile != "none"
    error_message = "Refusing to plan: staging_profile is 'none', so this environment is switched off and no resources should be created in it. To stand this environment up, change staging_profile to 'reduced' or 'full' on the workspace in WebbPulse-Organization/bootstrap/locals.tf."
  }
}

variable "staging_access_gate" {
  description = "Put the staging site and API behind the shared staging access gate (Cognito sign-in plus CloudFront signed cookies). WebbPulse-Platform sets this on staging workspaces only; production never receives it and every gate resource is skipped there."
  type        = bool
  default     = false
}

variable "staging_access_users" {
  description = "Email addresses allowed through the staging access gate; each becomes an invited Cognito user. WebbPulse-Platform sets this on staging workspaces only; production never receives it."
  type        = list(string)
  default     = []

  validation {
    condition     = !var.staging_access_gate || length(var.staging_access_users) > 0
    error_message = "staging_access_users must list at least one email when staging_access_gate is true. An empty list is a gate nobody can open."
  }
}

variable "passkeys_enabled" {
  description = "Mount the package's seven passkey routes on the identity function. False leaves them undeclared, whatever the passkeys and webauthn-challenges tables hold. Set true on the staging workspace; production receives it at promotion."
  type        = bool
  default     = false
}

variable "passkeys_passwordless" {
  description = "Allow a passkey to be a first factor, so POST /api/auth/login/passkey/options and verify serve. False with passkeys_enabled true mounts the five management routes and refuses both login routes, which makes a passkey a second factor only. Set true on the staging workspace; production receives it at promotion."
  type        = bool
  default     = false
}

variable "oauth_google_client_id" {
  description = "Client id of the Google OAuth application. Empty means the package declares no Google route and does not advertise Google on GET /api/auth/oauth/providers. Not a secret; set as an ordinary workspace variable."
  type        = string
  default     = ""
}

variable "oauth_github_client_id" {
  description = "Client id of the GitHub OAuth application. Empty means the package declares no GitHub route and does not advertise GitHub on GET /api/auth/oauth/providers. Not a secret; set as an ordinary workspace variable."
  type        = string
  default     = ""
}

variable "identity_jwt_mode" {
  description = <<-EOT
    How the gateway enforces the identity module's access tokens on the routes that need an
    authenticated caller. The routes themselves are marked once, with require_identity_jwt in
    terraform/apigateway.tf; this variable only picks which of the two mechanisms carries out the
    check, because an HTTP API route takes exactly one authorizer and which one is free depends on
    whether the staging access gate is in front of the API.

      "gate"    The staging access gate's own Lambda authorizer does both checks: the signed gate
                cookie as before, then a valid Bearer access token on the marked routes. This is
                what a gated staging environment has to use, because the gate already occupies the
                route's one authorizer slot. module.api.identity_jwt stays null and no route moves.

      "native"  API Gateway's own JWT authorizer verifies the token: the RS256 signature against
                the issuer's JWKS, then iss, aud, exp and nbf, with nothing of ours on the request
                path. This is the ungated shape, which is what production is. The marked routes
                become authorization_type JWT and are replaced, because the platform module keeps
                them in a separate resource so the .well-known routes can exist before the
                authorizer and the protected routes after it.

      "off"     Nothing is enforced at the gateway. The identity function still verifies the token
                itself, which it does in every mode: this is an extra gate in front of it, never a
                replacement for its own check. Every route named in apigateway.tf keeps answering
                exactly as it does today.

    The default is "off" and PRODUCTION KEEPS IT for now. "native" creates an authorizer whose
    CreateAuthorizer call synchronously fetches <issuer>/.well-known/openid-configuration from
    outside AWS, so it fails unless the identity function is already deployed and already serving
    those two documents at the production API host. The identity stack has not been promoted to
    production yet, so turning this on there before that promotion fails the apply rather than
    leaving anything open. Set it to "native" on the production workspace in the apply that follows
    the promotion, not before.
  EOT

  type    = string
  default = "off"

  validation {
    condition     = contains(["native", "gate", "off"], var.identity_jwt_mode)
    error_message = "identity_jwt_mode must be one of native, gate or off."
  }

  validation {
    condition     = var.identity_jwt_mode != "native" || var.environment != "staging"
    error_message = "identity_jwt_mode must not be native in staging. Every route there carries the staging access gate's REQUEST authorizer and a route takes exactly one authorizer, so a native JWT authorizer has no slot to occupy. Use gate, which moves the same check into the gate's own Lambda."
  }
}

variable "domain_jwt_enforced" {
  description = <<-EOT
    Whether the 80 domain route keys that need an authenticated caller actually require an
    identity access token at the gateway. Row 12 of docs/identity-adoption.md.

    THE KEYS EXIST EITHER WAY. local.domain_identity_jwt_route_keys writes all 80 route keys into
    the API in both settings, pointing at the same integration the generated `ANY` pair points at,
    so a request reaches the same function by the same route regardless. This variable only decides
    whether each of those keys additionally carries require_identity_jwt, which is what puts it in
    module.api.identity_jwt_route_keys and so into the gate Lambda's list.

    THE DEFAULT IS false AND IT HAS TO BE, because of the ordering this row sits in. With
    identity_jwt_mode = "gate", the moment a key is marked the gate demands a valid RS256 identity
    access token on it, and the CarModPicker frontend still sends the legacy HS256 session token,
    which the gate rejects. Marking the keys before the frontend cutover signs every user out of
    every write path in staging. So the keys land first, unmarked and inert, and enforcement is a
    later one line flip on the workspace variable once the frontend sends identity tokens.

    WHAT THE FLIP COSTS IN A PLAN. In staging the platform module keeps a marked route in the same
    resource at the same address as an unmarked one, with the same authorization_type CUSTOM and
    the same gate authorizer, because it only moves routes into its own JWT resource when
    module.api.identity_jwt is non-null, and in gate mode that is null. So flipping this changes no
    route resource at all: the only diff is the gate authorizer Lambda's environment, which gains
    the 80 keys. Flipping it back is the rollback and is equally cheap.
  EOT

  type    = bool
  default = false
}

variable "ephemeral_users_enabled" {
  description = <<-EOT
    Whether the identity function mounts the admin-only ephemeral e2e user routes,
    POST /api/auth/e2e/users and DELETE /api/auth/e2e/users/{user_id}.

    The e2e suite creates one throwaway login user per xdist worker and deletes it at
    session teardown, so runs no longer share the durable account and no longer need a
    concurrency group. The caller must present a KMS-minted token carrying the admin
    role, which only the e2e workflow can produce.

    Off by default and set true only on the staging workspace. The package additionally
    refuses to mount the routes when IDENTITY_ENVIRONMENT is a production one whatever
    this flag says, so a misconfigured production deployment has no route to reach.
  EOT

  type    = bool
  default = false
}

variable "adopt_spans_log_group" {
  description = "Adopt the reserved aws/spans log group into state and hold it at the platform's 7 day retention. X-Ray creates that group itself the first time it writes a span to the CloudWatchLogs destination, and it cannot be created ahead of time because CreateLogGroup rejects names beginning with aws/. An import block whose target does not exist is a plan time error, so a brand new account has to apply once with this false, generate one span, and then set it true. true is correct for every environment where a span has already been written, which is both of ours."
  type        = bool
  default     = true
}
