# Tire Rack (tirerack.com)

**Status:** adapter written in extension-only mode (parse-only).
Investigation 2026-04-19.

## Why this retailer matters

Tire Rack is the reference price-compare site for enthusiast wheel and
tire purchases — consumers mentally benchmark every wheel/tire SKU
against it. It also surfaces staggered fitment and load-rating data that
the car-parts retailers in the rest of our registry do not expose. Until
Tire Rack is covered, any build list that includes a wheel/tire package
is not fully priceable.

## Fetch blocker: heavy anti-bot

Product pages, search results, and sitemap-ish endpoints are all behind
an aggressive anti-bot stack (session-cookie JS challenge plus bot-score
heuristics — not a vanilla Cloudflare managed challenge, but the visible
symptoms are similar: the real HTML is withheld until a browser has
executed challenge JS and round-tripped cookies).

- `requests.get(...)` with a current Chrome User-Agent → typically 403
  or a short HTML body missing the product JSON-LD.
- `curl` with our `CarModPicker-Crawler/1.0` User-Agent → 403.
- `WebFetch` → 403 / interstitial.
- TLS impersonation (Tier 1, `curl_cffi`) will not help here: the gate
  is JS execution, not TLS fingerprint. Hence Tier 2 FlareSolverr is the
  minimum viable fetch path.

## Product URL shapes

Tire Rack uses multiple URL forms, and the "modern" vs "legacy" split is
not stable across the site:

- Modern tire detail: `/tires/<Make>/<Model-Slug>/`
- Legacy tire detail: `/tires/TireDetails.jsp?tireMake=...&tireModel=...&partnum=...`
- Modern wheel detail: `/wheels/<Make>/<Model-Slug>/`
- Legacy wheel detail: `/wheels/WheelDetail.jsp?wheelMake=...&wheelModel=...&partnum=...`

Vehicle/size selectors drive which URL a user lands on. Because the path
structure churns and the query-string form can carry the manufacturer +
part number while the slug form usually does not, we **do not** regex
brand/part-number out of the URL the way the JEGS adapter does. JSON-LD
and DOM meta are the trustworthy signals.

## Discovery

The vehicle-fitment selector that Tire Rack's homepage pushes is a
JS-driven modal and does not produce a stable URL-enumeration path. When
live crawling is wired up (FlareSolverr), discovery should walk the
brand-catalog index pages (`/tires/<Make>/`, `/wheels/<Make>/`) rather
than the fitment selector.

Consider whether wheels and tires eventually want to live under a
dedicated `wheels_tires/` sub-namespace in `adapters/`. For the first
adapter the existing `tier2_browser/` layout is fine — revisit once
Mackin / Wheels Boutique are added and the shape of a second
wheels-focused adapter makes the factoring decision easier.

## Paths forward

1. **Extension-only adapter (this change).** `parse_product_page()`
   tuned to Tire Rack's JSON-LD + DOM, hostname wired into
   `adapter_name_for_product_url()`. The Chrome extension scrapes pages
   the user already loaded in their browser (post-challenge), so the
   anti-bot stack is not a blocker for extension-captured HTML.
   `discover_product_urls()` is a stub.

2. **Crawler + FlareSolverr.** Add brand-catalog walking once Tier 2 is
   deployed (`FLARESOLVERR_URL` configured). Note that brand-catalog
   index pages are themselves behind the anti-bot stack, so discovery
   also has to flow through the Tier 2 fetcher.

## Open questions (need a real page sample)

Without a post-challenge HTML snapshot we cannot yet confirm:

- Does Tire Rack emit JSON-LD `Product` on modern slug URLs *and* legacy
  `TireDetails.jsp` URLs, or only one of the two?
- Are tire size, load index, speed rating, and wheel fitment (bolt
  pattern, offset, centerbore) exposed as structured data anywhere, or
  only as free text in the DOM? These are the fields that justify
  covering Tire Rack over a car-parts retailer in the first place.
- What's the image CDN pattern (for allowlisting in the frontend
  image-host whitelist)?

Next step before tightening the adapter: capture a real tire + a real
wheel detail page via the Chrome extension, drop them under
`backend/tests/crawlers/fixtures/`, and replace the synthetic HTML in
`test_tirerack_adapter.py` with those fixtures.
