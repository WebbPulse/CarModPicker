# Static UI assets

Place manufacturer logos and part category icons here. On startup, the backend syncs these to the storage bucket **only if they are not already present** (so you can add files locally, deploy once to seed the bucket, and later replace them via the bucket or re-sync).

## Layout

- **manufacturers/** – One file per make: `<slug>.<ext>` (e.g. `honda.svg`, `aston-martin.png`).
  - Slug: lowercase, spaces → hyphens (e.g. "Aston Martin" → `aston-martin`).
- **categories/** – One file per part category: `<name>.<ext>` (e.g. `exhaust.svg`, `suspension.png`).
  - Names match backend `part_categories_data.py`: exhaust, suspension, engine, wheels, body, interior, brakes.

Supported extensions: `.svg`, `.png`, `.webp` (tried in that order when syncing and when resolving URLs).

## Sync behavior

1. On app startup, after DB init, the app runs `sync_static_assets_to_bucket()`.
2. For each manufacturer (from `car_generations_data.CAR_GENERATIONS`) and each category (from `part_categories_data`), it checks if an object already exists in the bucket at `assets/manufacturers/<slug>.<ext>` or `assets/categories/<slug>.<ext>`.
3. If **not** in the bucket, it looks for a local file in this directory and uploads it. If multiple extensions exist locally, it uses the first found (svg, png, webp).
4. If the bucket is not configured (e.g. local dev without S3), sync is skipped.

Result: add or replace files in this directory, (re)deploy or restart the backend; only missing objects are uploaded.
