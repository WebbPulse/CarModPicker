# TFC injects AWS credentials automatically via dynamic provider credentials.
# No static keys needed here.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# ACM certificates for CloudFront must be provisioned in us-east-1 regardless
# of the primary deployment region.
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = local.common_tags
  }
}
