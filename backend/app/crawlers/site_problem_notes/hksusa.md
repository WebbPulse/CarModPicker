# hksusa.com

First-party brand site (HKS USA), Next.js 13 App Router on Vercel, backed by a
Strapi CMS. Plain `requests` passes — no Cloudflare / managed JS challenge.
Tier 0.

## Product URL shape

`https://hksusa.com/product/<CODE>` where `<CODE>` is the HKS part number,
e.g. `11003-AN020`, `80300-AA005C`, `51007-AK618`. Single path segment,
alphanumeric + `-` / `.`.

## Discovery

`/sitemap.xml` is a single flat urlset (~2k entries). Mixed content —
`/product/<code>`, `/category/<N>`, `/category/subcategory/<N>`, `/featured/…`,
`/productlist/…`, and the usual CMS pages. Filter on `/product/<code>`.
~1.9k product URLs.

No sitemap index, no pagination, no brand/category split by file — a single
fetch is enough.

## Parsing — the RSC problem

The tricky part of this storefront. There is **no JSON-LD `Product` block**,
and og:* carries only `og:title` / `og:image`. Every other useful field (MSRP,
remarks copy, part code linkage, chassis tags) lives inside the Next.js
React Server Components streaming payload:

```
self.__next_f.push([1,"… product record …"])
```

That payload is **JSON embedded inside a JS string literal**: every inner
double-quote appears as `\"` in the HTML source. The format is RSC's custom
stateful stream (tree-shaped refs like `$La`, `$L26`, typed rows like
`c:[…]`) — not directly `json.loads`-able without reimplementing Next's
`flight` decoder.

So the adapter uses **targeted regexes anchored on the URL's part code**
instead of a full parse:

- Name: `\"name\":\"<X>\",\"code\":\"<URL_CODE>\"` — the `,\"code\":\"<CODE>\"`
  suffix disambiguates the current product from related-product records that
  ride along on the same page (`featured_cars_products`, subcategory sibling
  lists, etc.).
- Description: pull `\"remarks\":\"…\"` from the same code-anchored record.
  `product_description` on this CMS is pure HTML wrapping product-sheet
  images with no body text, so `remarks` is the only human-readable copy
  worth promoting.
- MSRP: `\"msrp\":N` inside the `product-unit.product-unit-us` component.
  **Whole USD, not cents** — the only HKS-specific conversion gotcha.
  Multiply by 100 before returning.
- Hero image: `og:image` — points at the original-size JPG on the Strapi
  media host (`cheerful-bouquet-*.media.strapiapp.com`). Resized variants
  (`large_`, `medium_`, …) live under `formats.*` in the RSC blob and are
  not worth the extra parsing for a catalog thumbnail.

The RSC payload duplicates the product record (once inline in the HTML,
once via a streaming patch). Both copies carry the same `msrp`, so picking
the first regex match is fine.

## Brand policy

First-party site — every SKU is HKS-manufactured. Hardcode `HKS` as the
manufacturer; there is no per-product brand field and nothing on-site to
disambiguate co-branded SKUs (unlike ECS / FCP, HKS doesn't resell other
lines). If HKS ever adds a licensed/OEM line, we can revisit.

## URL character of the part code

The HKS part code in the URL path **is** the canonical part number — no
"Product Code:" row in the DOM to cross-check against. Feed the URL segment
through `normalize_part_number` (same as every other adapter) and use it
directly.
