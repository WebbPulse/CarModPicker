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
    Statement = [{
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
          "token.actions.githubusercontent.com:sub" = "repo:Tylert2610/CarModPicker:*"
        }
      }
    }]
  })
}

# NOTE: CloudFront statement uses a placeholder ARN until aws_cloudfront_distribution.frontend
# is uncommented in cloudfront.tf. Update the Resource to the real distribution ARN after that apply.
resource "aws_iam_role_policy" "github_actions_deploy" {
  name = "deploy-permissions"
  role = aws_iam_role.github_actions_deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
        Resource = aws_ecr_repository.backend.arn
      },
      # App Runner — trigger redeployment after new image is pushed
      {
        Effect   = "Allow"
        Action   = ["apprunner:StartDeployment"]
        Resource = aws_apprunner_service.backend.arn
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
      # BLOCKED: aws_cloudfront_distribution.frontend not yet deployed.
      # Uncomment cloudfront.tf, apply, then this reference will resolve.
      # For now this statement is omitted; re-apply after CloudFront exists.
    ]
  })
}
