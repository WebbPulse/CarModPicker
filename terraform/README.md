# Terraform: CarModPicker AWS Infrastructure

One root module, applied by two HCP Terraform workspaces in the `WebbPulse` organization:

| Workspace | AWS account | VCS branch | `environment` | `staging_profile` |
| --- | --- | --- | --- | --- |
| `CarModPicker` | 734702670403 | `main` | `production` | n/a |
| `CarModPicker-staging` | 748861776298 | `staging` | `staging` | `full` or `reduced` |

The `cloud` block in `versions.tf` names `CarModPicker`; the staging workspace overrides it.
State lives in HCP Terraform and AWS credentials come from HCP dynamic provider credentials, so the local checkout needs none.

**Manual apply is the real gate on production.** A merge to `main` cannot change AWS by itself: it queues a run, and someone has to confirm the apply.

## What this builds

Single region, `us-west-2`. Route 53 and ACM for the served domain, CloudFront and S3 for the SPA, an HTTP API in front of nine per-domain Lambda container images plus stream consumers, DynamoDB tables, SQS queues, S3 for user images and crawl data, SES, Secrets Manager, CloudWatch alarms and X-Ray Transaction Search. The CloudFront certificate is issued in `us-east-1` through the `aws.us_east_1` alias; the API certificate is regional. There is no VPC and no NAT Gateway.

Most of the stack comes from `app.terraform.io/WebbPulse/platform-modules/aws` submodules: `staging-dns`, `http-api`, `staging-access-gate`, `spa-frontend`, `ecr-repository`, `lambda-function`, `app-secrets`, `identity` and `github-actions-role`. Hand written is what a single-provider module cannot own: the ACM certificates, the CloudFront Function, and the SES records.

## File map

Flat root module; file names say what they own. The ones worth knowing before you read anything else:

- `lambda_domains.tf`: the nine domain functions, `media`, `build-logs`, `moderation`, `vehicles`, `admin`, `build-lists`, `identity`, `catalog` and `users`, plus `var.bootstrap_image_tag` and a runtime IAM policy each. `lambda_stream_consumers.tf` adds the stream and work-queue consumers, each running its domain's image with a different `command`, so one deploy call updates both.
- `apigateway.tf`: `module "api"`, explicit per-domain proxy route keys with `default_integration = null`, so an unmatched path is a gateway 404 rather than falling through.
- `dynamodb_tables.json`: generated from `backend/app/db/dynamo/tables.py` by `backend/scripts/export_dynamo_tables.py`. Edit the Python, not the JSON; a backend test fails when the two drift. Four tables carry `NEW_AND_OLD_IMAGES` streams: `users`, `parts`, `votes`, `part_listings`.
- `outputs.tf`: everything the deploy workflows read, mapped below.

## Staging profiles

`staging_profile` is `reduced` or `full`. `none` is rejected by a variable validation: a staging workspace with nothing in it should not exist.

- **`full`** (intended): everything `reduced` builds plus real DNS, served as `staging.carmodpicker.com`, `www.staging.carmodpicker.com` and `api.staging.carmodpicker.com`. The staging account owns the child hosted zone, and the same apply writes its `NS` delegation into the parent zone in the production account through the `aws.parent_dns` alias, which assumes `route53_write_role_arn` and targets `parent_route53_zone_id`. SES uses the domain identity exactly as production does.
- **`reduced`** (fallback while those two variables are absent): no custom domain. The frontend is served from the CloudFront hostname, the API from the `execute-api` endpoint, and SES sends from a mailbox identity.

Switching `reduced` to `full` changes `frontend_url` and `api_url`, so `VITE_API_URL` on the `staging` GitHub Environment has to be re-copied from `frontend_api_base_url` afterwards.

### Staging access gate

When `staging_access_gate = true` and the profile is `full`, `staging_access_gate.tf` instantiates the `staging-access-gate` submodule, every edit gated so the production plan is a no-op. CloudFront gains the gate's login origin, `trusted_key_groups` on the default behavior and ordered behaviors for `/_auth/*` and `/index.html`. The HTTP API sets `disable_execute_api_endpoint = true` and puts the gate's REQUEST authorizer on its routes: it admits an `OPTIONS` preflight, a request carrying the `x-origin-verify` header, or a browser request carrying the gate's signed cookies, and 401s everything else. The deploy role gets `ssm:GetParameter` on `/carmodpicker-staging/access-gate/origin-verify`, for any pipeline step that must call the API directly. Outputs: `staging_access_gate_hosted_ui`, `staging_access_gate_user_pool_id`.

## Production cutover

Production was cut over from App Runner + RDS PostgreSQL to Lambda + DynamoDB on 2026-09-06, and the legacy VPC, RDS, ECR and App Runner resources were destroyed.

## HCP workspace variables

Set per workspace, not in `.tfvars`.

| Variable | Notes |
| --- | --- |
| `environment`, `staging_profile` | Pushed from the WebbPulse-Platform repo. |
| `parent_route53_zone_id`, `route53_write_role_arn` | Staging only, pushed from WebbPulse-Platform. A variable validation requires both once staging has a custom domain. |
| `staging_access_gate`, `staging_access_users` | Staging only, pushed from WebbPulse-Platform. |
| `secret_key` | Sensitive, set by hand. Lands in the `<prefix>/app` JSON as `SECRET_KEY`. |
| `oauth_google_client_secret`, `oauth_github_client_secret` | Sensitive, set by hand. Land in the same JSON secret; the matching client ids are non-sensitive variables. |
| `extension_api_key` | Sensitive, set by hand. Lands in the `<prefix>/app` JSON as `EXTENSION_API_KEY`, the shared secret `POST /api/parts/price-history` accepts in the `X-API-Key` header. Leaving it unset is a supported state: that route then accepts admin bearer tokens only. |
| `bootstrap_image_tag` | The `sha-<40 hex>` seed tag every image function is created from. Defaults to `""`, which resolves the function and route maps to empty so a fresh account can apply once with no images in ECR. See the gotcha below. |
| `adopt_spans_log_group` | Whether to import the reserved `aws/spans` log group. Defaults to `true`. See the gotcha below. |
| `custom_domain_enabled`, `domain_name`, `email_from` | Optional shaping overrides. |

## GitHub Environment variables and their outputs

The deploy workflows select the `production` or `staging` GitHub Environment from the branch and read every deploy-time value from it. Populate each from the matching workspace's outputs.

| Variable | Output |
| --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | `github_actions_role_arn` |
| `FRONTEND_S3_BUCKET` | `frontend_bucket` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `cloudfront_distribution_id` |
| `VITE_API_URL` | `frontend_api_base_url` |
| `CWS_EXTENSION_ID` | Chrome Web Store extension id, not a Terraform output |

`CI_AWS_ROLE_ARN` is repository-scoped rather than environment-scoped, because a `pull_request` job cannot read an Environment whose deployment branch policy admits only `main` and `staging`. Take the **staging** workspace's `github_actions_ci_role_arn`. That role holds read-only CodeArtifact access and `sts:GetServiceBearerToken` and nothing else, so pull request CI can mint a token for the private `webbpulse` and `@webbpulse/*` packages without being able to deploy.

Other hostname-bearing outputs worth knowing: `api_url`, `frontend_url`, `domain_name`, `route53_zone_id`, `route53_zone_name_servers`.

## Gotchas

- **An API Gateway route key cannot end in a slash.** The plan is green and the apply fails with a `BadRequestException`. The gateway does not normalise a trailing slash away for you at declaration time.
- **A path part is either a whole variable or a literal, never a variable embedded in a literal.** `GET /sitemap-{name}.xml` plans green and fails the apply the same way, which is why `local.sitemap_child_names` in `apigateway.tf` spells out one literal route key per child sitemap. A fifth child sitemap needs its name added there or it 404s at the gateway while still working on a direct invoke.
- **`aws/spans` is a reserved log group name.** `CreateLogGroup` rejects names beginning with `aws/`, so Terraform cannot create it: X-Ray creates it on the first span export and `transaction_search.tf` imports it to hold 7 day retention. An import block whose target does not exist is a plan time error, so a brand new account applies once with `adopt_spans_log_group = false`, generates one span, then sets it `true` and applies again.
- **`bootstrap_image_tag` is a create-time seed that expires out from under you.** It seeds `image_uri` at `CreateFunction` and also gates `local.domain_functions_enabled`; after that `image_uri` is on the `lambda-function` module's `ignore_changes` list, so `deploy-backend.yml` owns every update. The ECR lifecycle policy keeps only the last ten `sha-` tagged images per repository, so a tag left pointing at an older commit is expired. A speculative plan cannot detect it: the plan renders the image URI as a string and only `CreateFunction` resolves it, so the run is green and the apply fails partway through. **Refresh it to a current tag before any apply that creates a function**, then confirm the tag resolves with `aws ecr describe-images --repository-name carmodpicker-<env>/<domain> --image-ids imageTag=sha-<sha>`.
- **The ECR repositories use immutable tags**, so a workflow rerun for the same commit would fail on a tag that already exists. The build job skips instead, resolving the tag with `aws ecr batch-get-image`.
- **A DynamoDB stream view type cannot be edited once a stream exists.** Changing one mints a new stream ARN and silently detaches every consumer reading the old one.

## Conventions

- **Naming**: every resource name starts with `local.prefix`, `carmodpicker-<environment>`.
- **Tags**: `Project`, `Environment`, `ManagedBy=terraform`, applied globally via provider `default_tags`.
- **Secrets**: values flow HCP workspace variable to `var.*` to Secrets Manager. The Lambda resolves `<prefix>/app` through `APP_SECRETS_ARN` on the first read of a secret field, not at import, so a function that reads no secret makes no call and needs no `secretsmanager:GetSecretValue` grant. No secret values live in outputs or version control.
- **Lambda code is not Terraform's**: every function is a container image and Terraform owns only the create.

## Local validation

```bash
terraform fmt -check -recursive terraform/
cd terraform && terraform init -backend=false && terraform validate
```

`terraform plan` runs in HCP on push.

## Teardown notes

DynamoDB tables set `point_in_time_recovery` and `deletion_protection` to `true` in production, so a production table cannot be destroyed without clearing protection first.
