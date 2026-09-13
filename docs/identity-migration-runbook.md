# Identity migration runbook

The scripts that move existing credentials and second factors into the identity
tables, the order they run in, and what each one refuses to do.

`docs/prod-promotion-plan.md` is the authority for the production sequence.
This document is the script reference that plan Steps 4, 5, 14, 15 and 16 call
into. Where the two disagree, the plan is correct.

Neither script is part of a deploy. Both are run by hand, per environment.

## What each script does

| Script | Reads | Writes |
|---|---|---|
| `backend/scripts/migrate_credentials_to_identity.py` | `users.hashed_password` | `credentials` rows, one per password account |
| `backend/scripts/migrate_totp_seeds_to_identity.py` | `users.totp_secret`, `users.totp_enabled` | `totp-factors` rows, sealed under KMS |
| `backend/scripts/clear_legacy_credentials.py` | `users`, `credentials`, `totp-factors` | removes `hashed_password` and `totp_secret` from user rows |

Neither migration script changes the `users` table. The TOTP script's separate
`--clear-plaintext` pass does, and is never run in the same command as sealing.

## Prerequisites

- The `credentials` and `totp-factors` tables exist and the `identity-data` KMS
  key exists, and the identity function is deployed so it reads what these
  scripts write.
- `DYNAMODB_TABLE_PREFIX` (or `--prefix`) set to the environment's prefix, for
  example `carmodpicker-staging`, with **no trailing hyphen**: the repository
  supplies the separator, so a trailing hyphen resolves to
  `carmodpicker-<env>--users` and the scan fails with
  `ResourceNotFoundException`.
- `IDENTITY_DATA_KEY_ARN` (or `--data-key-arn`) set to that environment's
  `identity-data` key, for the TOTP script only. A different key produces rows
  that decrypt nowhere.
- Credentials with `dynamodb:Scan` on `users`, read and write on the two
  identity tables, and `kms:GenerateDataKey` plus `kms:Decrypt` on the data key.
- Both `AWS_REGION` and `AWS_DEFAULT_REGION` exported.
  `migrate_totp_seeds_to_identity.py` builds its KMS client without threading
  `--region` through and raises `NoRegionError` otherwise.

## Flags that exist

Verified against the scripts. All three take `--prefix`, `--endpoint-url`,
`--region` and `--apply`. Beyond that: the two migration scripts take
`--replace`, the TOTP script alone takes `--data-key-arn` plus the mutually
exclusive `--verify` and `--clear-plaintext`.

There is **no force or overwrite flag on any of them.** `--replace` is the only
way to rewrite an existing row, and it rewrites only the rows it is pointed at,
preserving the original `created_at`.

`--prefix` writes itself back into `DYNAMODB_TABLE_PREFIX`, because the legacy
users repository reads that setting rather than the flag. One flag selects the
environment for both tables.

## Order of operations

Every step is a dry run first. Nothing writes without `--apply`. Run from
`backend/`, with `P=--prefix=carmodpicker-<env>`.

```
# 1. Credentials, dry run. Read the summary before going further.
python scripts/migrate_credentials_to_identity.py $P
# 2. Credentials, applied.
python scripts/migrate_credentials_to_identity.py $P --apply

# 3. TOTP seeds, dry run.
python scripts/migrate_totp_seeds_to_identity.py $P
# 4. TOTP seeds, sealed. The plaintext on the user row is left alone.
python scripts/migrate_totp_seeds_to_identity.py $P --apply
# 5. Verify every sealed seed opens and matches. Writes nothing, exits non-zero
#    if anything is missing, unreadable or mismatched.
python scripts/migrate_totp_seeds_to_identity.py $P --verify

# ---- the cutover happens here ----

# 6. One-way door. Only once the row 13 gate holds and step 5 exited zero.
python scripts/migrate_totp_seeds_to_identity.py $P --clear-plaintext
python scripts/migrate_totp_seeds_to_identity.py $P --clear-plaintext --apply

# 7. One-way door. Same gate. Dry run immediately before the apply, every time.
python scripts/clear_legacy_credentials.py $P
python scripts/clear_legacy_credentials.py $P --apply
```

Steps 1 to 5 are reversible: every legacy value stays exactly where it was, so
the identity rows are inert and deleting them restores the prior state exactly.
Steps 6 and 7 are not reversible. After them the sealed copy and the
`credentials` table are the only copies, and the only restore is the snapshot
taken before the promotion began.

## The row 13 gate

`docs/prod-promotion-plan.md` Step 14 is the authority for this precondition.
What follows is the mirror of it, kept here because the scripts above are what
it gates.

**Precondition, checked once rather than watched.** Step 12 has landed, the
owner has signed in through the identity path in a browser, one authenticated
write has succeeded, and the alarms are quiet:

    aws cloudwatch describe-alarms --state-value ALARM \
      --query 'MetricAlarms[].AlarmName' --output text

Expect empty.

Plan Step 13 was removed by owner decision on 2026-09-13. The soak it carried is
gone; the alarm check above is what replaced it and it runs once, at the top of
Step 14.

Plan Step 15 adds a second gate before any clearing: the owner has signed in
with a real password through the identity path in a browser, after the cutover,
not a synthetic account and not a curl probe.

## Reading the summary counts

Both migration scripts print one line per user and a `totals:` line. Read the
totals.

### Credentials

- `write` a bcrypt hash was copied into a new `credentials` row. Expected on a
  first run.
- `unchanged` a credential already holds exactly this hash. Expected on a rerun,
  and nothing was touched, `created_at` included.
- `conflict` a credential exists and holds a **different** secret. Stop, see
  below.
- `skip_oauth_only` `hashed_password` absent: a Google-only account, or one
  created through the identity flow. Normal, usually large, not data loss.
- `skip` a hash that is not a bcrypt modular crypt string of 60 characters.
  Investigate: copying it writes a credential that could never verify.

Hashes copy verbatim, both sides `webbpulse.security.hash_password`, bcrypt cost
12, the same 72 byte truncation on hash and on verify. **No user resets a
password.** The script is idempotent and preserves `created_at` on a rerun.

### TOTP seeds

- `seal` a seed was sealed into a new or corrected `totp-factors` row. Expected
  on a first run.
- `unchanged` a factor already holds this seed in this state. Expected on a
  rerun.
- `conflict` a factor exists holding a different seed, or one that will not
  decrypt. Stop, see below.
- `skip` no `totp_secret` on the user row. Normal, usually most rows.

Sealing generates an AES-256 data key from KMS under `IDENTITY_DATA_KEY_ARN` and
stores ciphertext, nonce and wrapped key. The encryption context is
`{"user_id": <id>, "purpose": "totp"}`, bound by KMS as authenticated data, so a
ciphertext copied to another row fails to decrypt rather than authenticating the
wrong person. **The seed itself is unchanged, so nobody re-enrols an
authenticator.**

`--verify` reports `verified`, `mismatch`, `unreadable`, `missing` and `skip`,
and exits non-zero if any of the middle three is non-zero.

`--clear-plaintext` reports `cleared`, `already_clear`, `refused` and `skip`. It
re-verifies each row inside the pass rather than trusting the earlier
`--verify`, and refuses any row whose sealed copy does not open rather than
destroying the last readable copy of a seed.

### On a conflict

Both migration scripts refuse the **whole run before writing anything** if any
conflict exists, and exit 1. A conflict means one of two things, and they want
opposite answers:

- A password or authenticator was changed through the identity flow after the
  cutover began. The identity row is the truth and must not be reverted.
- The run is pointed at the wrong environment's tables. Nothing should be
  written at all.

Work out which before doing anything. `--replace` says the `users` table is the
truth and overwrites. It is not a way to get past the message.

## Reading `clear_legacy_credentials.py`

Dry run by default. Nothing is written without `--apply`. Each user is
classified before anything is written, and the two columns are classified
independently.

- `cleared` at least one legacy column was removed, and every column removed had
  a confirmed replacement.
- `already_clear` neither legacy column is on the row. A second run reports every
  row this way, which is what idempotence looks like.
- `mismatch` a replacement exists but holds a different secret from the legacy
  column.
- `missing_credential` a legacy column is present and its replacement is absent.
- `errors` the write itself failed.

The last three are refusals, not warnings. **Any one of them refuses the whole
run**, the script exits non-zero having written nothing, and a refusal is a
signal to stop and read rather than to rerun.

A `mismatch` is usually benign: the identity login path opportunistically
rehashes a credential, so a user who has signed in since the cutover can hold a
credential whose bytes no longer match the legacy column. The remedy is
`migrate_credentials_to_identity.py --replace`, which rewrites only the
credential rows it is pointed at.

A `missing_credential` means either an account with no password credential at
all, or the migration has not run here. An account with **neither** column and
no credential is `already_clear` rather than a refusal: that is an OAuth-only or
passkey-only account.

Because rows can change classification between runs, the dry run that gates a
write must be the one taken minutes before it, not an earlier one.

No hash and no TOTP seed reaches the output of any of the three scripts, in any
branch. Every comparison happens in memory and is reported as a verdict.

## Executed record, staging

| Date | What ran | Result |
| --- | --- | --- |
| 2026-09-11 | `migrate_credentials_to_identity.py --prefix carmodpicker-staging`, dry run only | `write=0 unchanged=0 conflict=0 skip_oauth_only=58 skip=0`. `--apply` deliberately not run: a guaranteed no-op. |
| 2026-09-11 | `migrate_totp_seeds_to_identity.py --prefix carmodpicker-staging --verify` | `seal=0 unchanged=0 conflict=0 skip=58`. `--apply` deliberately not run. |
| 2026-09-11 | Frontend flipped to the identity path, then gateway enforcement turned on | Verified on the deployed bundle and through the gateway, not on the variable. |
| 2026-09-12 | Row 13 merged to `staging` (`bd9c9bc3`, PR 421) and applied | 0 to add, 13 to change, 0 to destroy, all in place. 20 of the 24 legacy routes answer 404; the other 4 are package routes at the same paths. Zero 5xx for 30 minutes after the deploy, all 11 staging alarms OK. |
| 2026-09-12 | `clear_legacy_credentials.py --prefix carmodpicker-staging`, dry run only | `cleared=0, already_clear=64, mismatch=0, missing_credential=0, errors=0`, exit 0. Nothing to clear. `--apply` not run. |

Staging held **no credentials at all**: zero users with `hashed_password`, zero
with `totp_secret`, zero `oauth_accounts` and `webauthn_credentials` rows, every
identity table empty. Staging was seeded from production content on 2026-09-06
and real credentials were never copied. **So both migration scripts are still
unexercised against real data and `clear_legacy_credentials.py` has never been
applied anywhere.** Treat the production run as a first application and read the
dry run output rather than skimming it.

Three `staging_access_gate` resources also show comment-only drift and ride
along in every plan, so the production cut should expect 13 changes, not 10.

## Two things not to touch while clearing

**Leave the HCP `secret_key` variable and the `SECRET_KEY` key of the
`carmodpicker-<env>/app` secret alone.** They are still read by
`GET /api/part-price-alerts/unsubscribe` on the `admin` function, and deleting
either breaks every unsubscribe link in every inbox. When the follow-up row
replaces that link, the order is: delete the `SECRET_KEY` key from the secret
first, confirm nothing 500s, then delete the HCP workspace variable and remove
`var.secret_key` from `terraform/variables.tf`.

**Expect three functions to still hold a Secrets Manager grant after the apply,
not zero.** `identity` keeps its grant to read the OAuth client secrets, `admin`
for `SECRET_KEY`, `catalog` for `EXTENSION_API_KEY`. `build-lists`,
`build-logs`, `media`, `moderation` and `users` each lose it.

The rest of the close-out, including deleting the inert `AUTH_MODE` environment
variable, is `docs/prod-promotion-plan.md` Step 17.
