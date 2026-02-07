# Scraping at Scale: Retailer Crawlers Architecture

## Summary

Use **per-retailer crawlers** built on a **shared base**: one interface and pipeline for fetching, parsing, and ingesting, with **retailer-specific adapters** that handle URL discovery and page structure. This matches the fragmented auto-parts retail landscape and keeps page-specific logic explicit and maintainable.

---

## Why per-retailer?

- **Page structure varies heavily**: JSON-LD, meta tags, and DOM selectors differ by site (and sometimes by section within a site). A single “generic” scraper is brittle and hard to tune.
- **Discovery differs**: Some retailers have sitemaps, category pages, or search APIs; others are mostly product links. Each needs its own strategy.
- **Policies and limits**: Rate limits, robots.txt, and optional auth vary by retailer. Per-retailer config keeps this clear.
- **Ownership**: One code path per retailer makes it obvious where to fix breakage when a site changes.

A shared base gives you consistent output shape, retries, dedup, and API integration; adapters give you reliability per site.

---

## Recommended architecture

### 1. Shared base (single pipeline)

- **Output contract**: All crawlers produce the same **scraped payload** your API already expects:
  - `name`, `description`, `price` (cents), `product_url`, `brand` (string), `part_number`, `image_url`, `image_urls`, optional `gtin`
- **Responsibilities of the base**:
  - HTTP fetching (with backoff, timeouts, optional proxy)
  - Retry and basic error handling
  - Mapping `brand` string → Brand (get-or-create) and domain → Retailer (get-or-create)
  - Calling existing **GlobalPart create** (or a dedicated “crawler ingest” endpoint) so dedup (URL, brand+part_number, GTIN) and PartListing/PartPriceHistory stay in one place
- **No page parsing in the base**: Parsing is entirely in retailer adapters.

### 2. Per-retailer adapters

Each retailer has a small module that implements a simple interface, e.g.:

- **URL discovery**: Given a retailer config (base URL, categories, etc.), yield product page URLs (sitemap, category listing, search, or a fixed list).
- **Parse product page**: Given HTML (and optionally response URL), return the common scraped payload above.

Adapter responsibilities:

- Selectors, JSON-LD paths, or regex for that site
- Normalizing price (currency, “from $X”, multi-option)
- Normalizing brand/part number (where they put it in title vs schema vs table)
- Handling pagination or “load more” if you need it for discovery

You can derive adapters from a **base class or protocol** that only defines:

- `discover_product_urls() -> Iterator[str]` (or async)
- `parse_product_page(html: str, url: str) -> ScrapedPayload | None`

So the base stays generic; all site-specific logic lives in the adapter.

### 2b. Central brand list

**Brands are a single shared resource.** The database is the only source of truth: the chrome extension, the API, and all crawlers use the same Brand table. The ingest pipeline calls `get_or_create_brand_by_name(db, brand_name)` so a brand is only created once; any crawler or the extension that submits "Rays" will get the same brand_id. You never need to define a brand in more than one place—edit or add brands in the app and they apply everywhere.

### 3. Where to put crawlers

- **Option A – Inside this repo (e.g. `backend/crawlers/` or `scripts/crawlers/`)**
  - Pros: Single repo, can reuse `part_listing_service`, DB session, config.
  - Cons: Crawlers need to run somewhere (cron, worker); you may want to keep heavy/scheduled jobs out of the main app process.
- **Option B – Separate service/repo**
  - Pros: Independent scaling, language choice (e.g. Python + Playwright for JS-heavy pages).
  - Cons: Duplicates config and must call your API (with auth) for ingest; you already have the ingest logic in this backend.

A practical approach: implement the **crawler core and adapters in this repo** (e.g. `backend/crawlers/`), and run them via **scheduled jobs** (cron, Celery, or a small worker process) that use the same DB or call your existing HTTP API. If you later need a different runtime (e.g. serverless or another language), the **adapter contract** (discover URLs + parse page → payload) still holds; only the runner changes.

### 4. Ingest path: reuse what you have

Your API already:

- Deduplicates by `product_url`, `(brand_id, part_number)`, and `gtin`
- Gets-or-creates Retailer by domain and Brand by name
- Creates/updates PartListing and PartPriceHistory when `retailer_id` + `product_url` and optionally `price_cents` are provided

So crawlers should:

1. Resolve **retailer** from product URL domain (e.g. `/retailers/get-or-create` with domain).
2. Resolve **brand** from scraped brand string (get-or-create by name in `part_listing_service` or a small helper used by the crawler).
3. Call **POST /global-parts** (or a dedicated ingest endpoint) with:
   - `product_url`, `retailer_id`, `price_cents`, `brand_id` (from step 2), `part_number`, `name`, `description`, `image_url`/`image_urls`, optional `gtin`
   - `source="scraped"`

If you prefer crawlers to run without a real “user”, add a **crawler-only endpoint** or an API key that maps to a system user and reuses the same create + dedup + listing logic. That keeps a single code path for create/dedup/listing.

### 5. Operational considerations

- **Rate limiting**: Per-retailer delay (e.g. 1–2 s between requests) and optional per-domain limits. Respect `robots.txt` and cache it.
- **Identification**: Use a consistent User-Agent (and optionally identify as your project) so retailers can contact you if needed.
- **Scheduling**: Run retailers on different schedules if needed (e.g. high-value partners more often). Start with a small set of URLs per retailer to validate before scaling discovery.
- **Monitoring**: Log parse failures, HTTP errors, and dedup hits so you can spot site changes and tune selectors.
- **Headless vs static**: Many part pages are server-rendered; `httpx`/`requests` + HTML parsing may be enough. For JS-heavy product pages, use a per-retailer decision (e.g. Playwright only where necessary) so you don’t pay the cost everywhere.

---

## Suggested layout (in this repo)

```text
backend/
  crawlers/
    __init__.py
    base.py          # ScrapedPayload dataclass, fetch + ingest pipeline (no parsing)
    runner.py        # Optional: run adapter.discover → fetch → adapter.parse → ingest
    adapters/
      __init__.py
      base.py        # Protocol or ABC: discover_product_urls, parse_product_page
      summit_racing.py
      a90shop.py
      # one module per retailer
```

Each adapter is focused: discovery + parsing for that retailer. The base handles fetch, retries, retailer/brand resolution, and API calls. You can then wire `runner` to a cron job or a Celery task that runs “all active retailers” or a specific list.

### Running the crawler (CLI)

From the **backend** directory:

```bash
python -m app.crawlers --adapter <name> [--limit N] [--delay SEC]
```

**Required env:**

- `CRAWLER_USER_ID` – User ID to attribute created parts to (must have create permission, e.g. premium).
- `CRAWLER_DEFAULT_CATEGORY_ID` or `CRAWLER_DEFAULT_CATEGORY_NAME` – Category for new parts (e.g. `exhaust`). If unset, the first active category in the DB is used.

**Example (A90 Shop PoC):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=wheels
python -m app.crawlers --adapter a90shop --limit 5
```

The `a90shop` adapter discovers URLs from `CRAWLER_A90SHOP_START_URLS` (comma-separated) or a default list including the sample product page. The `example` adapter yields no URLs.

---

## Why not Scrapy (or similar)?

We didn’t use Scrapy (or Playwright-based frameworks) by design:

- **Lightweight stack**: A small shared base + per-retailer adapters with `requests` + BeautifulSoup keeps the stack simple and avoids a large framework dependency. Adding a new retailer is “one adapter file” without learning Scrapy items, pipelines, and middleware.
- **Tight coupling to your API**: Ingest is “call GlobalPart create + PartListing/PartPriceHistory” with your existing dedup and subscription checks. That’s a single function call from the runner; a Scrapy pipeline would still need to call the same logic (or your HTTP API), so the framework doesn’t simplify ingest.
- **Scheduling and scale**: Scrapy shines when you need built-in scheduling, concurrency, and broad crawling. We don’t need those for a small set of retailers yet; the runner is “run one adapter, optionally with --limit.” If you later need scheduling or high concurrency, you can introduce Scrapy (or Celery + our adapters) and keep the same adapter contract (discover URLs, parse page → payload).

So the limitation isn’t that existing frameworks prevent us—we chose a minimal design that matches current needs. You can adopt Scrapy later if you want its scheduler and middleware without changing the “one adapter per retailer” idea.

---

## Conclusion

Use a **shared base** for fetch, ingest, and dedup, and **per-retailer adapters** for URL discovery and page parsing. That keeps scaling manageable, makes site-specific logic explicit, and reuses your existing part/listing/price model and API without duplication.
