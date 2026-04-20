# Wheels Boutique (wheelsboutique.com)

**Status:** adapter shipped 2026-04-19 as Tier-0 plain-HTTP
(`tier0_http/wheelsboutique.py`).

The `RETAILER_BACKLOG.md` entry put WB in the Priority-3 wheel tier above
Mackin for HRE / ANRKY / Forgeline / Vossen pricing. Reality check: the
site is a **catalog-only, lead-gen WordPress storefront** — there are no
prices anywhere on product pages. Every page has a "Request a Quote"
button that opens a vTiger lead form. Shipping the adapter anyway because
the wheel-catalog coverage (HRE, ANRKY, Forgiato, BBS, iPE, AG Luxury,
Rotiform, TechArt, 1886) is a meaningful expansion of the
manufacturer/model index we show in build lists even without a price
tag; when the user eventually compares across retailers, the row exists
with a `null` price rather than being absent.

## Platform

WordPress 6.9.4 on a custom theme (`webtista`). Tailwind CSS; no
WooCommerce, no Shopify, no JSON-LD `Product` block. Nginx origin, HTTP/2,
no Cloudflare. vTiger form submissions post to
`/wp-admin/admin-ajax.php` — not relevant to the crawler.

## Probe results, 2026-04-19, browser UA

| Path                                                     | HTTP | Notes                                               |
| -------------------------------------------------------- | ---- | --------------------------------------------------- |
| `/robots.txt`                                            |  200 | Allows all; points to `/custom-sitemap.xml`.        |
| `/sitemap.xml`                                           |  301 | Redirects to `/wp-sitemap.xml` (which returns 404). |
| `/wp-sitemap.xml`                                        |  404 | The WP default sitemap is disabled.                 |
| `/custom-sitemap.xml`                                    |  301 | Redirects to `/custom-sitemap.xml/` (trailing `/`). |
| `/custom-sitemap.xml/`                                   |  200 | Sitemap index; 6 child sitemaps.                    |
| `/custom-sitemap-wheels.xml`                             |  200 | **Not listed in the index.** ~935 wheel URLs.       |
| `/custom-sitemap-exhausts.xml/`                          |  200 | ~25 exhaust URLs.                                   |
| `/wheels/hre-wheels/520-series/hre-520/`                 |  200 | Product page, plain HTML.                           |

Tier-0 plain HTTP is sufficient. `requests` follows the 301s transparently
so the adapter targets the un-slashed paths.

## Sitemap oddity: wheels aren't in the index

`/custom-sitemap.xml/` indexes six children:

```
posts       — blog / "featured vehicle" articles
pages       — CMS pages (about, privacy, …)
taxonomies  — tag / brand / gallery category pages
exterior    — currently empty urlset
exhausts    — ~25 product URLs
gallery     — vehicle gallery posts
```

There's no `wheels` entry, but `/custom-sitemap-wheels.xml` exists at the
predictable path and contains ~935 wheel product URLs. The adapter fetches
this file explicitly in addition to walking the index, so wheels —
which are the actual reason for including this retailer — aren't missed.

## Product URL shapes

Wheels: two depths, both valid.
- `/wheels/<brand-slug>/<series-slug>/<model-slug>/` — 897 of 935.
- `/wheels/<brand-slug>/<model-slug>/` — 38 of 935 (all return 404; they
  look like orphan sitemap entries that have since been removed).

Exhausts: always `/exhausts/<slug>/` (1 segment after `/exhausts/`).

The adapter's `_is_product_url` accepts wheels with ≥2 path segments after
`/wheels/` (3 total including `wheels`) and exhausts with exactly 1
segment after `/exhausts/`. The stale 2-segment wheel URLs are allowed
through because the sitemap lists them, but they return 404 — the runner
drops those on fetch.

## Product page shape (no price, no JSON-LD, no SKU)

| Field         | Source                                               | Notes                                                                                             |
| ------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Name          | `<h1>` inside `<main>`                               | Matches og:title for every product inspected. og:title is the second-choice fallback.             |
| Description   | `main .prose` (the "Product Description" body)       | Often **empty** on wheel pages. Adapter falls back to og:description → meta description.          |
| Price         | —                                                    | **Not present on any product page.** Entire catalog is "Request a Quote."                         |
| Brand (wheel) | URL segment `/wheels/<brand-slug>/…`                 | Only reliable source on the page. Curated `_WHEEL_BRAND_DISPLAY` map for casing (HRE, iPE, etc.). |
| Brand (exh.)  | token match on `iPE` in name/description             | WB's exhaust taxonomy is iPE-only today (`/exhaust-brand/ipe-exhaust/`); every exhaust page       |
|               |                                                      | emits the literal string "iPE" in the description. No brand label surfaced in the DOM.            |
| Part number   | —                                                    | Not surfaced anywhere on the page. `part_number=None`.                                            |
| Image         | og:image                                             | Wheel pages render a "More wheels on: <series>" row of other-product thumbnails; a broad `<img>`  |
|               |                                                      | sweep would pull those in. Adapter takes the hero og:image only.                                  |

## On `price_cents=None`

`ScrapedPayload.price_cents` is `Optional[int]` and
`create_or_update_listing_and_price` treats `None` as "listing exists,
don't append to PartPriceHistory." That's the correct behavior here — we
want the manufacturer/model row in the catalog so build-list UI can show
"available at Wheels Boutique" with a "request quote" link, without
polluting price history with synthetic zeros or placeholders.

If WB ever publishes prices (or adds a published-MSRP field), revisit the
adapter to populate `price_cents` and stop short-circuiting the extractor.

## Brand-slug → display-name heuristic

Known slugs:

```
1886-wheels           → 1886
ag-luxury-wheels      → AG Luxury
anrky-wheels          → ANRKY
bbs-wheels            → BBS
forgiato-wheels       → Forgiato
hre-wheels            → HRE
ipe-wheels            → iPE
rotiform-wheels       → Rotiform
techart-wheels-porsche → TechArt
```

Unknown slugs fall through to: strip trailing `-wheels` (and any suffix
like `-porsche`), replace `-` with space, title-case. e.g.
`vossen-wheels` → `Vossen`. This is future-proofing for brands WB may
add — the backlog note explicitly calls out HRE, Vossen, ANRKY,
Forgeline; Vossen and Forgeline aren't currently in the catalog.
