# Production promotion plan, the ordered sequence

The concrete step list for promoting `staging` to `main` and into the
production workspace `ws-oh1VvpTBPxmcrSYD`.

**This document is the single authority on this promotion.** An earlier
`docs/prod-promotion-runbook.md`, written 2026-09-10, was superseded on ordering
by row 13 and has been deleted; everything from it that still applies to a
pending step is folded in below. Git history keeps the original.

Read `docs/identity-adoption.md` for what the rows are and
`docs/identity-migration-runbook.md` for the scripts.

**Nothing here is authorised to run itself.** Every merge, every apply and every
write is an owner decision.

## The finding that sets the order

The original runbook, written 2026-09-10, assumed the promotion merge lands a
tree that can still serve legacy auth, and scheduled the credential migration
after the merge and after the first apply. **That is no longer true.** Row 13
(`bd9c9bc3`, PR 421) landed on `staging` on 2026-09-11 and deleted the legacy
auth path as code, with no variable in front of it.

Verified at `origin/staging` head `59d99357`:

- `backend/app/api/endpoints/auth/` is gone. `core.py`, `oauth.py`,
  `two_factor.py` and `webauthn.py` exist at `origin/main` and do not exist at
  `origin/staging`. Those four routers are the 24 routes that served
  `/api/auth/token`, `/api/auth/token/2fa`, `/api/auth/oauth/google` and
  `/api/auth/oauth/google/signup`.
- `app/composition/domains.py` declares `_identity_routers()` returning `[]`.
  Its docstring reads "No routers of its own since row 13. The package's router
  is all of `/api/auth`." There is no conditional and no flag.
- `backend/app/lambda_handler.py` is deleted, so the monolith has no handler to
  run even if its function survived.
- `frontend/src/api/authMode.ts` declares `AUTH_MODES = ['identity']` and
  `AUTH_MODE` as a constant. `VITE_AUTH_MODE` is read by nothing;
  `authMode.test.ts` asserts `import.meta.env['VITE_AUTH_MODE']` is undefined.
- No `LEGACY_AUTH`, `AUTH_MODE` or equivalent backend setting exists anywhere
  under `backend/app/`. The only surviving `decode_access_token` call is the
  price drop alert unsubscribe link in `part_price_alerts.py`, which is an
  HS256 email token and not a sign-in path.

**So there is no production variable value that makes the staging tree serve
legacy auth.** The promotion merge is a hard cutover for authentication: the
moment the new images are deployed, `/api/auth/token` returns 404 and the only
way in is the identity path, which reads the `credentials` table.

Production today has 174 users, 30 of whom hold `hashed_password` as their only
credential, 1 with TOTP, and `carmodpicker-production-credentials` **does not
exist**. Real browsers completed legacy sign-ins on all four legacy routes in
the last 7 days.

If the merge happens before those 30 credentials are migrated, all 30 are locked
out with no backout short of reverting `main` and waiting for a rebuild.

### The answer: one merge, not several, but the migration moves before it

**One code merge, then variable flips with separate applies.** The row toggles
that remain after the merge are all Terraform variables, not code:

| Row | Toggled by | Production value at merge |
| --- | --- | --- |
| Row 8, gateway JWT on `/api/auth` | `identity_jwt_mode` | absent, so `off` |
| Row 12, gateway JWT on the 80 domain keys | `domain_jwt_enforced` | absent, so `false` |
| Passkey routes | `passkeys_enabled`, `passkeys_passwordless` | absent, so `false` |
| Rows 25 to 33, the domain split | code only, no variable | lands with the merge |
| **Row 13, legacy auth retired** | **code only, no variable** | **lands with the merge** |

The last row is the whole problem. Rows 8 and 12 are genuinely deferrable to
later applies and the original three-apply structure is right for them. Row 13
is not deferrable at all, so it cannot be sequenced after the merge the way the
original ordering assumed.

Splitting the merge to defer row 13 was considered and rejected. It would mean
reverting `backend/app/api/endpoints/auth/`, `domains.py`, `lambda_handler.py`,
`main.py`, the frontend auth client and the users model onto a promotion branch,
which is a large reconstruction of a tree that was deliberately deleted, and it
would have to be un-reverted in a second promotion. The migration scripts are
the supported path and they run against production from a workstation without
needing any of that code deployed.

**The order that follows:** migrate the credentials and seal the TOTP seeds
**first**, against production, using the scripts run from a `staging` checkout
while production still runs the monolith. Then merge. The identity function
comes up against a `credentials` table that is already populated, and no user is
locked out at any point.

This works because the migration is purely additive. It reads
`carmodpicker-production-users` and writes `carmodpicker-production-credentials`
and `-totp-factors`. Nothing reads those tables until the identity function
exists, so populating them early changes no behaviour. The legacy monolith keeps
serving `/api/auth/token` off `hashed_password`, untouched, right up to the
merge.

The one ordering constraint it creates: **the identity tables must exist before
the merge**, and they are created by the first apply, which is triggered by the
merge. That circularity is resolved in step 3 by creating the identity stack on
its own apply from a branch that does not carry row 13. See step 3 for the exact
mechanism and why a `-target` apply is not needed.

## Summary

**Applies: five.** One identity-stack-only apply before the merge, then the
the original three (first apply, mode native, domain enforcement), then one
cleanup. Steps needing the owner present are marked.

| # | Step | Owner present |
| --- | --- | --- |
| 0 | Gates and restore point | yes |
| 1 | Refresh `bootstrap_image_tag`, confirm images | no |
| 2 | Identity-stack-only apply, from a no-row-13 branch | **yes, apply** |
| 3 | Deploy the identity function, confirm discovery and JWKS | no |
| 4 | Migrate the 30 credentials, dry run then apply | **yes, gate** |
| 5 | Seal and verify the TOTP seed | **yes, gate** |
| 6 | Prove identity sign-in works while legacy still serves | **yes, browser** |
| 7 | Merge `staging` to `main`, refresh the tag again | **yes, release** |
| 8 | First full apply, mode off | **yes, apply** |
| 9 | Verify the cutover: legacy 404, identity 200 | **yes, browser** |
| 10 | Second apply, `identity_jwt_mode = native` | **yes, apply** |
| 11 | Verify the gateway authorizer | no |
| 12 | Third apply, `domain_jwt_enforced = true` | **yes, apply** |
| 13 | Removed by owner decision, 2026-09-13 | n/a |
| 14 | Chrome extension, then clear the plaintext TOTP seed | **yes, one-way door** |
| 15 | Dry run `clear_legacy_credentials.py` | **yes, gate** |
| 16 | Apply `clear_legacy_credentials.py` | **yes, one-way door** |
| 17 | Close out and cleanup apply | no |

## Step 0. Gates and restore point

Owner present. Nothing below runs until every box is checked.

- [ ] A production speculative plan renders, `planned_and_finished` with a diff.
      Fixed in `platform-modules` `v2.10.0`.
- [ ] The divergence check and trial merge are clean, re-run today:

      git fetch origin
      git merge-tree --write-tree origin/staging origin/main | head -20

- [ ] The owner accepts that **the merge in step 7 is a one-way cutover for
      authentication** and that backing it out means reverting `main` and
      waiting for a rebuild.
- [ ] The owner accepts the SES sandbox limitation for password reset.
- [ ] `CHROME_EXTENSION_AUTO_RELEASE` is unset on the `production` environment.
- [ ] The Google and GitHub OAuth apps carry
      `https://api.carmodpicker.com/api/auth/oauth/callback` exactly.

Record the revert target and snapshot the users table:

    cd /home/tyler-webb/Documents/Github/WebbPulse/CarModPicker
    git fetch origin && git rev-parse origin/main

    AWS_PROFILE=CarModPicker-Production/AdministratorAccess \
      aws dynamodb scan --region us-west-2 \
        --table-name carmodpicker-production-users \
        > ~/cmp-prod-users-preflight.json
    jq '.Count' ~/cmp-prod-users-preflight.json

Expect 174. **That file holds 174 real bcrypt hashes and the plaintext TOTP
seed.** `jq '.Count'` is the only thing that should read it other than a
restore. Delete it at step 17.

Record the current variable state for the rollback:

    T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
    curl -s -H "Authorization: Bearer $T" \
      https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
      | jq -r '.data[] | select(.attributes.sensitive == false)
               | "\(.attributes.key)=\(.attributes.value)"'

Confirm `identity_jwt_mode` and `domain_jwt_enforced` are absent. If
`identity_jwt_mode=native` prints, stop: any queued run fails at
`CreateAuthorizer`.

**Backout:** nothing has changed. **Verification:** the four commands above.

## Step 1. Refresh `bootstrap_image_tag` and confirm the images

Production ECR holds only `sha-46a28433` and `sha-51d573a3`, because images
build only on a push to `main` or `staging` and the keep-last-10 lifecycle
policy removes older tags. The tag on the workspace must name an image that
still exists before any apply that creates a Lambda.

`bootstrap_image_tag` is currently
`sha-51d573a3a2d987ad3b3915c632f1cd394f85e672`, which is `origin/main` head and
does resolve today. Confirm rather than assume:

    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
    TAG=$(curl -s -H "Authorization: Bearer $T" \
      https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
      | jq -r '.data[] | select(.attributes.key=="bootstrap_image_tag") | .attributes.value')
    echo "$TAG"
    for d in identity users catalog build-lists media build-logs moderation vehicles admin; do
      printf '%-12s ' "$d"
      aws ecr describe-images --repository-name "carmodpicker-production/$d" \
        --image-ids "imageTag=$TAG" \
        --query 'imageDetails[0].imagePushedAt' --output text 2>/dev/null || echo MISSING
    done

**Gate:** `identity` prints a timestamp. Step 2 creates only the identity
function, so that is the one that must resolve. A `MISSING` on `identity` means
step 2 fails at `CreateFunction` with the role and log group already made.

**Backout:** none needed, this step only reads. **Owner:** not required.

## Step 2. Identity-stack-only apply, from a branch without row 13

Owner present for the apply.

This creates the two KMS keys, the ten identity tables, the identity function
and its three role policies, **without** row 13 and without the domain split's
remaining rows. It exists so the migration in steps 4 and 5 has tables to write
into while production still serves legacy auth from the monolith.

Cut the branch from `origin/main`, which has no row 13 by construction, and take
only what the identity stack needs:

    git fetch origin
    git checkout -b promo/identity-stack origin/main
    git checkout origin/staging -- terraform/identity.tf
    git checkout origin/staging -- terraform/variables.tf
    git checkout origin/staging -- terraform/lambda_domains.tf
    git checkout origin/staging -- terraform/apigateway.tf

Then, on that branch, reduce `local.lambda_domains_declared` in
`terraform/lambda_domains.tf` to the five production domains plus `identity`,
and remove `build-lists`, `catalog` and `users`. Leave `identity.tf` whole.
Leave `apigateway.tf`'s `local.identity_jwt_route_keys` and
`local.domain_identity_jwt_route_paths` in place: with `identity_jwt_mode`
absent and `domain_jwt_enforced` absent, every key lands unmarked and inert.

This is a **Terraform-only branch**. It carries no `backend/` or `frontend/`
change, so the images it deploys are `main`'s images, which still serve legacy
auth. That is the point: the identity function comes up on `main`'s code, where
`app/entrypoints/identity.py` exists and the package router is mounted, and the
monolith keeps serving `/api/auth/token` beside it.

A `-target` apply is **not** needed. Blocker 1 is fixed: `platform-modules`
`v2.10.0` moved the three identity role policies onto `attach_role_policies`, a
plan-time boolean, so the plan renders even though the identity role is still to
be created. Confirm `terraform/identity.tf` pins `~> 2.10` or later before
queueing.

Open a pull request from `promo/identity-stack` into `main`, read the plan on
the speculative run, and merge it. Merging fires `deploy-backend.yml`, which is
expected and harmless: it pushes images and calls `UpdateFunctionCode` on
functions that exist.

**Expected plan:** roughly 40 to add, 0 to change, 0 to destroy.

| Group | Expect |
| --- | --- |
| KMS keys, aliases, key policies | 2 keys, 2 aliases, 2 policies |
| Identity tables | 10 create, all `deletion_protection = true` |
| IAM role policies on the identity role | 3 create |
| Identity Lambda, role, log group, X-Ray policy | 1 function plus its role and log group |
| Gateway routes | the `/api/auth` prefix cut plus row 8's 15 keys, all `NONE` |
| `aws_apigatewayv2_authorizer` | **0. Any authorizer here is a hard stop.** |
| Destroys of any kind | **0. Any destroy here is a hard stop.** |
| Route 53 record changes | **0** |

**Gate:** zero destroys, zero authorizers, zero Route 53 changes, and the
monolith `carmodpicker-production-api` is untouched. Then apply.

**Backout:** this apply is purely additive, so the backout is to leave it. The
ten tables carry `deletion_protection = true` and cost nothing empty. If the
promotion is abandoned entirely, remove them deliberately rather than by a code
revert.

## Step 3. Deploy the identity function and confirm discovery

Dispatch a backend deploy so the identity function runs `main`'s image rather
than the bootstrap image, then gate on discovery:

    gh workflow run deploy-backend.yml --ref main --repo WebbPulse/CarModPicker
    gh run watch <run-id> --repo WebbPulse/CarModPicker

    curl -s https://api.carmodpicker.com/api/auth/.well-known/openid-configuration | jq .
    curl -s -o /dev/null -w "jwks %{http_code}\n" \
      https://api.carmodpicker.com/api/auth/.well-known/jwks.json

**Gate**, all four:

- Both return `200`. Both return `404` today.
- `issuer` is exactly `https://api.carmodpicker.com/api/auth`, **with the
  path**. A bare host is wrong.
- `jwks_uri` is exactly
  `https://api.carmodpicker.com/api/auth/.well-known/jwks.json`.
- The JWKS body carries at least one **RSA** key. The authorizer is RSA only.

Confirm the legacy path is still serving, which is the whole reason this step
precedes the merge:

    curl -s -o /dev/null -w "legacy token %{http_code}\n" \
      -X POST https://api.carmodpicker.com/api/auth/token \
      -d 'username=nobody&password=wrong'

Expect `401`, not `404`. A `404` means row 13's code reached production early
and the ordering assumption of this plan is broken. Stop and reassess.

**Backout:** redeploy the previous image. **Owner:** not required.

## Step 4. Migrate the 30 credentials

Owner present for the gate.

Run from a `staging` checkout, because the scripts live there. They talk to
DynamoDB directly and need none of that code deployed.

    cd backend
    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    python scripts/migrate_credentials_to_identity.py --prefix carmodpicker-production

`--prefix` selects the environment for **both** tables: `parse_args` writes it
back into `DYNAMODB_TABLE_PREFIX`, because the legacy users repository reads
that setting rather than the flag and would otherwise hit
`carmodpicker-development-users`. The value is `carmodpicker-production`, with
**no trailing hyphen**.

Expect across 174 rows:

- `write` **30**, the rows carrying a bcrypt `hashed_password`,
- `skip_oauth_only` substantial, the Google-only accounts, which need no
  credential row and are not data loss,
- `unchanged` **0** on a first run,
- `conflict` **0**,
- `skip` **0**.

**Gate: zero conflicts and zero unsupported hashes.** CarModPicker has no admin
seeder, so nothing should have written an identity credential before this ran. A
conflict here is an unexplained write into production auth data. **Do not reach
for `--replace`.** Confirm with the owner first.

Then write:

    python scripts/migrate_credentials_to_identity.py --prefix carmodpicker-production --apply

The hashes copy verbatim, both sides `webbpulse.security.hash_password`, bcrypt
cost 12, same 72 byte truncation on hash and on verify. **No user resets a
password.** The script is idempotent and preserves `created_at` on a rerun.

Verify the count landed:

    aws dynamodb scan --table-name carmodpicker-production-credentials \
      --select COUNT --query 'Count'

Expect 30.

**Backout:** the credential rows are read by nothing until the merge. Deleting
them restores the prior state exactly.

## Step 5. Seal and verify the TOTP seed

Owner present for the gate. Production holds exactly one TOTP user.

    cd backend
    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    P=--prefix=carmodpicker-production

    python scripts/migrate_totp_seeds_to_identity.py $P            # dry run
    python scripts/migrate_totp_seeds_to_identity.py $P --apply    # seal
    python scripts/migrate_totp_seeds_to_identity.py $P --verify   # read only

Sealing generates an AES-256 data key from KMS under `IDENTITY_DATA_KEY_ARN`,
encrypts the seed with AES-256-GCM and stores the ciphertext, nonce and wrapped
key. The encryption context is `{"user_id": <id>, "purpose": "totp"}`, bound by
KMS as authenticated data, so a ciphertext copied to another row fails to
decrypt rather than authenticating the wrong person.

**The seed is unchanged, so the authenticator is not re-enrolled.** Same base32
bytes, same RFC 6238 defaults. Nobody rescans a QR code.

**`--apply` deliberately leaves the plaintext on the user row.** Clearing it is
step 14 and is the one-way door.

**Gate: `--verify` exits zero.** It opens the sealed row back through
`EnvelopeCipher`, writes nothing, and exits non-zero on anything missing,
unreadable or mismatched. Step 14's clear must not run unless this passed.

**Backout:** delete the sealed row. The plaintext is still on the user row.

## Step 6. Prove identity sign-in works while legacy still serves

Owner present, in a browser.

This is the gate that makes the merge safe, and it has no equivalent in the
the original ordering, which had legacy auth to fall back on. Here the merge is
one-way, so identity sign-in must be proven **before** it, while the monolith is
still there to fall back to.

The identity function is deployed and the credentials are migrated, so a real
account can sign in through the identity path right now:

    API=https://api.carmodpicker.com
    curl -s -X POST $API/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"email":"<owner-email>","password":"<password>"}' \
      | jq '{has_access: (.access_token != null), token_type}'

Note the identity login takes `email` where the legacy `/api/auth/token` took
`username`. Do not paste a password into a shared transcript.

A wrong password must be refused:

    curl -s -o /dev/null -w "bad pw %{http_code}\n" -X POST $API/api/auth/login \
      -H 'Content-Type: application/json' \
      -d '{"email":"<owner-email>","password":"definitely-not-the-password"}'

Expect `401`. A `200` is an immediate stop.

Confirm both OAuth providers are advertised, which is the behavioural check that
the two `OAUTH_*_CLIENT_SECRET` keys reached the app secret:

    curl -s $API/api/auth/oauth/providers | jq .

Expect `google` and `github`. An empty list means a client id or secret is
missing. **Never call `get-secret-value` to check this.**

**Gate, and it is the most important one in this document:** a real account
signs in through `/api/auth/login` with its own password, a wrong password is
401, and the providers list has two entries. Legacy sign-in still works at the
same time. Do not merge otherwise.

**Backout:** nothing has been taken away. If identity sign-in does not work, the
merge does not happen and production keeps running as it is.

## Step 7. Merge `staging` to `main`

Owner present. **This is a release and a one-way authentication cutover.**

Re-confirm both JWT variables are still absent:

    T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
    curl -s -H "Authorization: Bearer $T" \
      https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
      | jq -r '.data[].attributes | select(.key=="identity_jwt_mode" or .key=="domain_jwt_enforced")
               | "\(.key)=\(.value)"'

Expect no output.

CarModPicker uses squash merges, so the merge commit sha is what
`bootstrap_image_tag` becomes:

    gh pr create --base main --head staging \
      --title "Promote the identity adoption and the domain split to production" \
      --body "..." --repo WebbPulse/CarModPicker
    gh pr merge <n> --squash --repo WebbPulse/CarModPicker
    MERGE_SHA=$(git fetch origin && git rev-parse origin/main)
    echo "$MERGE_SHA"

Let Deploy Backend finish. It will partly fail and that is expected:
`deploy-images` calls `UpdateFunctionCode` on `build-lists`, `catalog` and
`users`, which do not exist yet, and `verify-route-cuts` probes prefixes that
are not cut. **Only `build-images` must be green**, because the images are what
the first apply creates the functions from.

    gh run list --branch main --workflow deploy-backend.yml --limit 3 --repo WebbPulse/CarModPicker
    gh run watch <run-id> --repo WebbPulse/CarModPicker

Confirm the tag landed in all nine repositories, then set it:

    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    for d in build-lists catalog identity users media build-logs moderation vehicles admin; do
      printf '%-12s ' "$d"
      aws ecr describe-images --repository-name "carmodpicker-production/$d" \
        --image-ids "imageTag=sha-$MERGE_SHA" \
        --query 'imageDetails[0].imagePushedAt' --output text 2>/dev/null || echo MISSING
    done

**Gate: all nine print a timestamp.** A `MISSING` means the first apply fails
partway at `CreateFunction`. Do not proceed.

    T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
    VAR_ID=$(curl -s -H "Authorization: Bearer $T" \
      https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars \
      | jq -r '.data[] | select(.attributes.key=="bootstrap_image_tag") | .id')
    curl -s -X PATCH -H "Authorization: Bearer $T" \
      -H "Content-Type: application/vnd.api+json" \
      -d "{\"data\":{\"id\":\"$VAR_ID\",\"type\":\"vars\",\"attributes\":{\"value\":\"sha-$MERGE_SHA\"}}}" \
      "https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars/$VAR_ID" \
      | jq -r '.data.attributes | "\(.key)=\(.value)"'

The frontend deploy that follows the merge ships the identity-only bundle. **No
`AUTH_MODE` GitHub variable is needed and none should be set**: row 13 made
`AUTH_MODE` a constant in `authMode.ts` and `VITE_AUTH_MODE` is read by nothing.
The original runbook said to set it and that instruction is obsolete.

**Backout:** revert `main` to the step 0 sha and wait for a rebuild. Users are
on legacy auth until the images redeploy, which is minutes, not seconds.

## Step 8. First full apply, mode off

Owner present for the apply.

The merge queued a run before the tag was refreshed. **Discard it and queue a
fresh one** rather than confirming a plan against the stale tag.

Step 2 already created the identity stack, so this plan is smaller than the
the 2026-09-10 estimate of 201/6/18. Expect roughly **160 to add, 6 to change,
18 to destroy**.
Treat the counts as shapes to check, not a number to match, and read every
destroy line.

| Group | Expect |
| --- | --- |
| Domain functions | 3 create, `build-lists`, `catalog`, `users`, each with role, log group, X-Ray policy and runtime policy. `identity` already exists from step 2 |
| Identity stack | **no change.** KMS keys, tables and role policies all landed at step 2 |
| Gateway routes, row 12a | 82 create, 80 domain keys plus 2 anonymous guard keys, all unmarked |
| Gateway routes, domain cuts | 6 create, the `ANY` bare and `{proxy+}` pair for each of three new prefixes |
| Gateway authorizer | **0. Mode is off. Any authorizer here is a hard stop.** |
| `carmodpicker-production/app` secret version | 1 change, or 1 create plus 1 destroy. A secret version showing as add plus destroy is normal |
| Route 53 records | **0 changes** |
| Monolith retirement, row 32 | destroys: `carmodpicker-production-api`, `$default`, the artifacts bucket and the zip chain. **Expected and the point of row 32** |
| Destroys of any DynamoDB table | **expect none. A data table destroy is a hard stop** |

**Gate:** no DynamoDB table destroy, no authorizer, no Route 53 change, and the
only destroys are row 32's retirement, each one recognised. Then apply.

No workspace auto-applies, so confirm through the UI or the API after reading
the plan.

**This apply is the cutover.** When it lands, `$default` and the monolith are
gone and `/api/auth/token` returns 404.

**Backout:** set `identity_jwt_mode` and `domain_jwt_enforced` back to absent if
they were touched, revert `main`, and accept that the monolith retirement is not
cleanly reversible: the artifacts bucket's objects are gone. Treat any rollback
past this point as fix-forward on the domain split.

## Step 9. Verify the cutover

Owner present, in a browser.

    API=https://api.carmodpicker.com

    curl -s -o /dev/null -w "legacy    %{http_code}\n" -X POST $API/api/auth/token \
      -d 'username=nobody&password=wrong'
    curl -s -o /dev/null -w "discovery %{http_code}\n" $API/api/auth/.well-known/openid-configuration
    curl -s -o /dev/null -w "jwks      %{http_code}\n" $API/api/auth/.well-known/jwks.json
    curl -s -o /dev/null -w "retailers %{http_code}\n" $API/api/retailers/count
    curl -s -o /dev/null -w "makes     %{http_code}\n" $API/api/car-generations/stats/car-makes
    curl -s -o /dev/null -w "search    %{http_code}\n" "$API/api/search/?q=civic"

Expect `404, 200, 200, 200, 200, 200`. The legacy `404` is row 13 landing and is
correct here, where it would have been a stop at step 3. The last three are the
regression check: they are `200` today and must stay `200`.

There is no `/health` and no `/api/car-makes` on the production gateway. The
HTTP API carries only the 142 explicit domain route keys, with no `$default` and
no root health route, so both return `404` and neither is a useful probe. Pick
public reads that live on a real route key, as the three above do. Mind the
trailing slashes too: `/api/search` and `/api/car-generations/` both answer
`307`, and `/api/search/` without a query is `422`.

Then **sign in at `https://www.carmodpicker.com` in a browser as a real user**
and confirm the session survives a reload. Not a curl, and not a synthetic
account.

Confirm the legacy routes have actually gone quiet rather than assuming, by
reading the access log for the four legacy paths over the hour after the apply:

    aws logs start-query \
      --log-group-name /aws/apigateway/carmodpicker-production-api \
      --start-time $(date -d '1 hour ago' +%s) --end-time $(date +%s) \
      --query-string 'fields @timestamp, path, status
        | filter path like /\/api\/auth\/(token|oauth\/google)/
        | stats count() by path, status'

Any `200` on a legacy path after this apply means something is still serving it
and wants reading before step 10. The access log group is
`/aws/apigateway/carmodpicker-production-api`, which outlives the monolith
function of the same name. A request the gateway itself rejected, rather than
passing to a function, logs `integrationLatency` as `-`.

**Gate:** browser sign-in works, public reads unchanged, legacy paths 404.
Otherwise roll back before touching the gateway.

## Step 10. Second apply, `identity_jwt_mode = native`

Owner present for the apply.

    T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
    curl -s -X POST -H "Authorization: Bearer $T" \
      -H "Content-Type: application/vnd.api+json" \
      -d '{"data":{"type":"vars","attributes":{
            "key":"identity_jwt_mode","value":"native","category":"terraform","sensitive":false,
            "description":"Native API Gateway JWT authorizer. Requires the identity function to be deployed and already serving discovery and JWKS at the production API host, because CreateAuthorizer fetches both synchronously at create time."}}}' \
      https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars

The validation in `variables.tf` refuses `native` when `environment` is
`staging`, so this value is only ever valid on this workspace. Staging uses
`gate`, because every route there carries the staging access gate's REQUEST
authorizer and a route takes exactly one authorizer.

`CreateAuthorizer` **synchronously fetches** the discovery document and then the
JWKS it names, from outside AWS, at create time. Step 3 already proved both
serve, which is why this apply can be queued at all.

Expected plan: **1 add, 0 change, 15 replacements**.

| Group | Expect |
| --- | --- |
| `aws_apigatewayv2_authorizer` | 1 create, type `JWT`, issuer `https://api.carmodpicker.com/api/auth`, audience `carmodpicker-production-api` |
| Row 8's marked routes | **15 replacements**, not updates. Every key in `local.identity_jwt_route_keys` carries `require_identity_jwt = true`, so all fifteen move into the module's separate JWT route resource |
| Row 12a's 80 domain keys | **unchanged.** `domain_jwt_enforced` is still `false` |
| The 2 anonymous guard keys | **unchanged**, and never marked |
| `.well-known` routes | **unchanged.** They must stay anonymous, since the authorizer fetches them |
| Generated `ANY` prefix pairs | **unchanged** |

**Gate:** the plan replaces exactly the fifteen keys carrying
`require_identity_jwt`, touches neither `.well-known` route, and moves none of
the eighty domain keys. Verify against `module.api.identity_jwt_route_keys` in
the plan output rather than trusting the number here. Then apply.

Route replacement is briefly disruptive on those fifteen. It is seconds, and
they are identity-management routes rather than the public catalogue.

**Backout:** set `identity_jwt_mode` back to `off` and apply. The routes return
to `NONE` and the authorizer is destroyed. The frontend is unaffected either
way, because the identity function verifies tokens itself in every mode.

If the apply fails inside `CreateAuthorizer` with a message about fetching the
discovery document, step 3's gate regressed. Set the variable back to `off`,
apply to clean up, and return to step 3.

## Step 11. Verify the gateway authorizer

    API=https://api.carmodpicker.com
    curl -s -o /dev/null -w "no token  %{http_code}\n" -X POST $API/api/auth/logout-all
    curl -s -o /dev/null -w "discovery %{http_code}\n" $API/api/auth/.well-known/openid-configuration

Expect `401` then `200`.

Distinguishing a gateway 401 from an application 401 matters, because only the
first proves the authorizer is doing anything. Both read as 401 from a
token-less probe. Tell them apart by `integrationLatency` in the access log: a
`-` means the request was denied before the function was invoked.

Then call a flagged route with a valid access token and expect `200`.

**Gate:** a flagged route refuses a missing token from the gateway and accepts a
valid one. **Owner:** not required.

## Step 12. Third apply, `domain_jwt_enforced = true`

Owner present for the apply. **Run this at a quiet hour**, not alongside a
frontend deploy.

    T=$(jq -r '.credentials["app.terraform.io"].token' ~/.terraform.d/credentials.tfrc.json)
    curl -s -X POST -H "Authorization: Bearer $T" \
      -H "Content-Type: application/vnd.api+json" \
      -d '{"data":{"type":"vars","attributes":{
            "key":"domain_jwt_enforced","value":"true","category":"terraform","sensitive":false,
            "description":"Require an identity access token at the gateway on the 80 domain route keys that need an authenticated caller. The keys exist and are inert either way."}}}' \
      https://app.terraform.io/api/v2/workspaces/ws-oh1VvpTBPxmcrSYD/vars

The description text above is the one to paste when the variable is created:
the keys exist and are inert either way, and the flip is only safe once the
deployed frontend sends identity tokens.

**This is not Portfolio's 0/1/0, and it is not staging's shape either.** In
`gate` mode the platform module keeps a marked route at the same address and the
only diff is the gate authorizer Lambda's environment gaining the route list.
Production is in `native` mode, where `module.api.identity_jwt` is non-null and
the module moves every route carrying `require_identity_jwt` into its own
resource. A move between resource addresses is a replacement.

Expect roughly **80 add, 0 change, 80 destroy** rendered as replacements.

| Group | Expect |
| --- | --- |
| Domain route keys | **80 replacements**, against the keys in `local.domain_identity_jwt_route_paths` |
| The 2 anonymous guard keys | **unchanged**, never marked |
| Row 8's 15 identity keys | **unchanged**, already on the authorizer from step 10 |
| `aws_apigatewayv2_authorizer` | **unchanged**, 1 |
| Generated `ANY` prefix pairs | **unchanged** |

**Gate:** exactly the eighty keys move, the fifteen identity keys are untouched,
and the two guard keys `GET /api/reports/count` and `GET /api/bug-reports/count`
are **not** among them. They hold a more specific match than the flagged `{id}`
keys on the same method and depth, and marking them would demand a token on an
anonymous count route. Then apply.

Eighty route replacements is briefly disruptive across every authenticated write
path. They are not replaced atomically.

Re-probe after it lands, a write both ways:

    curl -s -o /dev/null -w "write     %{http_code}\n" -X POST $API/api/part-price-alerts \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{...}'
    curl -s -o /dev/null -w "write 401 %{http_code}\n" -X POST $API/api/part-price-alerts \
      -H 'Content-Type: application/json' -d '{...}'

Claims reach the domain functions at `requestContext.authorizer.jwt.claims` as a
**string map**: every value is a string, `exp`, `iat` and `nbf` included, because
API Gateway flattens the claim set. The Lambda Web Adapter forwards the request
context in `x-amzn-request-context` as **plain JSON, not base64**; a base64
decode of it fails and presents as a 401.

**Backout:** set `domain_jwt_enforced` back to `false` and apply. The eighty keys
move back and stay pointed at the same integrations throughout, so a request
reaches the same function by the same route either way.

## Step 13. Removed

**Removed by owner decision on 2026-09-13.** This step was a full working day
soak whose gate was a meaningful number of the 30 password users signing in.
The owner is effectively the only active user, so that sign in count could never
be met and the step would have blocked the rollout indefinitely. The owner
accepted the UX risk in order to finish the promotion.

The alarm check this step carried now runs as a one off precondition at the top
of step 14. The heading stays so the later step numbers and every cross
reference to them keep working.

## Step 14. Chrome extension, then clear the plaintext TOTP seed

Owner decision.

**Precondition, checked once rather than watched.** Step 12 has landed, the
owner has signed in through the identity path in a browser, one authenticated
write has succeeded, and the alarms are quiet:

    aws cloudwatch describe-alarms --state-value ALARM \
      --query 'MetricAlarms[].AlarmName' --output text

Expect empty.

The release is held behind a `production` environment variable. The gate in
`.github/workflows/chrome-extension-deploy.yml` releases on a push only when
`CHROME_EXTENSION_AUTO_RELEASE` is exactly `true`. It is unset by default, which
is the hold, so the step 7 merge published nothing.

1. `DEFAULT_AUTH_MODE = "identity"` is already on `main` from the merge.
2. Set the variable:

       gh variable set CHROME_EXTENSION_AUTO_RELEASE --body true \
         --env production --repo WebbPulse/CarModPicker

3. Dispatch, which is never gated:

       gh workflow run chrome-extension-deploy.yml --repo WebbPulse/CarModPicker

4. **Put the hold back once the publish is done**, so a later merge touching the
   extension cannot spend a store review by accident:

       gh variable delete CHROME_EXTENSION_AUTO_RELEASE \
         --env production --repo WebbPulse/CarModPicker

A run whose `release` job shows as skipped did not publish. Read the `gate` job
summary for which of the two reasons applies, the variable or an unchanged
extension tree.

A store review is not instant and is outside anybody's control. Existing
installs keep working through the handoff, because `getAuthMode()` reads
`chrome.storage.sync` and an install that has never set it falls to the shipped
default, which row 13 flipped to `identity`.

**This is one publish, not two.** That is the locked decision.

**Backout:** the `authMode` setting remains in the extension as the backout
lever for installs on an older build.

### Clear the plaintext TOTP seed

Owner present. **This is a one-way door.**

Only after step 12 has landed and the owner's own sign in and one
authenticated write succeed, and only if step 5's `--verify` exited zero.

    cd backend
    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    P=--prefix=carmodpicker-production
    python scripts/migrate_totp_seeds_to_identity.py $P --clear-plaintext
    python scripts/migrate_totp_seeds_to_identity.py $P --clear-plaintext --apply

Each row is verified again inside this pass rather than trusting the earlier
`--verify`, which is why it refuses rather than clearing a row it cannot open.

After it, the sealed seed is the only copy and
`docs/security/totp-seed-encryption.md`'s finding is closed.

**Backout:** restore the column from the step 0 snapshot. There is no other
copy.

## Step 15. Dry run `clear_legacy_credentials.py`

Dry run only. Nothing is written at this step.

`backend/scripts/clear_legacy_credentials.py` exists on `staging` and clearing
the legacy columns is safe once the two migration scripts have run. An earlier
note said to leave `hashed_password` populated because it cost nothing and two
users-domain routes still wrote it. Both halves were wrong, and the evidence is
recorded here rather than in the deleted runbook:

- There is no `POST /api/users/` route at all.
  `backend/app/api/endpoints/users.py` declares one `POST`, the profile picture
  upload.
- `PUT /api/users/{user_id}` has no password branch. It copies `UserUpdate`
  fields through and clamps `session_expire_minutes`, nothing else.
- Neither `UserUpdate` nor `AdminUserUpdate` in
  `backend/app/api/schemas/user.py` carries a password field, so the route could
  not receive one.
- The `User` model in `backend/app/db/dynamo/users.py` declares neither
  `hashed_password` nor `totp_secret`.
- Across `backend/app/**` there are exactly two non-test mentions of the column:
  a parameter name in `backend/app/api/dependencies/auth.py`, and a discarding
  `record.pop("hashed_password", None)` in
  `backend/app/composition/identity_hooks.py`. `get_password_hash` and
  `verify_password` in that auth module have zero callers in the application.
- The script's own docstring at `backend/scripts/clear_legacy_credentials.py:23`
  opens by saying the script is safe to run.

So leaving the column populated buys nothing. It is 174 unusable bcrypt
verifiers plus the plaintext TOTP seeds, a standing exposure rather than a
rollback asset, and row 13 deleted the legacy routes as code so there is nothing
in the shipped image that could read it.

The script is built for exactly this. It is a dry run unless `--apply` is
passed, it classifies every row before it writes anything, it refuses the entire
run on any `mismatch` or `missing_credential` rather than clearing half a table,
it issues one DynamoDB `REMOVE` for both `hashed_password` and `totp_secret`,
and it is idempotent, so a second run reports `already_clear` and writes
nothing.

    cd backend
    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    P=--prefix=carmodpicker-production
    python scripts/clear_legacy_credentials.py $P

Two gates, and both must hold before step 16 is even considered:

- [ ] **Zero refusals.** No row classified `mismatch`, `missing_credential` or
      `errors`. Any of the three refuses the whole run, and a refusal is a signal
      to stop and read, not to rerun. Expect the remainder to split between
      `cleared` and `already_clear`.
- [ ] **The owner has signed in with a real password through the identity path
      in a browser**, after the cutover, not a synthetic account and not a curl
      probe. A migrated credential that nobody has exercised has not been proven
      to work.

A `mismatch` is usually benign and has a known remedy: the identity login path
opportunistically rehashes a credential, so a user who has signed in since the
cutover can hold a credential whose bytes no longer match the legacy column.
The fix is `migrate_credentials_to_identity.py --replace`, which rewrites only the
credential rows it is pointed at. The script has no force or overwrite flag.

**Owner:** yes, gate.

## Step 16. Apply `clear_legacy_credentials.py`

Owner present. **This is a one-way door**, on the same footing as the TOTP seed
clear in step 14.

Only after step 12 has landed and the owner's own sign in and one
authenticated write succeed, and only if step 5's `--verify` exited zero.
Neither this repository nor Portfolio has run this script against production, so
treat it as a first application and read the dry run output rather than skimming it.

    cd backend
    export AWS_PROFILE=CarModPicker-Production/AdministratorAccess AWS_REGION=us-west-2
    P=--prefix=carmodpicker-production
    python scripts/clear_legacy_credentials.py $P
    python scripts/clear_legacy_credentials.py $P --apply

The dry run is repeated immediately before the apply on purpose. Rows can change
classification between runs, for the rehash reason above, so the run that gates
the write should be the one taken minutes before it.

If the apply refuses, nothing was written. Resolve the named rows, with
`--replace` for a `mismatch`, and run the pair again.

**Backout:** restore the two columns for the affected rows from the step 0
snapshot. There is no other copy, and nothing in the shipped image would read
them if there were. Row 13 deleted the legacy routes as code, so a populated
`hashed_password` column was never the rollback path; the rollback is a revert of
`main` plus a rebuild.

## Step 17. Close out

- [ ] Delete `~/cmp-prod-users-preflight.json`.
- [ ] **Delete `LAMBDA_FUNCTION_NAME` and `LAMBDA_ARTIFACTS_BUCKET` from the
      `production` GitHub Environment.** Row 32 deleted `backend-deploy.yml`, the
      monolith function and the artifacts bucket, so both variables now name
      things that do not exist. `TFC_WORKSPACE_ID` and `TFC_API_TOKEN` stay,
      because `frontend-deploy.yml` still polls with them.
- [ ] Confirm no `AUTH_MODE` variable was ever set on the `production`
      environment. It is read by nothing and would be a stale value someone
      later reads as a live fact.
- [ ] Confirm `dig +short TXT _dmarc.carmodpicker.com` is unchanged.
- [ ] Confirm the CloudWatch alarms are quiet.
- [ ] Confirm `aws sesv2 get-email-identity --email-identity carmodpicker.com`
      still reports DKIM `SUCCESS`.
- [ ] Decide separately on `passkeys_enabled` and `passkeys_passwordless`. Both
      default `false` in this repository, deliberately, as a staged rollout
      switch; staging has them `true`. With both unset the passkey routes are
      not declared in production, so **passkey sign-in is not part of the
      production verification** at any step above. That is expected, not a
      fault. `passkeys_passwordless` in particular makes a passkey a way in
      with no password, so it is its own decision rather than a follow-on from
      `passkeys_enabled`.
- [ ] Decide separately on appealing the SES sandbox case. Sending is
      sandbox-limited until an owner-approved support case says otherwise, and
      the earlier request was denied.
- [ ] `extension_api_key` is unset in both environments and is unrelated to this
      promotion. Empty means API-key auth is disabled and only an admin bearer
      token is accepted on the batch price-history route. Leave it unless there
      is a separate reason.

A final cleanup apply may be wanted if step 2's branch left anything that the
step 8 apply did not reconcile. Read the plan; a zero-change plan is the
expected outcome and means nothing is needed.

## Do not do

- **Do not save plan JSON to disk.** HCP plan `json-output` includes sensitive
  variable values in plaintext. Fetch it only through a `jq` filter, never
  redirect it to a file, and tell any subagent the same.
- **Do not call `get-secret-value` or `batch-get-secret-value`** on
  `carmodpicker-production/app`, and do not hit the Secrets Manager Agent daemon.
  Verify the secret's shape from the plan and from behaviour, which is what step
  6's `GET /api/auth/oauth/providers` probe does. `describe-secret` metadata is
  fine. A promotion agent called `get-secret-value` on the Portfolio equivalent
  despite this rule and it is recorded as an incident.
- **`--prefix carmodpicker-production` has no trailing hyphen.** The scripts
  append the separator themselves. A trailing hyphen produces
  `carmodpicker-production--users` and the script fails on a missing table,
  which is the safe failure, but the value is easy to get wrong by pattern
  matching on the table names.
- **Identity keeps its secrets grant.** `identity` is declared with
  `secrets = true` in `terraform/lambda_domains.tf`, alongside `admin` and
  `catalog`. Row 13 removed `APP_SECRETS_ARN` from the other six domains, not
  from these three. A plan that drops the identity function's
  `secretsmanager:GetSecretValue` statement is wrong and wants reading before
  applying.
- **Do not set `AUTH_MODE` on the production GitHub Environment.** Row 13 made
  it a constant in the bundle and `VITE_AUTH_MODE` is read by nothing.
- **Do not run `clear_legacy_credentials.py` before step 15.** It is safe to
  run once the two migration scripts have, but it is a one-way door and it is
  gated on the step 15 dry run refusing nothing and on a real browser sign-in by
  the owner. Steps 15 and 16 are where it belongs.
- **Do not pass `--replace` to the credential migration on a first run.** It is
  the remedy for a `mismatch` at step 15, not a first-run flag, and the script
  has no force or overwrite flag at all.
- **Do not use a `-target` apply.** Blocker 1 is fixed in `platform-modules`
  `v2.10.0`; if a run still errors on a count, read the module pin in
  `terraform/identity.tf` first. It must be `~> 2.10` or later.
- **Do not resolve a merge conflict inside the promotion pull request.** If the
  trial merge at step 0 shows conflict markers, the fix is a separate pull
  request into `staging` that merges `main` back first, reviewed on its own.

## Rollback

### What reverting `main` does not undo

Folded in from the deleted runbook, because a code revert is the lever most
likely to be reached for and these are the parts it does not cover.

- **The gateway authorizer and the route markings.** Both are Terraform state,
  not code deployment. Removing them means setting `domain_jwt_enforced` back to
  `false` and `identity_jwt_mode` back to `off` and applying. Until that apply
  runs, ninety-five routes keep demanding a JWT, and a reverted frontend that
  stopped sending one is locked out of every write path. **Revert the two
  variables and apply before or alongside the code revert, never after.**
- **The identity tables and the two KMS keys.** A revert of the code plans them
  for destroy, and all ten tables carry `deletion_protection = true` because
  `var.environment == "production"`. The destroy fails rather than losing data,
  which is the safe failure, but a clean revert needs them removed from state or
  the protection lifted deliberately. Prefer leaving them: unused tables cost
  nothing and hold the migrated credentials.
- **The monolith retirement.** Row 32 destroyed
  `carmodpicker-production-api`, `$default`, the artifacts bucket and the zip
  chain. Reverting the code plans them back as creates, but the artifacts
  bucket's objects are gone. **This is the least reversible part of the
  infrastructure change and it is independent of identity.** Treat the domain
  split as fix-forward whatever happens to identity.
- **The cleared plaintext TOTP seeds, step 14.** Once cleared, the sealed copy
  is the only one. Recovery is restoring the column from the step 0 snapshot.
- **Anything written through the identity path after the cutover.** A password
  changed through the identity flow exists only in the `credentials` table, and
  a revert to the legacy column resurrects the old password for that user.

A revert is also not instant: the previous images have to finish building and
deploying, which is minutes rather than seconds.

### By step reached

| Reached | Rollback |
| --- | --- |
| Through step 1 | Nothing changed. |
| Through step 2 | The identity stack is additive and unused. Leave it. |
| Through step 5 | As above. Credentials and the sealed seed are read by nothing until step 7. Delete the rows to restore exactly. |
| Through step 6 | As above. The merge has not happened and production is untouched. This is the last cheap point. |
| Through step 8 | Revert `main` to the step 0 sha and wait for the rebuild. **The monolith retirement is not cleanly reversible**: the artifacts bucket's objects are gone. Treat the domain split as fix-forward whatever happens to identity. |
| Through step 11 | Set `identity_jwt_mode` to `off`, apply, then decide on the code. The frontend is unaffected either way. |
| Through step 12 | Set `domain_jwt_enforced` to `false` **and** `identity_jwt_mode` to `off`, and apply. **Revert the variables and apply before or alongside any code revert, never after**: until that apply runs, ninety-five routes keep demanding a JWT. |
| After step 14 | Restore the plaintext seed from the step 0 snapshot, or accept the sealed seed as the only copy and fix forward. Fixing forward is usually right, and the extension is already published. |
| After step 16 | The legacy columns are gone. Restore them from the step 0 snapshot before reverting, or fix forward on the identity path. Fixing forward is usually right, and by this point every signed-in user has already proven the identity path works. |
