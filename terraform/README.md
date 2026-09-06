# Terraform — CarModPicker AWS Infrastructure

Terraform configuration for the CarModPicker AWS stack. One root module, two HCP Terraform workspaces:

| Workspace | AWS account | VCS branch | `environment` | `staging_profile` |
| --- | --- | --- | --- | --- |
| `CarModPicker` | 734702670403 | `main` | `production` | — |
| `CarModPicker-staging` | 748861776298 | `staging` | `staging` | `full` (intended), `reduced` (fallback) |

State lives in HCP Terraform; applies are triggered by pushing to the bound branch. Production is manual-apply.

## Architecture at a glance

```
                  ┌────────────────────────────────────────┐
Route53 ──┐       │              CloudFront                │
          ├──── www.carmodpicker.com ──▶  S3 (frontend)    │
          │       │  + uri_rewrite CloudFront Function     │
          │       └────────────────────────────────────────┘
          │
          ├──── carmodpicker.com ──▶ S3 website redirect ──▶ www
          │
          └──── api.carmodpicker.com ──┬──▶ HTTP API ──▶ Lambda (app.lambda_handler) ──▶ DynamoDB
                     (api_target)      │                    ├──▶ Secrets Manager (<prefix>/app)
                                       │                    ├──▶ S3 (user images)
                                       │                    └──▶ SES
                                       │
                                       └──▶ App Runner ──▶ RDS PostgreSQL 16   (legacy, production only)
```

Single-region deployment in `us-west-2`. The CloudFront cert lives in `us-east-1` via the `aws.us_east_1` provider alias; the HTTP API cert is regional. Staging serves the same shape one label down: `staging.carmodpicker.com`, `www.staging.carmodpicker.com`, `api.staging.carmodpicker.com`, from a child zone it owns and that the parent zone delegates to (see "Staging profiles").

## Environment shaping

Six inputs decide what a workspace builds. Every other resource is unconditional.

| Variable | Default | Effect |
| --- | --- | --- |
| `legacy_stack_enabled` | `null` → `true` in production, always `false` in staging | Builds VPC, RDS, ECR, App Runner, their secrets, log groups and alarms. `local.legacy_stack` can never be true outside production, so staging cannot create RDS or App Runner whatever the variable says. |
| `api_target` | `null` → `legacy` while `local.legacy_stack` is true, `lambda` otherwise | Which backend `api.<domain>` resolves to when a custom domain exists: `legacy` = CNAME to App Runner, `lambda` = alias to the HTTP API domain. Ignored when there is no custom domain. Staging can never run the legacy stack, so it always resolves to `lambda`. |
| `custom_domain_enabled` | `null` → `true` in production or when `staging_profile = full` | Hosted zone, ACM certs, custom-domain records, SES domain identity, CloudFront aliases, HTTP API domain name. |
| `domain_name` | `carmodpicker.com` | Registered apex. `local.domain_name` is the domain actually served: `domain_name` in production, `staging.<domain_name>` in staging. Every hostname, the hosted zone, the ACM certs, the SES identity and the CloudFront apex→www redirect derive from it. |
| `parent_route53_zone_id` | `null` | Staging only: hosted zone id of `domain_name` in the production account, where the NS delegation for `staging.<domain_name>` is written. Required when staging has a custom domain. |
| `route53_write_role_arn` | `null` | Staging only: role in the production account, scoped to that one NS record, assumed by the `aws.parent_dns` provider alias. Required when staging has a custom domain. |
| `email_from` | `null` → `no-reply@<served domain>` with a custom domain, `no-reply@<domain_name>` without | Sender address for transactional mail; must belong to the SES identity the environment verifies. |

`db_password` is optional; a precondition on the RDS instance rejects a null value only when the legacy stack is enabled.

### Staging profiles

`staging_profile` is `reduced` or `full` (`none` is rejected — a staging workspace with nothing in it should not exist).

- **`full`** (intended): everything `reduced` builds plus real DNS. The staging account owns a hosted zone for `staging.carmodpicker.com`; in the same apply the `aws.parent_dns` provider assumes `route53_write_role_arn` in the production account and writes the `NS` delegation for `staging.carmodpicker.com` into `parent_route53_zone_id` (the `carmodpicker.com` zone owned by the production workspace). Both ACM validations `depends_on` that record so validation does not start before the child zone is reachable. Hostnames: `staging.carmodpicker.com` (CloudFront alias, 301 → www), `www.staging.carmodpicker.com` (SPA), `api.staging.carmodpicker.com` (HTTP API custom domain), `bounce.staging.carmodpicker.com` (SES MAIL FROM). SES uses the domain identity exactly as production does; `email_from` defaults to `no-reply@staging.carmodpicker.com`. Both variables are pushed to the workspace by WebbPulse-Platform; until they are, the profile must stay `reduced`.
- **`reduced`** (fallback): DynamoDB + Lambda + HTTP API + CloudFront + S3 + SES, no custom domain. The frontend is served from the CloudFront hostname, the API from the `execute-api` endpoint, and SES sends from a mailbox identity (`email_from`, defaulting to `no-reply@carmodpicker.com`) instead of a domain identity. Outputs `frontend_url` and `api_url` carry the generated hostnames.

Switching `reduced` → `full` changes `frontend_url` and `api_url`, so `VITE_API_URL` on the `staging` GitHub Environment has to be re-copied from `api_url` afterwards.

### Production cutover

Production runs both stacks until the Lambda path is proven:

1. Apply with defaults. The legacy stack is untouched (every gated resource has a `moved` block so nothing is recreated); DynamoDB, Lambda, the HTTP API and `api.carmodpicker.com` on API Gateway are created alongside it. DNS still points at App Runner.
2. Deploy the backend so the Lambda holds real code (the Terraform-managed zip is a 503 placeholder), then copy the data with `backend/scripts/backfill_from_postgres.py` (`--dry-run` first, then a real run with `--verify`; it is idempotent, so it can be re-run right before the DNS flip to pick up late writes).
3. Set `api_target = lambda`. The Route53 `api` record flips from the App Runner CNAME to the HTTP API alias. Set it back to `legacy` to roll back.
4. Set `rds_deletion_protection = false` and apply, so the instance can be destroyed (the final snapshot `carmodpicker-production-final-snapshot` is still taken).
5. Set `legacy_stack_enabled = false` to destroy VPC, RDS, ECR and App Runner. `api_target` can be unset at the same time: with the legacy stack off it defaults to `lambda`. Unset `APP_RUNNER_SERVICE_ARN` on the `production` GitHub Environment at the same time so the deploy workflow stops building images.

## File map

| File | What it manages |
| --- | --- |
| `versions.tf` | Terraform version pin, AWS + archive provider versions, HCP Terraform cloud block (production workspace; the staging workspace overrides it). |
| `providers.tf` | Default `aws` provider, `aws.us_east_1` alias (CloudFront certs), `aws.parent_dns` alias that assumes `route53_write_role_arn` when set (staging NS delegation). |
| `variables.tf` | Input variables: region, environment, shaping toggles above, throttling, secrets. |
| `locals.tf` | `project`, `prefix` (`carmodpicker-<env>`), `legacy_stack`, `custom_domain`, `domain_name` (served domain), `active_domain` (served domain, or the apex when no custom domain is bound), `parent_delegation`, `email_from`, `frontend_url`, `api_url`, `allowed_origins`. |
| `data.tf` | `aws_caller_identity`, `aws_region` lookups for ARN construction. |
| `outputs.tf` | API/Lambda/DynamoDB/CloudFront identifiers plus everything the deploy workflows need. Legacy outputs are `null` when the stack is off. |
| `dynamodb.tf` | One `aws_dynamodb_table` per entry in `dynamodb_tables.json`, on-demand billing, PITR + deletion protection in production. |
| `dynamodb_tables.json` | Generated from `backend/app/db/dynamo/tables.py` by `backend/scripts/export_dynamo_tables.py`; a backend test fails when it is stale. |
| `lambda.tf` | Execution role (DynamoDB on `<prefix>-*`, SES, user-images S3, app secret, logs, X-Ray), log group, placeholder zip, the `<prefix>-api` function. |
| `lambda_placeholder/` | Source of the placeholder zip Terraform uploads on first create; code changes are ignored afterwards so the deploy workflow owns them. |
| `apigateway.tf` | HTTP API with a `$default` Lambda proxy route, `$default` stage with throttling + JSON access logs, invoke permission, custom domain + mapping when `local.custom_domain`. |
| `vpc.tf` | Legacy: VPC, IGW, two public subnets in AZs a/b, public route table. |
| `rds.tf` | Legacy: PostgreSQL 16 `db.t4g.micro`, subnet group, SG, PI, CW log exports. |
| `ecr.tf` | Legacy: backend image repo + lifecycle policy. |
| `apprunner.tf` | Legacy: access role, instance role, auto-scaling config, App Runner service, custom domain association. |
| `s3.tf` | `user-images` (private), `crawl-data` (private), `lambda-artifacts` (versioned, 30-day noncurrent expiry), `frontend` (private + OAC). |
| `cloudfront.tf` | Distribution for the frontend, managed cache/origin/headers policies, SPA 403/404 fallback. Aliases and the ACM cert apply only with a custom domain. |
| `cloudfront_function.tf` | Viewer-request function, rendered from `cloudfront_functions/uri_rewrite.js.tftpl` with the served domain: apex → www 301 and `/foo` → `/foo/index.html` rewrite for prerendered routes. |
| `acm.tf` | Wildcard cert for the served domain in `us-east-1` (CloudFront) and a regional cert for `api.<domain>` (HTTP API), both DNS-validated; validation waits on the staging delegation record. |
| `route53.tf` | Hosted zone for the served domain, staging NS delegation into the parent zone (`aws.parent_dns`), apex/`www`/`api` records, SES DKIM/MAIL-FROM/DMARC, App Runner validation records. `api` is a CNAME to App Runner or an alias to the HTTP API depending on `api_target`. |
| `ses.tf` | SESv2 configuration set, domain identity (custom domain) or mailbox identity (`email_from`), custom MAIL FROM, SNS topic + subscription for bounces/complaints, account-level VDM. |
| `secretsmanager.tf` | `<prefix>/app` JSON secret (`SECRET_KEY`, `SENTRY_DSN`) read by the Lambda at import; `secret-key` / `sentry-dsn` / `database-url` (legacy) for App Runner. |
| `iam_github_actions.tf` | GitHub OIDC provider + `github-actions-deploy` role: Lambda code updates, artifacts upload, frontend sync, invalidation; ECR + App Runner only while the legacy stack exists. |
| `monitoring.tf` | Alarms SNS topic; Lambda errors/throttles, HTTP API 5xx and p99 integration latency, per-table DynamoDB throttle events; legacy App Runner + RDS log groups and alarms. |
| `management.tf` | Tag-based Resource Group, Cost Explorer anomaly monitor + daily email subscription, monthly cost budgets. |

## Conventions

- **Naming**: every resource name starts with `local.prefix` = `carmodpicker-<environment>`.
- **Tags**: `Project`, `Environment`, `ManagedBy=terraform` applied globally via provider `default_tags`.
- **Secrets**: values flow HCP workspace variable → `var.*` → Secrets Manager. The Lambda reads `<prefix>/app` at import time through `APP_SECRETS_ARN` (`backend/app/core/secrets.py`); App Runner reads the per-value secrets via `runtime_environment_secrets`. No secret values live in Terraform state outputs or version control.
- **Lambda code is not Terraform's**: the function is created with a placeholder and `ignore_changes` on the package attributes. `backend-deploy.yml` uploads the real zip to `<prefix>-lambda-artifacts` and calls `update-function-code`.
- **No NAT Gateway**: the Lambda is not in a VPC; the legacy RDS is publicly accessible (secured by SSL + strong password).

## HCP workspace variables

Set per workspace, not in `.tfvars`:

- `environment` and `staging_profile` — pushed from the WebbPulse-Platform repo.
- `parent_route53_zone_id` and `route53_write_role_arn` — staging only, pushed from the WebbPulse-Platform repo; required once the profile is `full`.
- `secret_key`, `sentry_dsn` — sensitive, set by hand.
- `db_password` — sensitive, production only (legacy RDS).
- `legacy_stack_enabled`, `rds_deletion_protection`, `api_target`, `custom_domain_enabled`, `domain_name`, `email_from` — optional, see above.

AWS credentials are injected automatically via HCP Terraform dynamic provider credentials (no static keys).

## GitHub Environments

The deploy workflows select the `production` or `staging` GitHub Environment from the branch and read every value from it. Populate each from this workspace's outputs:

| Variable | Output |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | `github_actions_role_arn` |
| `TFC_WORKSPACE_ID` | HCP workspace id (`ws-…`) |
| `LAMBDA_FUNCTION_NAME` | `lambda_function_name` |
| `LAMBDA_ARTIFACTS_BUCKET` | `lambda_artifacts_bucket` |
| `FRONTEND_S3_BUCKET` | `frontend_bucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `cloudfront_distribution_id` |
| `VITE_API_URL` | `api_url` (`https://api.carmodpicker.com` / `https://api.staging.carmodpicker.com` with a custom domain, the `execute-api` endpoint without) |
| `CWS_EXTENSION_ID` | Chrome Web Store extension id |
| `ECR_REPOSITORY_NAME`, `APP_RUNNER_SERVICE_ARN` | production only, from `ecr_repository_url` / `app_runner_service_arn`; remove with the legacy stack |

Secret: `TFC_API_TOKEN`.

## Local validation

```bash
terraform fmt -check -recursive terraform/
cd terraform && terraform init -backend=false && terraform validate
```

`terraform plan` runs in HCP on push; the local checkout has no credentials and should not need any.

## Destroy / teardown notes

- RDS has `deletion_protection = true`. To tear it down: set to `false`, apply, then destroy.
- DynamoDB tables have `deletion_protection_enabled = true` in production.
- ECR has `force_delete = true` so image churn doesn't block destroy.
- `final_snapshot_identifier` is set on RDS — destroy will create a snapshot named `carmodpicker-<env>-final-snapshot`.
- Secrets use `recovery_window_in_days = 0` for immediate deletion.

## Bootstrap: Sentry

Sentry DSN provisioning is out-of-band (Terraform cannot create Sentry projects):

1. Create the Sentry project in the Sentry dashboard.
2. Set `sentry_dsn` on the HCP workspace; the next apply writes it into `<prefix>/app` and `<prefix>/sentry-dsn`.
3. Add frontend Sentry secrets to GitHub Actions: `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`.
4. Redeploy so the new value is picked up.

Until step 2 completes, the Sentry SDK `init_sentry()` helper no-ops gracefully (env-gate handles empty DSN).
