# Terraform — CarModPicker AWS Infrastructure

Terraform configuration for the CarModPicker production AWS stack. State is managed in **HCP Terraform**; applies are triggered by pushing to `main`.

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
          └──── api.carmodpicker.com ──▶ App Runner ──▶ RDS PostgreSQL 16
                                          │              (publicly accessible,
                                          │               SSL + auth)
                                          ├──▶ Secrets Manager
                                          ├──▶ S3 (user images, page archive)
                                          └──▶ SES (carmodpicker.com)
```

Single-region deployment in `us-west-2`. ACM certs for CloudFront live in `us-east-1` via the `aws.us_east_1` provider alias.

## File map

| File | What it manages |
| --- | --- |
| `versions.tf` | Terraform version pin, AWS provider version, HCP Terraform cloud block. |
| `providers.tf` | Default `aws` provider + `aws.us_east_1` alias (CloudFront certs). |
| `variables.tf` | Input variables (region, env, DB password, secrets). |
| `locals.tf` | `project`, `prefix` (`carmodpicker-<env>`), `common_tags`. |
| `data.tf` | `aws_caller_identity`, `aws_region` lookups for ARN construction. |
| `outputs.tf` | ECR URL, App Runner URL, CloudFront domain/ID, GitHub Actions role ARN, etc. |
| `vpc.tf` | VPC, IGW, two public subnets in AZs a/b, public route table. |
| `rds.tf` | PostgreSQL 16 `db.t4g.micro`, subnet group, SG (0.0.0.0/0 on 5432 — secured by SSL+auth), PI, CW log exports. |
| `ecr.tf` | Backend image repo + lifecycle policy. |
| `apprunner.tf` | Access role, instance role (Secrets/S3/SES IAM), auto-scaling config, App Runner service, custom domain association for `api.carmodpicker.com`. |
| `s3.tf` | `user-images` (private), `crawl-data` (chrome-extension page archive, private), `frontend` (private + OAC), `carmodpicker.com` (apex website redirect). |
| `cloudfront.tf` | Distribution for `www.carmodpicker.com`, managed cache/origin/headers policies, SPA 403/404 fallback to `/index.html`. |
| `cloudfront_function.tf` | Viewer-request function that rewrites `/foo` → `/foo/index.html` for prerendered routes. |
| `cloudfront_functions/uri_rewrite.js` | The function source. |
| `acm.tf` | Wildcard cert for `carmodpicker.com` in `us-east-1` with DNS validation. |
| `route53.tf` | Hosted zone, apex A→S3 redirect, `www` A→CloudFront, `api` CNAME→App Runner, SES DKIM/MAIL-FROM/DMARC, App Runner custom-domain validation records. |
| `ses.tf` | SESv2 configuration set, domain identity, custom MAIL FROM, SNS topic + subscription for bounces/complaints, account-level VDM. |
| `secretsmanager.tf` | `database-url` (assembled from RDS), `secret-key` (JWT), `sentry-dsn`. |
| `iam_github_actions.tf` | GitHub OIDC provider + `github-actions-deploy` role. |
| `monitoring.tf` | Alarms SNS topic, pre-created CW log groups for App Runner + RDS, CloudWatch alarms (App Runner 5xx, RDS CPU/storage/connections/memory). |
| `management.tf` | AppRegistry application + attribute group, Resource Group, Cost Anomaly Detection, Budgets. |

## Conventions

- **Naming**: every resource name starts with `local.prefix` = `carmodpicker-<environment>`.
- **Tags**: `Project`, `Environment`, `ManagedBy=terraform` applied globally via provider `default_tags`.
- **Secrets**: values flow HCP workspace variable → `var.*` → Secrets Manager → App Runner env via `runtime_environment_secrets`. No secret values live in Terraform state or version control.
- **No NAT Gateway**: RDS is publicly accessible (secured by SSL + strong password). App Runner uses AWS-managed egress.

## HCP workspace variables

Sensitive variables set in the HCP Terraform workspace (not in `.tfvars`):

- `db_password` — RDS master password
- `secret_key` — FastAPI JWT signing key

AWS credentials are injected automatically via HCP Terraform dynamic provider credentials (no static keys).

## Apply workflow

```bash
terraform fmt -recursive
terraform validate

git commit -am "terraform: <change>"
git push origin main
# → HCP Terraform runs plan → review/apply in the UI
```

## Destroy / teardown notes

- RDS has `deletion_protection = true`. To tear it down: set to `false`, apply, then destroy.
- ECR has `force_delete = true` so image churn doesn't block destroy.
- `final_snapshot_identifier` is set on RDS — destroy will create a snapshot named `carmodpicker-<env>-final-snapshot`.
- Secrets use `recovery_window_in_days = 0` for immediate deletion.

## Bootstrap: Sentry

Sentry DSN provisioning is out-of-band (Terraform cannot create Sentry projects — only AWS Secrets Manager scaffolding):

1. Create Sentry project in the Sentry dashboard.
2. `terraform apply` to create the empty `${prefix}/sentry-dsn` Secrets Manager secret.
3. Populate the value:
   ```
   aws secretsmanager put-secret-value \
     --secret-id "${prefix}/sentry-dsn" \
     --secret-string "https://<public-key>@<org>.ingest.sentry.io/<project-id>"
   ```
4. Add frontend Sentry secrets to GitHub Actions: `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`.
5. Redeploy so the new env value is picked up.

Until step 3 completes, the Sentry SDK `init_sentry()` helper no-ops gracefully (env-gate handles empty DSN).
