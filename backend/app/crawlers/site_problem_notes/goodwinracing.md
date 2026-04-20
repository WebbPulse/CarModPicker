# Good-Win Racing (good-win-racing.com)

**Status:** Tier-1 TLS adapter committed. Investigation 2026-04-19.

## Platform

Classic Interchange (Akopia / Red Hat Perl e-commerce). Giveaways:
`<input name="mv_session_id" …>`, `<input name="mv_todo" value="refresh">`,
and the `/mazda/miata/ord/basket.html` cart path. The theme is older,
but every product page still emits a well-formed `<script type=
"application/ld+json">` `Product` block with sku, name, description,
brand.name, image, and offers.price in USD — `extract_json_ld_product()`
+ `scraped_payload_from_json_ld()` get everything the ingest layer
needs, and no DOM fallback is required on current sampling.

## Fetch blocker: Cloudflare managed challenge (TLS fingerprint only)

Probe, 2026-04-19, from local egress:

| Client                                | `/sitemap.xml` |
| ------------------------------------- | -------------- |
| `requests` + crawler UA               | 403 + `Just a moment...` interstitial |
| `curl` + Chrome UA                    | 403 + `Just a moment...` interstitial |
| `curl_cffi` `impersonate="chrome120"` | 200 |

The block is fingerprint-based (TLS ClientHello / JA3) — no JS
challenge is actually being solved on the `curl_cffi` path, just passed
by presenting Chrome-shaped TLS bytes. No cookies, no warm-up.
`FETCHER_TIER = "tls"` is sufficient for the sitemap walk, every
category browse page, and every product page. If this tightens to a
true JS challenge, promote to `"browser"` (FlareSolverr) without
touching the parser.

`/robots.txt` itself bypasses the block (Cloudflare rule exception)
and is served to any client.

## robots.txt

Disallows are all admin / login / cart / review / scan / gift-certificate
paths (`/mazda/miata/admin/`, `/mazda/miata/ord/`, `/mazda/miata/login.html`,
`/mazda/miata/review.html`, `/mazda/miata/member/`, `/mazda/miata/GIFT*`,
`/mazda/miata/scan/MM*`, `/miata/images/captcha/`). None intersect
with the `/Mazda-Performance-Parts/…` category browse path or the
`/Mazda-Performance-Part/<sku>.html` product path. No `Sitemap:`
directive; sitemap lives at the conventional `/sitemap.xml`.

`SemrushBot` is blanket-disallowed (irrelevant to us).

## URL shapes

- **Product:** `/Mazda-Performance-Part/<sku>.html` — **singular**.
  SKUs span hyphenated numerics (`61-3447`, `13-1063`), letter-prefixed
  codes (`BB1221`, `GWR-031`, `VH060650`), and pure numerics.
- **Category browse:** `/Mazda-Performance-Parts/<chassis>/<category>[/<sub>].html`
  — **plural**. Despite the "Mazda-Performance-Parts" prefix on the
  path, this segment covers every chassis the store sells: Miata, MX5,
  MX5-ND, RX7, RX8, Mazda2/3/6, CX5, Fiat-124, BRZ-FRS-86, Truck-Parts,
  Ridgeline, Maverick, Rivian, MINI-Cooper. Not a Mazda-only segment.
- **Session tag:** every internal href picks up `?id=<8-char-token>`
  (Interchange session). The adapter's link extractor strips it before
  dedupe so cache keys are stable across sessions.

## Sitemap

`/sitemap.xml` is a flat urlset (not an index) of ~4,000 URLs. The
vast majority are `/mazda/miata/gallerycar/<id>.html` photo pages
(~1,000 entries) and other non-commerce URLs. Product-bearing entries
are the **category** URLs under `/Mazda-Performance-Parts/...` — the
sitemap does **not** list individual product pages.

Discovery therefore walks every `/Mazda-Performance-Parts/*` URL in
the sitemap and extracts `/Mazda-Performance-Part/<sku>.html` links
from each. Depth-3 browse pages (`/Miata/Brakes.html`) render only
subcategory link-outs and return zero products — that's a cheap no-op.
Depth-4+ pages (`/Miata/Brakes/Pads.html`) return the real product
cards. ~340 category pages in total across all chassis; at the default
2.5s request delay that's ~15 minutes for a full discovery pass.

## Image URL sizes

`/images/items/485x485/<file>.webp` is the hero resolution; `300x300/`
is used for category card thumbnails. Neither `600x600/` nor `1000x1000/`
exists — requesting them returns HTTP 404 with the site's error-page
HTML. JSON-LD `image` already emits the 485x485 form, so no rewriting
is needed.

## Brand policy

Good-Win is a multi-brand reseller. JSON-LD `brand.name` reliably
carries the real manufacturer across the catalog (DBA, EBC, Koyo, ACT,
Competition Clutch, Sparco, Jackson Racing, Racing Beat, RoadsterSport,
and many more) and also fills in for Good-Win's own-branded SKUs
(typically `GWR-*` part numbers). The adapter passes it through
unchanged — no default, no vendor-variant collapse.
