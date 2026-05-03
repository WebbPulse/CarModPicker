# Catalog data audit — 2026-05-02

Audit of the **local** parts DB (28,205 rows from `archive_rescrape` + 60 user/scraped) against archived HTML in MinIO. Goal: surface adapter-side issues that hurt catalog accuracy. Findings are grouped by *what kind of adapter change would fix it*, so a future agent can pick up a class of issues at once.

## Severity overview

| Issue                                                | Affected rows | Affected retailers                                                                |
| ---------------------------------------------------- | ------------- | --------------------------------------------------------------------------------- |
| Missing `part_number` (legitimate, no fix needed)    | ~2,250        | Wheelsboutique (961), HRE (88), Studiorsr (678), Forgeline accessories (~150)     |
| Missing `part_number` (variant pages — multi-SKU)    | ~1,000        | A90Shop, X-Ph, Cobbtuning, Hasportperformance, Vividracing, Roadsportsupply       |
| Bad `part_manufacturer` (component noun captured)    | 25            | Atpturbo (15), Lingenfelter (8), Full-Race (2)                                    |
| Manufacturer name fragmentation                      | ~50 pairs     | catalog-wide                                                                      |
| Vehicle make captured as manufacturer                | ~1,500        | Suncoastparts ("Porsche" 1009), Bimmerworld ("Genuine BMW" 491)                   |
| Stale rows (DB predates a known adapter fix)         | unknown       | Hasportperformance (compose_name was added but 33 rows still bare-SKU named)      |

## A. Variant collapse (single page → many price-distinct SKUs)

Confirmed problem on **a90shop**: 14 of a 50-page sample have `options.selections` with 2+ entries (28%). About 70% of those carry meaningful price modifiers in the option labels (`+$33`, `+$100`, `+$250`). Examples:

* `https://www.a90shop.com/product-page/rexpeed-complete-v3-carbon-aero-kit` — Clear Coat Finish: Gloss vs `Matte +$99`. DB stores one row at $3,245.
* `https://www.a90shop.com/product-page/rexpeed-v3-forged-carbon-splitter` — 5-way Clear Coat Finish with `+$33` and `+$250` tiers.
* `https://www.a90shop.com/product-page/armaspeed-air-intake` — Graphene Coating: bare vs `+$100`.

**Other retailers with the same pattern** (DB shape suggests they have it too):

* **X-Ph** (BigCommerce Stencil) — 94/547 rows missing PN. DOM has empty `<dd data-product-sku>` precisely on multi-variant pages. BCData's top-level `sku` is null when `price.price_range` is present (i.e. variants exist). PNs live per-variant, not at the parent.
* **Cobbtuning, Vividracing, Roadsportsupply, Sheepeyrace** — high `missing_pn` rate (8–72%) with high product complexity. Likely the same pattern.

**Adapter strategy needed**: extend `parse_product_page` to return a list of `ScrapedPayload` (one per variant with materially different SKU/price). Touches `base.py` + `runner.py` + every adapter that opts in. Out of scope for a single-adapter fix.

## B. Manufacturer extraction picking up component nouns

The shared `part_manufacturer_from_title` heuristic (in `parsing.py`) is treating leading nouns from titles like `Flange, Tial 44mm…` as the manufacturer. 25 parts in the DB attached to:

```
Flange       2 parts (Atpturbo)        Flange,    9 parts (Atpturbo)
Gasket       3 parts                   Gasket,    1 part
O-ring       3 parts                   O-ring,    1 part
Thermostat   1 part                    Thermostat, 4 parts (Lingenfelter)
C5           1 part                    C5,        0 parts
```

Real manufacturer in those titles is **Tial / ATP / Mr Gasket**. The fix: `part_manufacturer_from_title` should reject any candidate that matches a small denylist of generic component nouns (`flange`, `gasket`, `o-ring`, `thermostat`, `seal`, `bracket`, `clamp`, `bolt`, `nut`, `washer`, `c5`, `c6`, `c7`, `c8`, etc.).

DB cleanup applied 2026-05-02: rows attached to these manufacturers had `part_manufacturer_id` set to NULL so the next adapter pass can reattribute correctly. The `part_manufacturers` rows themselves are kept (no FK cascade-delete needed; harmless).

## C. Manufacturer name fragmentation

Same brand stored under multiple spellings:

```
ApexI                  / A'PEX-i
Borg Warner            / BorgWarner
Deatsch Werks          / DeatschWerks
Gram Lights            / GramLights
Griot's Garage         / Griots Garage
GSC Power Division     / GSC PowerDivision
K&N                    / KN
OS Giken               / OSGiken
Power Stop             / PowerStop
Pure Turbos            / PureTurbos
RS-R                   / RSR
Stop Tech              / StopTech
Studio RSR             / StudioRSR
Super Pro              / SuperPro
Techna-Fit             / TechnaFit
Titan 7                / Titan7
Turbo XS               / TurboXS
Red Line               / Redline
Oil-Air                / Oil/Air
Fuel-It                / Fuel-It!
```

These come from **different retailers** scraping the same brand under each retailer's preferred spelling. The fix is in `parsing.py`'s manufacturer normalization layer: a small canonical alias map, applied last in `part_manufacturer_from_*`. (Out of scope right now — `parsing.py` is being heavily restructured.)

## D. Vehicle make captured as part manufacturer

* `Suncoastparts` produces 1,001 parts attributed to manufacturer `Porsche`. Suncoast is the Porsche-OEM-parts specialist; the actual brand is Porsche AG and the parts are Porsche OEM. Whether to treat that as a manufacturer or to elevate it to a vehicle-fitment field is a model decision — not strictly wrong, but it bloats the manufacturers leaderboard.
* `Bimmerworld` 491 / `Turnermotorsport` 50 / `IND` 122 / `Wheelsboutique` 156 → all attributed to `Genuine BMW`. There's also a separate `BMW` (153) — the two should consolidate.

These two retailer-class fixes need adapter-level overrides (or a shared post-processor that maps OEM-genuine values onto a canonical brand). Both adapters (`suncoastparts.py`, `bimmerworld.py`) are sensitive — Suncoast is in active modification.

## E. Hasportperformance bare-SKU names (stale rows, no code fix needed)

The current `hasport.py` adapter already composes `"<SKU> - <short description>"` for bare-SKU JSON-LD names (`_compose_name` in adapter, working correctly when re-tested against archived HTML). But the DB still has rows like `name='PR3BB'` that predate the fix. Re-running `--rescrape-url` against the affected archives would refresh all 33 of them. Affected URLs:

```sql
SELECT pl.product_url FROM parts p
JOIN part_listings pl ON pl.part_id=p.id
JOIN retailers r ON r.id=pl.retailer_id
WHERE r.name='Hasportperformance'
  AND p.name ~ '^[A-Z][A-Z0-9]{1,15}$';
```

## F. Forgeline accessory part numbers

Forgeline wheel pages extract a model code from `h1.product_title` (e.g. `AR1`). Accessory pages (`/cf-contoured-cap/p255`, `/beadlock-replacement-ring/p381`) have multi-word `h1.product_title` that doesn't match the model-code regex; the page emits no JSON-LD `Product` and no `SKU`/`Item #` on the DOM. The only stable identifier is the URL's `/p<digits>` suffix.

Suggested fix in `forgeline.py::_extract_part_number`: when no `Part #` text and no model-code H1 match, fall back to the numeric ID from the URL path (`/p255` → `"P255"`). Affects ~149 currently-empty rows.

`forgeline.py` is in active modification (41 lines added in working tree); deferred to that worktree.

## G. Duplicate parts on identical product URL

Only one observed pair:

```
https://www.a90shop.com/product-page/adro-toyota-supra-widebody-kit
  019daece-44e3-7eb3-a50d-49dca7bcbe22  ADRO - Toyota Supra Widebody Kit  (older, orphan)
  019db2dc-d482-7db9-a2fc-d9d69b6588a7  ADRO - Toyota Supra Widebody Kit  (newer, with crawled_page link)
```

The unique constraint `uq_part_listing_part_retailer (part_id, retailer_id)` prevents listing-side dupes but not part-side. Dedup pass: keep the newer row, repoint car associations, drop the older. Resolved 2026-05-02.

---

## DB cleanup applied 2026-05-02

| Action                                                       | Rows |
| ------------------------------------------------------------ | ---: |
| Spurious component-noun mfrs → set `parts.part_manufacturer_id = NULL` (Gasket, Flange, O-ring, Thermostat, C5 and trailing-comma siblings) | 25 |
| Empty `part_manufacturers` rows for those component nouns dropped | 10 |
| Manufacturer name pairs consolidated (20 majority/minority pairs; minority parts repointed to majority, minority row dropped) | 84 parts / 20 mfrs |
| ADRO Toyota Supra Widebody Kit duplicate part deleted (older orphan; car associations migrated to newer; listing/price-history dropped) | 1 |

After cleanup: 28,204 parts (was 28,205), 1,140 distinct manufacturers (was 1,160), 0 normalized-name dupe pairs.

The same source-side issues will re-emerge on next crawl unless the parsing-layer fixes (alias map, component-noun denylist) land. The findings above are intended as input for that work.
