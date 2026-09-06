# GitHub Actions OIDC provider — separate from the HCP Terraform OIDC provider
# (app.terraform.io). This allows GitHub Actions workflows to assume an AWS role
# via short-lived OIDC tokens without storing long-lived AWS credentials as secrets.
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1", "1c58a3a8518e8759bf075b76b750d4f2df264fcd"]
}

resource "aws_iam_role" "github_actions_deploy" {
  name = "${local.prefix}-github-actions-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:WebbPulse/CarModPicker:*"
          }
        }
      }
    ]
  })
}

locals {
  github_actions_legacy_statements = local.legacy_stack ? [
    # ECR — push backend images
    {
      Effect = "Allow"
      Action = [
        "ecr:GetAuthorizationToken",
      ]
      Resource = "*"
    },
    {
      Effect = "Allow"
      Action = [
        "ecr:BatchCheckLayerAvailability",
        "ecr:CompleteLayerUpload",
        "ecr:InitiateLayerUpload",
        "ecr:PutImage",
        "ecr:UploadLayerPart",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
      ]
      Resource = aws_ecr_repository.backend[0].arn
    },
    # App Runner — trigger redeployment and poll readiness before deploying
    {
      Effect   = "Allow"
      Action   = ["apprunner:StartDeployment", "apprunner:DescribeService"]
      Resource = aws_apprunner_service.backend[0].arn
    },
  ] : []

  github_actions_statements = [
    # Lambda — upload the zip to the artifacts bucket, then point the function at it
    {
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:GetObject"]
      Resource = "${aws_s3_bucket.lambda_artifacts.arn}/*"
    },
    {
      Effect = "Allow"
      Action = [
        "lambda:UpdateFunctionCode",
        "lambda:PublishVersion",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:GetFunctionCodeSigningConfig",
      ]
      Resource = aws_lambda_function.api.arn
    },
    # S3 — sync frontend build artefacts
    {
      Effect = "Allow"
      Action = [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.frontend.arn,
        "${aws_s3_bucket.frontend.arn}/*",
      ]
    },
    # CloudFront — invalidate the cache after a frontend deploy
    {
      Effect = "Allow"
      Action = [
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation",
      ]
      Resource = aws_cloudfront_distribution.frontend.arn
    },
  ]
}

resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "deploy-permissions"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = concat(local.github_actions_legacy_statements, local.github_actions_statements)
  })
}
