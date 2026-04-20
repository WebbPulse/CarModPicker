# Texas Speed & Performance (texas-speed.com)

**Status:** Tier-1 TLS adapter committed. Investigation 2026-04-19.

## Platform

Magento 2 on the Hyva frontend theme (CSS path
`/static/.../frontend/Dcw/Eah_hyva/en_US/...`). Product URLs are
`url_key`-style but nested under a brand segment:
`https://www.texas-speed.com/brand/<brand-slug>/p-<sku-slug>/` with a trailing
slash (not the vanilla Magento `/<slug>.html` shape). Category / CMS pages do
not fit this pattern, so the URL regex is a positive product identifier, not
just a shape guard.

## Fetch blocker: Cloudflare interactive challenge

Every path except `/robots.txt` returns a Cloudflare `Just a moment…`
challenge to plain `requests` and to curl with a full current-Chrome header
set (UA, `Sec-Ch-Ua*`, `Sec-Fetch-*`, `Accept-Language`, `Accept-Encoding`).
`curl_cffi` with `impersonate="chrome"` clears the handshake (confirmed on a
live product page, sitemap index, and every child sitemap), so
`FETCHER_TIER = "tls"`. Same pattern as Cobb / Turner / Vivid. If the
challenge escalates to a managed JS challenge, promote `FETCHER_TIER` to
`"browser"` without touching the parser.

Probe, 2026-04-19, browser UA, plain curl → all 403:

| Path                                | plain curl | curl_cffi chrome |
| ----------------------------------- | ---------- | ---------------- |
| `/robots.txt`                       |    403     | 200              |
| `/sitemap/sitemap.xml` (index)      |    403     | 200              |
| `/media/sitemap/sitemap-1-1.xml`    |    403     | 200              |
| `/brand/<brand>/p-<sku>/` (product) |    403     | 200              |

## robots.txt highlights

The default Magento 2 block list, with one addition worth calling out:
`Disallow: /*?` — **any URL with query params is off limits.** Product URLs
have no query string in the sitemap, and `canonicalize_url()` strips known
tracking params, but `_is_product_url()` also rejects anything with a
remaining query on top of that.

Other standard-Magento disallows: `/lib/`, `/*.php$`, `/pkginfo/`, `/report/`,
`/var/`, `/catalog/`, `/customer/`, `/sendfriend/`, `/review/`, `/*SID=`,
`/newsletter/subscriber/new/`, `/checkout/`, `/onestepcheckout/`. None
overlap the `/brand/.../p-.../` product path.

## Two sitemaps, only one is real

There are two Magento sitemap paths served on this origin, and they disagree:

1. **`/sitemap.xml`** — 200 OK, ~23k URLs, **all pointing at
   `https://mcprod.texas-speed.com/<slug>.html`**. The `mcprod` host 302s to
   `https://www.texas-speed.com/<slug>.html`, and every one of those 302
   targets is a Magento `no-route` 404 on the live site. This is a stale
   export from an earlier Magento instance that was never repointed. **Do not
   use.** Adapters that probe the default `/sitemap.xml` location will walk
   23k dead URLs.

2. **`/sitemap/sitemap.xml`** — the real sitemap **index**. Points at
   `/media/sitemap/sitemap-1-<N>.xml` child urlsets (four at time of writing,
   ~5000 URLs each, ~17.5k products total). URLs use the canonical
   `/brand/<slug>/p-<slug>/` shape and resolve 200 on `www.texas-speed.com`.

The adapter hardcodes `/sitemap/sitemap.xml` as `SITEMAP_INDEX_URL` and does
not fall back to `/sitemap.xml`.

## Part-number field choice: prefer `mpn` over `sku`

Every product page emits JSON-LD with both `sku` and `mpn`, and they are not
interchangeable:

| Product                                   | sku                   | mpn           |
| ----------------------------------------- | --------------------- | ------------- |
| TSP "Chopacabra" Truck Cam                | `TSP-CHOPacabra`      | `CHOPacabra`  |
| PRW Water Pump Pulleys 2634600            | `PRW-2634600`         | `2634600`     |
| GM 58x Reluctor Wheel                     | `GM-12586768`         | `12586768`    |
| Procharger 2011-18 RAM 1500 … Tuner Kit   | `PRO-1DH305-SCI`      | *(missing)*   |

`sku` is Texas Speed's brand-prefixed retailer SKU; `mpn` is the clean
manufacturer part number that other retailers (Summit, Jegs, Amazon) also
carry. Using `sku` as `part_number` would defeat cross-retailer dedupe on
`(part_manufacturer, part_number)` — the same Chopacabra cam sold at Summit
would never match the Texas Speed row.

The adapter therefore reads `mpn` first and only falls back to `sku` when
`mpn` is absent (rare — mostly composite / bundle SKUs like the Procharger
kit above). Shared `scraped_payload_from_json_ld` defaults to
`sku or mpn`; this adapter re-runs the preference in the reverse order.

## Gallery images live in a Hyva JSON array, not JSON-LD

JSON-LD `image` ships only the main `_1.jpg`. Multi-image products serialize
the full gallery as a standard JSON array under an Alpine `x-data` expression:

```js
"images": [
  {"thumb": "...", "img": "...", "full": "...",
   "caption": "...", "position": "1", "isMain": true,
   "type": "image", "videoUrl": null},
  ...
]
```

`_extract_gallery_full_urls()` locates the `"images": [` marker and walks
bracket depth (ignoring contents inside quoted strings) to find the array
boundaries, then `json.loads` it and emits the `full` URLs in `position`
order. Adapter falls back to JSON-LD `image` when the gallery JSON is absent
(single-image products, or soft-404 landing pages where the Alpine block is
missing).

The `full` URLs have Hyva's optimizer query string preserved
(`?optimize=high&bg-color=255,255,255&fit=bounds&…`) — we pass it through
because stripping it yields a different, un-optimized CDN path.

## Default manufacturer

Texas Speed is a multi-brand storefront — the overwhelming majority of
products carry a JSON-LD `brand.name` (Procharger, PRW, GM, Whipple,
Magnaflow, Pedders, Point One, Wegner Motorsports, …). The default only
fires on the rare page where `brand` is missing; when that happens the
adapter assigns `"Texas Speed & Performance"` rather than running the
title-first-word heuristic, which would pick up product words like `"Stage"`
or `"Camshaft"` as a manufacturer.
