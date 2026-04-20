# Terraform — CarModPicker AWS Infrastructure

Terraform configuration for the CarModPicker production AWS stack. State is managed in **HCP Terraform** (`WebbPulseTerraform/CarModPicker`); applies are triggered by pushing to `main` on `WebbPulse/CarModPicker` and approved in the TFC UI.

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
                                          ├──▶ S3 (user images, crawl data)
                                          ├──▶ SES (carmodpicker.com)
                                          └──▶ ECS Fargate (on-demand crawler tasks)
                                                   ▲
                                                   │
                          EventBridge Scheduler ──▶│ (per-adapter crons managed
                           ──▶ Event Bus ──▶ Rule ─│  by the backend reconciler
                           ──▶ API Destination ────┘  via boto3, NOT terraform)
```

Single-region deployment in `us-west-2`. ACM certs for CloudFront live in `us-east-1` via the `aws.us_east_1` provider alias.

## File map

| File | What it manages |
| --- | --- |
| `versions.tf` | Terraform version pin, AWS provider version, HCP Terraform cloud block. |
| `providers.tf` | Default `aws` provider + `aws.us_east_1` alias (CloudFront certs). |
| `variables.tf` | Input variables (region, env, DB password, secrets, crawler compute, FlareSolverr). |
| `locals.tf` | `project`, `prefix` (`carmodpicker-<env>`), `common_tags`. |
| `data.tf` | `aws_caller_identity`, `aws_region` lookups for ARN construction. |
| `outputs.tf` | ECR URL, App Runner URL, CloudFront domain/ID, GitHub Actions role ARN, etc. |
| `vpc.tf` | VPC, IGW, two public subnets in AZs a/b, public route table. |
| `rds.tf` | PostgreSQL 16 `db.t4g.micro`, subnet group, SG (0.0.0.0/0 on 5432 — secured by SSL+auth), PI, CW log exports. |
| `ecr.tf` | Backend image repo + lifecycle policy (untagged 1d, keep last 3 tagged). |
| `apprunner.tf` | Access role, instance role (Secrets/S3/SES/ECS/Scheduler IAM), auto-scaling config, App Runner service, custom domain association for `api.carmodpicker.com`. |
| `ecs.tf` | Fargate-only cluster, task/execution roles, SG, log group, task definition for on-demand crawler runs (image shared with App Runner). |
| `scheduler.tf` | EventBridge Connection (X-Admin-Cron-Key), API Destination, Event Bus rule + target, IAM roles for scheduler→bus and bus→API destination. Per-adapter schedules themselves are created by the backend. |
| `s3.tf` | `user-images` (private), `crawl-data` (private), `frontend` (private + OAC), `carmodpicker.com` (apex website redirect). |
| `cloudfront.tf` | Distribution for `www.carmodpicker.com`, managed cache/origin/headers policies, SPA 403/404 fallback to `/index.html`. |
| `cloudfront_function.tf` | Viewer-request function that rewrites `/foo` → `/foo/index.html` for prerendered routes. |
| `cloudfront_functions/uri_rewrite.js` | The function source. |
| `acm.tf` | Wildcard cert for `carmodpicker.com` in `us-east-1` with DNS validation. |
| `route53.tf` | Hosted zone, apex A→S3 redirect, `www` A→CloudFront, `api` CNAME→App Runner, SES DKIM/MAIL-FROM/DMARC, App Runner custom-domain validation records, Google Search Console TXT. |
| `ses.tf` | SESv2 configuration set, domain identity, custom MAIL FROM, SNS topic + subscription for bounces/complaints, account-level VDM. |
| `secretsmanager.tf` | `database-url` (assembled from RDS), `secret-key` (JWT), `cron-secret-key` (EventBridge→App Runner auth). |
| `iam_github_actions.tf` | GitHub OIDC provider + `github-actions-deploy` role (ECR push, App Runner deploy, S3 sync, CloudFront invalidation). Accepts both `WebbPulse/CarModPicker` and `Tylert2610/CarModPicker` subs. |
| `monitoring.tf` | Alarms SNS topic, pre-created CW log groups (14-day retention) for App Runner + RDS, 5 CloudWatch alarms (App Runner 5xx, RDS CPU/storage/connections/memory). |
| `management.tf` | AppRegistry application + attribute group, Resource Group, Cost Anomaly Detection, two Budgets ($30 warn / $60 critical), tag-sync role extras. |

## Conventions

- **Naming**: every resource name starts with `local.prefix` = `carmodpicker-<environment>` (e.g. `carmodpicker-production-backend`).
- **Tags**: `Project`, `Environment`, `ManagedBy=terraform` applied globally via provider `default_tags`. Inline `Name` tags are layered on top where they help the console.
- **Secrets**: values flow HCP workspace variable → `var.*` → Secrets Manager → App Runner/ECS env via `runtime_environment_secrets` / `secrets`. No secret values live in Terraform state or version control.
- **No NAT Gateway**: RDS is publicly accessible (secured by SSL + strong password), ECS tasks run in public subnets with assigned public IPs. App Runner uses AWS-managed egress.
- **Dynamic schedules**: per-adapter crawler schedules are reconciled by the backend (`app/api/services/adapter_schedule_service.py`) against the `adapter_schedules` DB table, not Terraform. Terraform only provisions the shared Target plumbing (Connection, API Destination, Event Bus rule, IAM role the schedules pass to AWS).

## HCP workspace variables

Sensitive variables set in the HCP Terraform workspace (not in `.tfvars`):

- `db_password` — RDS master password
- `secret_key` — FastAPI JWT signing key
- `cron_secret_key` — shared with `CRON_SECRET_KEY` in App Runner; authenticates EventBridge → admin endpoint invocations

AWS credentials are injected automatically via HCP Terraform dynamic provider credentials (no static keys).

## Apply workflow

```bash
# Local validation
terraform fmt -recursive
terraform validate

# Apply is git-driven — commit and push
git commit -am "terraform: <change>"
git push origin main
# → HCP Terraform runs plan → review/apply in the UI
```

Plan-only against an open branch also triggers in HCP on push.

## Two-stage flows

A few resources require a plan/apply cycle to learn values before a downstream resource can reference them. These are flagged with `NOTE:` comments in the source:

1. **App Runner custom domain** (`apprunner.tf` + `route53.tf`)
   - Stage 1: create `aws_apprunner_custom_domain_association.api` → AWS emits certificate validation records.
   - Stage 2: the `aws_route53_record.apprunner_validation` block (count=2) picks those records up on the next apply and publishes the CNAMEs.

2. **ACM → CloudFront → S3 policy → www DNS** (acm.tf → cloudfront.tf → s3.tf → route53.tf)
   - Cert must reach `ISSUED` before CloudFront will accept it; CloudFront ARN must exist before the S3 bucket policy condition resolves; distribution domain must exist before the `www` alias record does. Normal `depends_on` handles ordering inside a single apply, but if any earlier stage is replaced, downstream resources will replan.

## Destroy / teardown notes

- RDS has `deletion_protection = true`. To tear it down: set to `false`, apply, then destroy.
- ECR has `force_delete = true` so image churn doesn't block destroy.
- `final_snapshot_identifier` is set on RDS — destroy will create a snapshot named `carmodpicker-<env>-final-snapshot`.
- Secrets use `recovery_window_in_days = 0` for immediate deletion (no 30-day grace period).

## See also

- `backend/app/crawlers/README.md` — FlareSolverr deployment and FETCHER_TIER details referenced by the scheduler/ECS config.
- `backend/app/api/services/adapter_schedule_service.py` — reconciler that manages `aws_scheduler_schedule` resources outside Terraform.
- Root `CLAUDE.md` — stack overview and dev commands.
