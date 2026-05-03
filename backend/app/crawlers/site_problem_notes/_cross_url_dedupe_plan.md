# Cross-URL dedupe — implementation plan

Some retailers list one physical SKU under N URLs — typically per-chassis
landing pages (Cobb's `ACCESSPORT_V3` listed for every Porsche chassis;
PRL's `PRL-HC10-CL` for Civic / Accord / Integra) and locale variants
(PRL's `/en-ca/...` parallel of every product).

Today these land as N separate `parts` rows with the same
`(part_manufacturer_id, part_number)`. The canonical-linker (`link_new_part`
in `PartService.create`) does set `canonical_part_id` so they're already
*linkable* in the data model — but the UI / build-list layer counts them
as distinct parts, and that's where the catalog-accuracy story breaks.

## Scope

From the local DB (28k parts):

* **548 rows** are in dup groups by `(manufacturer, part_number)` — the
  ceiling on "collapsible" rows.
* **382 distinct dup groups** average 2.4 rows each.
* Top retailers: PRL (234), Cobb (145), BCRacing (54), Functionwerk (47),
  Hondata (31), Full-Race (28), AMS (26), Driveshaft Shop (26).
* PRL specifically also has 43 `/en-ca/` locale duplicates (one Canada
  page per product).

## Two distinct cases

### Case 1: Locale i18n (PRL only — 43 rows)

The exact same product is listed under both `prlmotorsports.com/products/X`
and `prlmotorsports.com/en-ca/products/X`. The pages emit the same
JSON-LD with the same SKU. The canonical-linker has already linked them.

**Fix shape:** drop the `/en-ca/` variant during URL discovery in
`prlmotorsports.py::discover_product_urls` (sitemap-walk filter). Adapter-only
change. Existing `/en-ca/` rows can be deleted from the DB or repointed at
the canonical row — both safe because `canonical_part_id` is already set.

### Case 2: Per-chassis fan-out (Cobb, PRL, Functionwerk, others — ~500 rows)

The retailer puts the same SKU on N distinct car-specific landing pages
because the SKU genuinely fits N chassis. The pages are NOT duplicates —
they carry distinct titles ("Accessport for Porsche 992 Carrera"
vs "Accessport for Porsche 996 Turbo"), distinct car-attribution data,
and the user expects to find the part by searching "991.2 Carrera S"
and getting an Accessport hit.

This is **not a bug to fix** at the part-rows level. The right model is:

* **One canonical part** carrying the SKU, name (the most-generic form),
  manufacturer, etc.
* **N car_generations associations** capturing every fitment.
* **N `part_listings.product_url`s** all pointing at the same canonical
  part, so price history stays continuous regardless of which chassis
  page the crawler hits today.

Today the canonical-linker partially does this — `canonical_part_id` is set —
but the *non-canonical* rows still count toward catalog totals, search
results, and "missing" attribution. Search the catalog for "Accessport"
and you get 8 hits when the user expects 1 hit with 8 fitments.

**Fix shape (in priority order):**

1. **UI/API — count canonicals only.** Wherever the catalog aggregates
   parts (`/api/parts/search`, manufacturer leaderboard, build-list
   pickers), filter to `WHERE canonical_part_id IS NULL OR id = canonical_part_id`.
   Lowest risk; doesn't touch ingest. Surfaces the existing data
   correctly.

2. **Ingest — collapse on canonical link.** When a new scraped part
   matches an existing canonical via `(manufacturer, part_number)`,
   instead of creating a new row + setting `canonical_part_id`, merge:
   * Add the new URL as another `part_listing` on the canonical row.
   * Add the new car-generation associations to the canonical row.
   * Skip the new `parts` row entirely.

   Touches `PartService._refresh_part_from_reingest` /
   `link_new_part` in `parts.py`. Higher risk because it changes
   *what gets created* — needs careful test coverage on the ingest
   path. Also one-way: existing duplicate rows would still need a
   migration pass.

   The contract `uq_part_listing_part_retailer` (`part_id`, `retailer_id`)
   means **only one URL per retailer per canonical part** — a problem
   for Cobb's case where one canonical part should have 8 listings on
   the same retailer. The unique constraint needs relaxing OR the
   listings need a different shape (one PartListing rolling up many
   URLs, or a child `PartListingURL` table).

3. **Backfill migration.** One-shot script to walk existing dup groups,
   pick the oldest as canonical (or the one with the most car
   associations), repoint listings + car associations to canonical,
   delete the rest. Safe because `canonical_part_id` is already set.

## What NOT to change

* The `parts.canonical_part_id` design itself — it's correct; it's the
  consumer paths that don't honor it.
* Cross-retailer dedupe — same SKU across Cobb + a90shop is a separate
  problem (currently neither is canonical for the other; they're both
  canonical, linked via no relation today). Out of scope.

## Recommended order

1. **PRL `/en-ca/` discovery filter** — tiny adapter change, immediate
   43-row improvement.
2. **DB pass: delete `/en-ca/` orphans** — once the discovery filter is
   in, the existing 43 rows can be safely removed.
3. **API filter on canonical** — biggest user-visible win for the
   smallest backend change. Search/list endpoints add
   `WHERE canonical_part_id IS NULL OR id = canonical_part_id`.
4. **Schema: relax `uq_part_listing_part_retailer`** — required before
   step 5; alembic autogenerate should produce the migration.
5. **Ingest: merge into canonical** — meaningful refactor; needs
   coverage. Pair with a feature flag so the old behavior is the
   default until validated.
6. **Backfill migration** — last, after ingest is correct, so the
   cleanup doesn't get redone wrong on the next crawl.

## Validation

* Search the local UI for "Accessport" before/after: count goes from
  ~8 to 1 with 8 fitments.
* `SELECT COUNT(*) FROM parts WHERE canonical_part_id IS NULL` — the
  "real" catalog size; should track the number we report externally.
* Spot-check Cobb pages: the canonical Accessport row should list every
  Porsche chassis under `car_generations`.

## Estimated effort

* Step 1 (PRL filter): 30 min.
* Step 2 (DB pass): 30 min, gated on step 1.
* Step 3 (API canonical filter): 1 day.
* Step 4 (schema relax): 1 day (with rollout planning).
* Step 5 (ingest merge): 2–3 days.
* Step 6 (backfill): 1 day.

Total: ~1 week of focused work. Steps 1–3 together (1.5 days) deliver
most of the user-visible win and can ship without steps 4–6.
