# Implementation Plan: Part Deduplication & Retailer Price History

## Goals

1. **Deduplicate parts at creation** using reliable identifiers: brand + part number, and duplicate URLs (same page supplied twice).
2. **Maintain price history per retailer** for each part.
3. **Expose “most recently known price” per retailer** for a part.
4. **Expose “best guess” most competitive retailer** for a part (e.g., lowest current price).

## Current State Summary

### GlobalPart (current)

- **One part ≈ one retailer URL today**: Single `product_url`, single `price`, single `image_url`. Same part at another retailer is a separate `GlobalPart`.
- **Dedup today**: Only in the main global-parts create flow: duplicate `product_url` → 409 Conflict. No brand+part_number dedup. Create-and-add-part and the scraper do not use URL dedup consistently.
- **Scraper**: Creates parts with `source="scraped"`, dedups by name OR image_url only, does not set `product_url`, and uses `brand` (string) vs model’s `brand_id` (needs alignment).
- **Create-and-add-part**: Always creates a new `GlobalPart`; does not check URL or brand+part_number.

### Relevant models

- **GlobalPart**: id, name, description, price, image_url, product_url, category_id, user_id, car_id, brand_id, part_number, specifications, is_verified, source, edit_count, timestamps. Relationships: Category, User, Car, Brand, BuildListPart, Vote, Report.
- **Brand**: Part manufacturer (e.g. HKS, Borla). Not the retailer.
- **BuildListPart**: Links a build list to a GlobalPart (no price/retailer at this level).

---

## Recommended Data Model Changes

### 1. New entity: Retailer

- **Purpose**: Represent the store/site where a part is sold (e.g. A90Shop, Summit Racing). Distinct from **Brand** (part manufacturer).
- **Suggested fields**:
  - `id`, `name` (e.g. "A90Shop"), optional `domain` / `base_url`, `is_active`, `created_at`, `updated_at`.
- **Use**: Every “this part at this store” link and every price observation is tied to a retailer.

### 2. New entity: PartListing (or PartOffer / RetailerPart)

- **Purpose**: “This global part at this retailer” — one row per (global_part_id, retailer_id). Holds the canonical URL for that part at that retailer and optional latest snapshot fields for convenience.
- **Suggested fields**:
  - `id`
  - `global_part_id` (FK → global_parts)
  - `retailer_id` (FK → retailers)
  - `product_url` (unique per retailer, or unique globally if you want one URL per listing) — the product page at that retailer
  - Optional: `last_known_price_cents`, `last_price_updated_at` (denormalized from price history for fast “current” display)
  - `created_at`, `updated_at`
- **Uniqueness**: `(global_part_id, retailer_id)` unique so one listing per part per retailer. Optionally unique `product_url` (or per-retailer) to support URL-based dedup.
- **Relationship**: GlobalPart has many PartListings; Retailer has many PartListings.

### 3. New entity: PartPriceHistory (or RetailerPartPrice)

- **Purpose**: Time-series price observations for a part at a retailer.
- **Suggested fields**:
  - `id`
  - `part_listing_id` (FK → part_listings) — or (global_part_id, retailer_id) if you prefer to skip PartListing in the first iteration
  - `price_cents`
  - `observed_at` (timestamp)
  - Optional: `currency`, `availability`, `raw_value` for future use
- **Use**: All “current price” and “price history” queries and “best retailer” logic read from here (with “current” = latest by `observed_at` per listing).

### 4. GlobalPart changes (behavioral + optional schema)

- **Stop storing “single” price/URL on GlobalPart for retailer-sourced data**: Either deprecate `price` / `product_url` over time (keep for backward compatibility and user-created parts that have no retailer), or keep them as “display default” (e.g. first or best listing) populated by app logic.
- **Dedup identity**: Treat “same part” as:
  - Same **brand_id + part_number** (when both present), or
  - Same **product_url** (when adding a listing: same URL → attach to existing part/listing instead of creating a new part).
- **No schema change strictly required** on GlobalPart for Phase 1 if you add PartListing + PartPriceHistory and move retailer URL/price there; optional: add a unique index on `(brand_id, part_number)` where both are not null for dedup lookups.

---

## Deduplication Strategy at Creation

### When creating a part (API or create-and-add-part)

1. **By URL**
   - If `product_url` is provided and retailer is known (or inferred):
     - Check **PartListing** (or GlobalPart during transition) for existing row with that URL.
     - If found: **do not create a new GlobalPart**; attach to existing part (e.g. create/update PartListing and add a price history row). Return existing GlobalPart (and optionally create BuildListPart if from create-and-add-part).
2. **By brand + part number**
   - If `brand_id` and `part_number` are both provided:
     - Look up GlobalPart by `(brand_id, part_number)`.
     - If found: treat as same part — **do not create a new GlobalPart**; create/update PartListing for the given retailer + URL and add price history. Return existing GlobalPart.
3. **Conflict handling**
   - If URL matches a listing that belongs to a _different_ GlobalPart than the one identified by brand+part_number, treat as conflict and return 409 with clear message (e.g. “URL already linked to another part”).

### When scraping

1. **Resolve retailer**: Map domain (e.g. a90shop.com) to a Retailer row (get-or-create).
2. **Resolve brand**: Map scraped brand string to Brand (get-or-create by name) → `brand_id`.
3. **Dedup**:
   - First check by `product_url` (existing PartListing or legacy GlobalPart.product_url).
   - Then by `(brand_id, part_number)` if both present.
4. If match: create or update PartListing for that retailer, append PartPriceHistory.
5. If no match: create GlobalPart (with brand_id, part_number, name, etc.), then PartListing + PartPriceHistory.

---

## “Current Price” and “Best Retailer”

- **Latest price per retailer**: For a given GlobalPart, join PartListing → PartPriceHistory, take per listing the row with max(observed_at) → “current price” per retailer.
- **Best retailer**: From the above, choose retailer with minimum price (and optionally filter by availability if you add it later). Expose in API as e.g. `best_listing` (retailer name, URL, price, last_updated).

---

## API and Backward Compatibility

- **GlobalPart read**:
  - Keep returning existing fields. Optionally add `listings` (array of { retailer, product_url, current_price, last_updated }) and `best_listing` (single object) so clients can show “buy from X for $Y”.
- **Create/update**:
  - Accept optional `product_url` + `retailer_id` (or retailer name/domain) and optional `price_cents`. Backend applies dedup rules; if existing part is found, creates/updates PartListing and PartPriceHistory instead of a new GlobalPart.
- **New endpoints (optional)**:
  - `GET /global-parts/{id}/listings` — list all retailers + current price for that part.
  - `GET /global-parts/{id}/price-history?retailer_id=…` — history for one or all retailers.

---

## Implementation Phases

### Phase 1: Foundation (retailer + listing + price history)

1. **Retailer**
   - Add `Retailer` model and table.
   - CRUD or admin-only create; get-or-create by name/domain for scrapers and API.
2. **PartListing**
   - Add model: `global_part_id`, `retailer_id`, `product_url`, optional `last_known_price_cents`, `last_price_updated_at`, timestamps. Unique (global_part_id, retailer_id). Optionally unique product_url.
   - Alembic migration.
3. **PartPriceHistory**
   - Add model: `part_listing_id`, `price_cents`, `observed_at`. Alembic migration.
4. **Relations**
   - GlobalPart → PartListings; Retailer → PartListings; PartListing → PartPriceHistory. Register in `app.api.models.__init__`.

### Phase 2: Deduplication at creation

1. **GlobalPart create (and create-and-add-part)**
   - Accept optional `product_url`, `retailer_id`, and `price_cents`.
   - Dedup: by URL (PartListing or legacy GlobalPart.product_url), then by (brand_id, part_number).
   - If match: create/update PartListing, insert PartPriceHistory, return existing GlobalPart; for create-and-add-part, add BuildListPart to that existing part.
   - If no match: create GlobalPart as today; if product_url/retailer/price provided, also create PartListing + PartPriceHistory.
2. **Scraper**
   - Map domain → Retailer (get-or-create). Map brand string → Brand (get-or-create) → brand_id.
   - Set product_url from scraped URL.
   - Use same dedup (URL, then brand_id+part_number); on match update listing + price history; on no match create GlobalPart + PartListing + PartPriceHistory. Fix scraper to use brand_id (from Brand lookup) instead of raw brand string where the model expects brand_id.

### Phase 3: “Current price” and “best retailer”

1. **Queries**
   - Helpers: “current price per listing” (latest PartPriceHistory per PartListing), “best listing” for a part (min price among current prices).
2. **GlobalPart read**
   - Add optional expand or separate endpoint to include `listings` (with current price) and `best_listing`. Backfill `last_known_price_cents` / `last_price_updated_at` on PartListing when writing price history for fast reads.
3. **List endpoints**
   - Optionally support filtering/sorting by “lowest current price” or “has listing from retailer X”.

### Phase 4: Migrate legacy data (optional)

1. **Existing GlobalPart rows**
   - For each GlobalPart with `product_url` set: create a Retailer (e.g. “Unknown” or infer from URL domain), create PartListing (global_part_id, retailer_id, product_url), append PartPriceHistory from current `price` and `updated_at` if price is set.
2. **Deprecation**
   - Once clients use listings/best_listing, consider making `price`/`product_url` on GlobalPart optional or derived-only.

---

## File / Area Checklist

- **Models**: `backend/app/api/models/retailer.py`, `part_listing.py`, `part_price_history.py`; update `global_part.py` (relationships only if no column changes); `__init__.py`.
- **Schemas**: Pydantic for Retailer, PartListing, PartPriceHistory; extend GlobalPart read/create/update for optional retailer/URL/price and for `listings`/`best_listing`.
- **Endpoints**: Retailer CRUD or admin-only; GlobalPart create/update dedup logic; optional `GET /global-parts/{id}/listings` and price-history.
- **Services**: Dedup logic can live in a small “PartDedupService” or inside GlobalPartService; scraper and create-and-add-part call the same dedup + listing/price logic.
- **Migrations**: One migration per new table; one optional for unique index on GlobalPart (brand_id, part_number) and for backfilling PartListing/PartPriceHistory from existing product_url/price.
- **Tests**: Dedup by URL, dedup by brand+part_number, create listing + price history, “current price” and “best retailer” queries, scraper and create-and-add-part integration.

---

## Summary

- **New entities**: **Retailer** (store), **PartListing** (part at retailer + URL), **PartPriceHistory** (time-series prices).
- **Dedup**: At creation, by **product_url** first, then by **(brand_id, part_number)**; reuse existing GlobalPart and attach PartListing + PartPriceHistory when matched.
- **Price and best retailer**: Stored in PartPriceHistory; “current” = latest per listing; “best retailer” = listing with minimum current price. Expose via GlobalPart read or dedicated listing/price-history endpoints.

This keeps GlobalPart as the single “logical part” and moves retailer-specific URL and all prices into PartListing and PartPriceHistory, with a clear path for backward compatibility and scraper/API alignment.
