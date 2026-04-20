# IND Distribution (ind-distribution.com)

**Platform:** Shopify + Booster Apps SEO plugin. **Fetcher tier:** 0 / `http`.

## What works

- Plain `requests` with a normal User-Agent returns full HTML; Cloudflare fronts the site but does not challenge.
- Booster Apps SEO injects a clean JSON-LD `Product` block at the very top of `<head>` (name, `brand.name`, `sku`, `mpn`, description, `offers` array, `image`). The shared `extract_json_ld_product` finds it first and that's the authoritative source.
- A second `ProductGroup` JSON-LD block with `hasVariant[]` appears further down the page. We don't use it today — the `Product` block already has everything we need.
- Discovery: standard Shopify sitemap index at `/sitemap.xml` pointing at `sitemap_products_N.xml` children plus pages/collections/blogs sitemaps we skip.

## Brand handling

IND is a **multi-brand retailer**. JSON-LD brand is the actual part manufacturer (LCK, Dinan, Akrapovic, KW, Eventuri, etc.), so we pass it through unchanged. Do **not** rewrite brand to "IND" / "IND Distribution" the way an in-house retailer adapter (like ADRO) would — that would destroy the useful information.

The title-heuristic fallback sometimes returns the lead token when a title opens with the target vehicle (e.g. `BMW G87 M2 …`). For those we drop the value rather than pick a house brand, because the honest answer is "unknown" — IND could be selling any of dozens of manufacturers' parts and we can't guess.

## Product-URL shape

`https://ind-distribution.com/products/<handle>[?variant=<id>]` — variant query param is optional; the same handle serves the product page regardless.

## Robots / policy

`robots.txt` carries a prose policy forbidding *automated checkout completion* ("buy-for-me" agents). The crawler only reads product pages, so that constraint doesn't apply. Standard `Disallow` rules are respected by our shared robots parser.
