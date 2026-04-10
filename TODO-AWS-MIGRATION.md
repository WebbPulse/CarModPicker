# AWS Migration TODO

## Context

CarModPicker is being migrated from Railway to native AWS. All Terraform and application code has been written but **nothing has been applied yet**. The goal is to keep costs low (~$21–29/month after year 1 free tiers).

**Current state of DNS:** Route53 still pointing `www` → Railway frontend, `api` → Railway backend. The new `route53.tf` already has the correct AWS records baked in — they take effect the moment `terraform apply` runs. Railway stays live until then.

**Repo:** https://github.com/Tylert2610/CarModPicker  
**Terraform Cloud:** HCP org `WebbPulseTerraform`, workspace `CarModPicker`

---

## Target Architecture

| Component | Service |
|-----------|---------|
| Frontend | S3 (`carmodpicker-prod-frontend`) + CloudFront → `www.carmodpicker.com` |
| Backend | App Runner (0.25 vCPU / 512 MB) → `api.carmodpicker.com` |
| Database | RDS PostgreSQL 16 `db.t4g.micro`, single-AZ, publicly accessible |
| Images | S3 `carmodpicker-prod-user-images` (private, IAM role access, presigned URLs) |
| Secrets | AWS Secrets Manager (5 secrets) |
| CD | GitHub Actions OIDC → ECR push + App Runner redeploy / S3 sync + CF invalidation |

No NAT Gateway. No ALB. App Runner has built-in TLS/LB.

---

## Phase 1 — Apply Infrastructure (no traffic impact)

### Step 1: Add HCP Terraform workspace variables

Go to HCP Terraform → workspace `CarModPicker` → Variables. Add these as **sensitive workspace variables**:

| Key | Type | Notes |
|-----|------|-------|
| `db_password` | terraform | Strong random password for RDS master user |
| `secret_key` | terraform | JWT signing key for FastAPI (generate with `openssl rand -hex 32`) |
| `sendgrid_api_key` | terraform | SendGrid API key |
| `sendgrid_verify_email_template_id` | terraform | SendGrid email verification template ID |
| `sendgrid_reset_password_template_id` | terraform | SendGrid password reset template ID |

### Step 2: Run `terraform apply`

This creates: ACM cert + Route53 validation records, VPC + subnets, RDS instance, ECR repo, Secrets Manager secrets.

**Important:** ACM cert validation is automatic (Route53 DNS). RDS takes ~5–10 min to provision.

After apply, note these outputs:
- `ecr_repository_url` — needed for Step 3
- `rds_endpoint` — needed for Step 4
- `cloudfront_distribution_id` — needed for Step 7
- `frontend_bucket` — needed for Step 7
- `app_runner_service_url` — testing endpoint before DNS cutover
- `github_actions_role_arn` — needed for Step 7

**Note:** App Runner and CloudFront are also created in this apply because all resources are in the same workspace. App Runner won't start successfully yet (no image in ECR).

---

## Phase 2 — Deploy Backend Container

### Step 3: Build and push the first Docker image

```bash
cd backend

# Authenticate to ECR (replace <ecr_url> with the ecr_repository_url output)
aws ecr get-login-password --region us-west-1 | \
  docker login --username AWS --password-stdin <ecr_url>

# Build and push
docker build -t <ecr_url>:latest .
docker push <ecr_url>:latest
```

### Step 4: Trigger App Runner deployment

```bash
aws apprunner start-deployment \
  --service-arn <app_runner_service_arn from console or terraform state>
```

Wait ~2 min for the service to start.

### Step 5: Run database migrations

```bash
cd backend
DATABASE_URL="postgresql://carmodpicker:<db_password>@<rds_endpoint>/carmodpicker?sslmode=require" \
  alembic upgrade head
```

**Note:** You may need to temporarily add your local IP to the RDS security group if it's locked down, or run from a machine with internet access (the security group allows 0.0.0.0/0 on 5432 by default from the Terraform config).

### Step 6: Smoke test backend

```bash
curl https://<app_runner_service_url>/health   # → {"status":"healthy",...}
curl https://<app_runner_service_url>/ready    # → {"status":"ready","database":"up"}
```

---

## Phase 3 — Deploy Frontend

### Step 7: Build and sync frontend to S3

```bash
cd frontend
npm run build  # output goes to dist/

# Sync to S3 (replace <frontend_bucket> with terraform output)
aws s3 sync dist/ s3://<frontend_bucket>/ --delete

# Invalidate CloudFront cache (replace <cf_distribution_id> with terraform output)
aws cloudfront create-invalidation \
  --distribution-id <cf_distribution_id> \
  --paths "/*"
```

### Step 8: Test at CloudFront default domain

```bash
curl https://<cloudfront_domain from terraform output>/
```

The SPA should load. The API calls will still hit Railway since DNS hasn't cut over yet.

---

## Phase 4 — DNS Cutover

The new `terraform/route53.tf` already has the correct records:
- `www.carmodpicker.com` → CloudFront alias (A record)
- `api.carmodpicker.com` → App Runner CNAME

**DNS cutover happened automatically when `terraform apply` ran in Phase 1** — the old Railway CNAME records were replaced in the same apply. If you want to stage this separately, you need to temporarily revert route53.tf to the Railway records for the first apply, then swap.

After the apply, verify:
```bash
curl https://www.carmodpicker.com    # → SPA
curl https://api.carmodpicker.com/health  # → {"status":"healthy",...}
curl https://api.carmodpicker.com/ready   # → {"status":"ready",...}
```

---

## Phase 5 — Wire Up GitHub Actions CD

### Step 9: Add GitHub Actions secrets

Go to GitHub → repo Settings → Secrets and variables → Actions. Add:

| Secret | Value |
|--------|-------|
| `AWS_DEPLOY_ROLE_ARN` | `github_actions_role_arn` terraform output |
| `ECR_REPOSITORY_NAME` | `carmodpicker-prod-backend` |
| `APP_RUNNER_SERVICE_ARN` | App Runner service ARN (from AWS console or `terraform state show aws_apprunner_service.backend`) |
| `FRONTEND_S3_BUCKET` | `carmodpicker-prod-frontend` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `cloudfront_distribution_id` terraform output |

After this, pushes to `main` that pass CI will automatically deploy.

---

## Phase 6 — Cleanup

1. Confirm stable operation for 1–2 weeks
2. Cancel Railway subscription (services: frontend, backend, PostgreSQL, storage bucket)
3. Remove Railway TXT verification records from `terraform/route53.tf`:
   - `_railway-verify.www.carmodpicker.com`
   - `_railway-verify.api.carmodpicker.com`
   (These were already removed in the current route53.tf — just confirm they're gone)

---

## Key Files Changed

| File | What changed |
|------|-------------|
| `terraform/providers.tf` | Added `us-east-1` provider alias (for ACM) |
| `terraform/variables.tf` | Added db/app/secrets variables |
| `terraform/s3.tf` | Added `user_images` + `frontend` buckets; removed old `assets` bucket |
| `terraform/route53.tf` | Replaced Railway CNAMEs with CloudFront alias + App Runner CNAME |
| `terraform/outputs.tf` | Added ECR URL, App Runner URL, RDS endpoint, CF domain/ID |
| `backend/Dockerfile` | Created — python:3.13-slim, Pillow deps, uvicorn |
| `backend/app/core/config.py` | `S3_ENDPOINT_URL` default changed from Railway URL to `""` |
| `backend/app/api/services/storage_service.py` | boto3 passes `None` for empty creds → falls back to IAM role |
| `.github/workflows/backend-deploy.yml` | New CD workflow (triggers after Backend CI) |
| `.github/workflows/frontend-deploy.yml` | New CD workflow (triggers after Frontend CI) |

**New terraform files:** `vpc.tf`, `rds.tf`, `secretsmanager.tf`, `ecr.tf`, `acm.tf`, `apprunner.tf`, `cloudfront.tf`, `iam_github_actions.tf`

---

## Known Gotchas

- **`RAILWAY_ENVIRONMENT=production`** is set as a plain env var on App Runner in `apprunner.tf` — the backend uses this to determine `is_production`. Do not remove it.
- **RDS is publicly accessible** (`publicly_accessible = true`) with port 5432 open to 0.0.0.0/0. This is intentional (no NAT gateway = no VPC connector for App Runner). Secured by strong password + `sslmode=require` in connection string.
- **`aws_s3_bucket.assets` was renamed to `aws_s3_bucket.user_images`** — if there's existing Terraform state with the old resource name, you'll need to `terraform state mv aws_s3_bucket.assets aws_s3_bucket.user_images` before applying to avoid destroying and recreating the bucket.
- **App Runner custom domain validation**: `aws_apprunner_custom_domain_association` creates DNS records automatically via `route53.tf`. App Runner may take a few minutes to activate the custom domain after DNS propagates.
- **Frontend build needs `VITE_PROD_API_URL`** set to `https://api.carmodpicker.com` when building for production. This is already set in `frontend-deploy.yml`.
