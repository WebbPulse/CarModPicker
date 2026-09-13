# Adopting the shared identity standard

CarModPicker's authentication runs on the org's shared identity layer: the
`webbpulse.identity` package for the flows, and the
`platform-modules/aws//modules/identity` Terraform module for the keys and
tables underneath them. This document is the map of what the rows are.

`docs/prod-promotion-plan.md` owns the production sequence and
`docs/identity-migration-runbook.md` owns the scripts. Neither is repeated here.

## What the standard replaced

| Before | Now |
| --- | --- |
| HS256, one `SECRET_KEY` shared by nine functions | RS256, signed in KMS, private half never leaves it |
| `sub` is the **username** | `sub` is the user id |
| No `iss`, `aud`, `jti`, `kid`, roles or scopes | All of them, `typ` asserted positively on every token |
| No refresh tokens, no revocation, no denylist | Refresh rotation with reuse detection |
| One key signs seven purpose-scoped tokens | Purpose is a claim that is checked, not a convention |
| TOTP seeds in **plaintext base32** on the user item | Sealed under a KMS envelope key, per-user encryption context |
| No recovery codes | A generated set, shown once |
| No account lockout | Progressive lockout on `login-attempts` |
| Each function re-reads `users` on every authenticated request | Claims carry it; an API Gateway JWT authorizer verifies once |

## The six tables

Created by `module.identity` in `terraform/identity.tf`, physically named
`carmodpicker-<env>-<key>`. The key schemas are the package's contract: a table
whose hash key does not match what the store writes fails at request time, not
at apply time.

| Logical name | Hash key | Range key | Index | TTL | PITR |
| --- | --- | --- | --- | --- | --- |
| `credentials` | `user_id` | `credential_type` | none | none | yes |
| `refresh-tokens` | `token_hash` | none | `family_id-generation-index` (hash `family_id`, range `generation`, projection ALL) | `expires_at` | yes |
| `identity-tokens` | `token_hash` | none | none | `expires_at` | yes |
| `login-attempts` | `identity_key` | `attempted_at` | none | `expires_at` | **no** |
| `totp-factors` | `user_id` | none | none | **none, ever** | yes |
| `recovery-codes` | `user_id` | `code_hash` | none | **none, ever** | yes |

`tables` is deliberately **not passed** to the module, so all six come from its
default map. Passing `tables` replaces that map wholesale rather than merging
with it.

**`totp-factors` and `recovery-codes` have no TTL on purpose.** A factor or a
recovery code reclaimed on DynamoDB's own schedule is a silent lockout of an
account somebody still controls, with the paper codes in their hand still
looking valid. Both rows are deleted explicitly, never on a clock.

**Continuous backups are on in both environments**, unlike `module.dynamodb`.
Losing a staging product table costs a reseed; losing staging's `credentials`
table locks every synthetic test account out with no way back. `login-attempts`
keeps the module's `false`, because every row there is a failure counter inside
a lookback window.

## The sequence

| Row | What | State |
| --- | --- | --- |
| 4 | Terraform: `module.identity`, six tables, two KMS keys, env merge | landed |
| 5 | Backend hooks, `composition/identity.py`, mount | landed |
| 6 | Frontend `AuthClient`, verify and reset pages | landed |
| 7 | Credential migration script plus TOTP seed sealing script | landed |
| 8 | Terraform: `identity_jwt_mode`, fifteen explicit `/api/auth` route keys | landed |
| 9 | Backend passkey and OAuth adoption | landed |
| 10 | Chrome extension: auth option, handoff page, publish | landed |
| 11 | Domains read authorizer claims; `sub` becomes the user id | landed |
| 12a | Terraform: 80 explicit domain route keys behind `domain_jwt_enforced` | landed |
| 12 | Cutover: flip the frontend, run migrations, verify, then `domain_jwt_enforced = true` | staging landed 2026-09-11, verified at the gateway |
| 13 | Retire legacy: 24 routes, `hashed_password`, `totp_secret` | staging landed 2026-09-12 (`bd9c9bc3`, PR 421) |

Production is mid-promotion and tracked in `docs/prod-promotion-plan.md`, not
here. That plan's Steps 0 to 11 are applied; Step 12 and Steps 14 to 17 are
pending, and its Step 13 was removed by owner decision on 2026-09-13.

## The row 13 gate

`docs/prod-promotion-plan.md` Step 14 is the authority for this precondition.
What follows is the mirror of it.

**Precondition, checked once rather than watched.** Step 12 has landed, the
owner has signed in through the identity path in a browser, one authenticated
write has succeeded, and the alarms are quiet:

    aws cloudwatch describe-alarms --state-value ALARM \
      --query 'MetricAlarms[].AlarmName' --output text

Expect empty.

This is the one gate in the sequence that a variable cannot undo. Rows 6 through
12 all rolled back by flipping a variable and redeploying, because the legacy
path was still sitting there. After row 13 there is nothing to flip back to.

## What row 13 removes

**The 24 routes.** Every route this application served under `/api/auth` is
gone, along with the four routers that carried them, their schemas, and their
OpenAPI operations. The prefix itself is not gone: the package's own identity
routes mount there. The OpenAPI snapshot moves from 142 paths to 119, and the
operation count drops by exactly 24 with nothing added.

**The legacy HS256 session.** Rows 11 and 12 ran every auth resolver in dual
mode. Row 13 deletes the legacy half of each one. A request either carries an
identity access token the gateway authorizer verified, or it is refused.

**`hashed_password` and `totp_secret`, from the code.** Both columns are off the
`User` model, its schemas, the whole repository including both legacy hash
helpers, the admin seeder and the tests. They are **not** off the rows in
DynamoDB: that is `backend/scripts/clear_legacy_credentials.py`, which runs
after the deploy. See the runbook for the order.

**The password call sites.** `POST /api/users/` is deleted rather than reworked,
as are the password branch of `PUT /api/users/{user_id}` and the admin password
set on `PUT /api/users/admin/users/{user_id}`. Registration is the package's
`POST /api/auth/register` and a password change its `POST /api/auth/password`,
both of which write the `credentials` table the identity function owns. No route
in the application takes a password any more, which is what unblocks
`clear_legacy_credentials.py`.

### What row 13 could not remove

**`SECRET_KEY` survives, for exactly one route.**
`GET /api/part-price-alerts/unsubscribe` reads a 30 day HS256 token that
`app/core/email.py` mints into every price-drop alert email and
`app/api/endpoints/part_price_alerts.py` verifies. The recipient of that email
is by construction not signed in, so there is no identity access token to swap
it for. Links already in inboxes stay valid for 30 days after the last send.

So `admin` is the only domain that still names `SECRET_KEY` in its descriptor,
and the HCP `secret_key` variable and the `SECRET_KEY` key of the
`carmodpicker-<env>/app` secret both stay. Retiring them is a follow-up row
whose content is replacing that link with an opaque unsubscribe id or something
the identity service can issue.

## Migration facts carried forward

**Password hashes copy verbatim.** One bcrypt implementation on both sides, cost
12, 72 byte truncation applied identically on hash and on verify. No user resets
a password. OAuth-only accounts are a skip rather than a failure, and the
migration summary counts them separately so it does not look like data loss.

**TOTP seeds are sealed, not rotated**, so no authenticator is re-enrolled. The
plaintext is not cleared until the sealing is verified. A seed never reaches a
log.

**Recovery codes did not exist before**, so every enrolled TOTP user should be
prompted to generate a set at first login after the cutover. The codes are shown
once, in the activation response, and never again.

## Gateway enforcement

Enforcement has been on in staging since 2026-09-11. The authorizer environment
measures **396 bytes with all 95 keys enforced**, against 4545 bytes for the
attempt that failed the 4KB Lambda environment ceiling. The fix shipped in
`staging-access-gate` 2.11.0: the route key list and the signing public key PEM
travel in the authorizer's deployment package as `identity_jwt_config.json` and
are read at import time, so the ceiling is removed rather than raised.

Verified through the staging gateway with the origin-verify header and no bearer
token: `GET /api/build-lists/user/me` is refused by the authorizer with 403
`{"message":"Forbidden"}` before reaching application code, while the two
anonymous guard routes `GET /api/reports/count` and `GET /api/bug-reports/count`
still answer 200. `docs/identity-migration-runbook.md` carries the execution
record.

Two constraints worth knowing before adding route keys: a route key may not end
in a slash, and prefix matching is unsafe here because of the two anonymous
guard routes.

## Open questions for the owner

1. **`session_expire_minutes`.** A shipped user-facing setting spanning 15
   minutes to 7 days, against a package that fixes the access token at 10
   minutes with a one hour cap. Reinterpret it as a per-user refresh lifetime,
   or drop the setting and its UI?
2. **Chrome extension authentication.** The handoff gives the worker a raw
   bearer token, and the refresh half is an httpOnly cookie an extension cannot
   read. Its own refresh family (new package surface), or `host_permissions`
   plus the `cookies` permission (one manifest change, wider grant)?
3. **OAuth auto-link.** The standard permits auto-linking when both emails are
   verified; CarModPicker today always demands the account password.
4. **Passkeys.** `passkeys_enabled` and `passkeys_passwordless` both default
   `false` in production, so passkey sign-in is not part of the production
   verification at any step. That is expected, not a fault.
