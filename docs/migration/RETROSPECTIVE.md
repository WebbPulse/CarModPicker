# Migration retrospective: the per-domain split

The CarModPicker backend moved from one FastAPI monolith on a single Lambda to
nine per-domain functions, each deployed as an OCI image behind the AWS Lambda
Web Adapter. This is the closing record. The planning documents that drove the
work (`split-plan.md`, `inventory.md` and the migration-era
`prod-promotion-runbook.md`) were deleted once it landed; git history keeps
them.

This document is history. It is not a runbook and nothing here is a live
procedure.

## What changed

| Before | After |
| --- | --- |
| One `carmodpicker-<env>-api` Lambda serving `$default` | Nine domain functions, routed by path prefix |
| Zip packaging, uploaded to a `<prefix>-lambda-artifacts` bucket | One OCI image per domain from one `backend/Dockerfile`, `DOMAIN` selecting the entrypoint |
| `backend-deploy.yml` (the zip chain) | `deploy-backend.yml` (the image chain) |
| RDS PostgreSQL | DynamoDB |
| Sentry | OpenTelemetry, traces to X-Ray, structured JSON logs to CloudWatch |
| 14 day log retention | 7 day log retention everywhere |
| Synchronous cascades and aggregates | DynamoDB streams plus SQS for four seams |

The nine domains are `identity`, `users`, `catalog`, `vehicles`,
`build-lists`, `build-logs`, `moderation`, `media` and `admin`. The public API
contract did not change: the frontend needed no edits for the split itself.

Two composition roots survive the migration and are the structure to know
today. Root A (`backend/app/composition/`) mounts every domain in one process
and serves local development and the test suite. Root B
(`backend/app/entrypoints/<domain>.py`) is one module per deployed function.
`CLAUDE.md` describes both as current state.

## How it landed

Work was sequenced as 33 numbered rows, each one pull request, landing on
`staging` first and promoted to `main` as a batch.

| Rows | What landed |
| --- | --- |
| 1 to 8 | Composition roots, the route contract test, per-domain repository bundles, lazy secret resolution, `webbpulse` package adoption |
| 9 to 12 | Nine ECR repositories per environment, deploy role grants, the parameterised Dockerfile, the `deploy-backend.yml` image chain |
| 13 to 21 | The first cuts: `media`, then `build-logs`, `moderation`, `vehicles`, `admin`. Aggregated alarms and 7 day retention landed alongside |
| 22 to 25 | DynamoDB streams on `users`, `parts`, `votes` and `part_listings`, the queues and the DLQ alarm, then seams 3 and 4 (the `net_votes` handler and the price alert email) |
| 26 to 31 | `build-lists`, `identity`, seam 2 (part purge), `catalog`, seam 1 (user delete cascade), and `users` as the ninth and last cut |
| 32 | The monolith retired: the function, `$default`, the artifacts bucket and the zip chain all destroyed, `default_integration` set to null |
| 33 | The frontend `services/Api.ts` shim deleted |

Dates worth keeping:

- **2026-09-06.** Production cut over from App Runner plus RDS PostgreSQL to
  Lambda plus DynamoDB. The legacy stack was destroyed.
- **2026-09-07.** The `ingestion` domain was renamed `admin`, before its
  function existed.
- **2026-09-11.** Row 13 landed on `staging` and deleted the legacy auth path
  as code, with no variable in front of it. This is the single fact that
  reshaped the production promotion, because it made authentication a hard
  cutover rather than a deferrable flag.
- **2026-09-12.** Rows 32 and 33 delivered on `staging`.

## Shapes that were measured, not guessed

One domain cut is `5 + 2 + 2 * prefixes + 2` Terraform adds and 4 changes:
five resources for the function (the module's Lambda, IAM role, log group and
X-Ray policy, plus this repository's own domain policy), two for the
integration (the integration and the Lambda permission), two routes per path
prefix (the bare key and the `{proxy+}` key), and two metric filter adds. The
four changes are the two log-based alarm descriptions and the two aggregate
alarms whose metric math appends a term. Rows 19, 20, 21, 26 and 27 each
counted a real plan and matched exactly.

The alarm module aggregates Lambda alarms through `lambda_function_names` with
a chunk size of ten. Nine domains fit in one chunk, which is why the monolith
was kept out of the list: the signal stays "the backend is erroring" rather
than "group A is erroring".

## Decisions taken along the way

- **Alarm ceiling.** The monolith stayed out of `lambda_function_names` so the
  nine domains share one aggregate errors alarm and one aggregate throttles
  alarm, with no chunking.
- **`net_votes` eventual consistency.** The vote and un-vote routes answer with
  the entity's counts read in the same request, so the frontend never displays
  a stale aggregate. The frontend never read `net_votes` at all: it renders
  `upvotes - downvotes`, and `net_votes` is a server-side sort key.
- **`ingestion` renamed to `admin`**, because it held price alerts and two
  admin modules and `crawled_pages` touches no repository.
- **Log retention 14 to 7 days**, accepted as a smaller debugging window in
  exchange for storage across nine log groups.
- **arm64**, matching the shared base image, with `Pillow`, `bcrypt` and
  `webauthn` verified by building `media` first.

## Where open items live now

The split itself is finished. Three things outlived it:

- **The production identity promotion.** `docs/prod-promotion-plan.md` is the
  live runbook and the only authority on ordering. Steps 0 to 11 are applied;
  Step 12 and Steps 14 to 17 are pending. Step 13 was removed by owner decision
  on 2026-09-13.
- **The identity adoption record and its scripts.**
  `docs/identity-adoption.md` and `docs/identity-migration-runbook.md`.
- **Current-state infrastructure reference.** `terraform/README.md`, and
  `CLAUDE.md` for the repository as a whole.

Two questions were raised during the migration and never settled. Neither
blocks anything today:

- **The two unauthenticated write routes.** `POST /api/parts/{part_id}/listings`
  and `POST /api/parts/price-history` take no user dependency, unlike every
  other mutating route. Both are presumably for the Chrome extension, which
  does hold a bearer token and could send it.
- **The orphan sweep.** Five full table scans behind an admin HTTP route in a
  29 second Lambda. It will time out as the tables grow, and moving it to a
  scheduled job is the fix when that happens.

The `vehicles` boundary was noted at the time as the weakest in the domain map,
because search fans out over four domains and `vehicles` would otherwise be the
smallest domain. It was accepted as the least bad of three options.
