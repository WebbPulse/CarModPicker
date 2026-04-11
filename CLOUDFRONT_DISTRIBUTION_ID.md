# `CLOUDFRONT_DISTRIBUTION_ID` (GitHub Actions)

The **Frontend Deploy** workflow ([`.github/workflows/frontend-deploy.yml`](.github/workflows/frontend-deploy.yml)) can invalidate the CloudFront cache after syncing the SPA to S3. It reads a GitHub Actions **variable** named **`CLOUDFRONT_DISTRIBUTION_ID`** from the **`prod`** [environment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment).

## When to set it

1. After Terraform defines the CloudFront distribution (currently commented in [`terraform/cloudfront.tf`](terraform/cloudfront.tf) until ACM/DNS are ready), apply Terraform.
2. Copy the distribution ID from Terraform output `cloudfront_distribution_id` or from the AWS CloudFront console.
3. In the repo: **Settings → Environments → `prod` → Environment variables**, add **`CLOUDFRONT_DISTRIBUTION_ID`** with that value.

## If it is unset

The invalidation step is **skipped** (`if: vars.CLOUDFRONT_DISTRIBUTION_ID != ''`), so deploys still upload to S3; only cache invalidation is omitted.

## IAM

The GitHub OIDC deploy role needs `cloudfront:CreateInvalidation` on the distribution ARN. That statement is added in [`terraform/iam_github_actions.tf`](terraform/iam_github_actions.tf) when the CloudFront resource is uncommented and applied.
