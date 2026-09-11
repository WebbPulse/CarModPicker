
locals {
  lambda_domain_names = [
    "media",
    "build-logs",
    "moderation",
    "vehicles",
    "admin",
    "build-lists",
    "identity",
    "catalog",
    "users",
  ]
}

module "registry" {
  source  = "app.terraform.io/WebbPulse/platform-modules/aws//modules/ecr-repository"
  version = "~> 2.0"

  name_prefix = local.prefix

  repositories = { for domain in local.lambda_domain_names : domain => {} }
}
