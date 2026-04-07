# TFC injects AWS credentials automatically via dynamic provider credentials.
# No static keys needed here.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
