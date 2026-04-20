# Cobb Tuning (cobbtuning.com)

**Status:** Tier-1 TLS adapter committed. Investigation 2026-04-19.

## Platform

Magento 2, based on the `robots.txt` disallow list (`/checkout/`,
`/onestepcheckout/`, `/customer/`, `/catalog/`, `/catalogsearch/`, `/review/`,
`/tag/`, `/pkginfo/`, `/var/`, `/app/`, `/bin/`, `/dev/`, `/lib/`, `/pub/` —
all canonical Magento 2 directory shapes). Product URLs are Magento 2
`url_key` values with the default `.html` suffix at the site root, e.g.
`https://www.cobbtuning.com/accessport-v3.html`.

## Fetch blocker: Cloudflare block (not a JS challenge)

Same profile as Vivid Racing (`site_problem_notes/vividracing.md`): plain
`requests.get(...)` with the crawler UA returns **403**, and `curl` with a
full current-Chrome header set (UA, `Sec-Ch-Ua*`, `Sec-Fetch-*`,
`Accept-Language`, `Accept-Encoding: gzip, deflate, br, zstd`,
`Upgrade-Insecure-Requests`, `--compressed`) is **also 403**. Real-browser
access from the same network loads fine, which rules out an IP / ASN block
against our egress. Likely signal: TLS ClientHello / JA3 fingerprint (Python
`requests` and curl both look nothing like real Chrome), possibly layered
with Bot Management scoring on HTTP/2 frame behavior and header order.

Probe, 2026-04-19, from AWS egress, browser UA:

| Path                    | HTTP |
| ----------------------- | ---- |
| `/robots.txt`           |  200 |
| `/sitemap.xml`          |  403 |
| `/`                     |  403 |
| `/media/sitemap.xml`    |  403 |
| `/accessport-v3.html`   |  403 |

Only `/robots.txt` is served outside the Cloudflare block rule. Everything
else — sitemap, homepage, product pages — goes through the same rule.
Practical implication: `curl_cffi` with `impersonate="chrome"` (our
`TlsFetcher`) has a reasonable chance of getting through for **both**
discovery (the sitemap walk) and product fetches, because the block is
client-fingerprint-based, not IP-based. Plain `requests` and stock
`cloudscraper` will not help — they fail the TLS fingerprint check before
any challenge is even served.

## robots.txt highlights

- `User-Agent: *` is allowed for product paths (root-level `.html` slugs are
  not in the disallow list).
- `Disallow: /*?` — **any URL with query params is disallowed.** Canonical
  product URLs have no query string, but any tracking-param or sorting URL
  (`?product_list_mode=`, `?product_list_order=`, `?SID=`) must be stripped
  before being fed to the adapter. `canonicalize_url()` in
  `crawlers/base.py` already strips known tracking params.
- No `Sitemap:` directive is declared in `robots.txt`. Magento 2's default
  location is `/sitemap.xml` at the root, and the adapter probes it there.
- Standard e-commerce account / checkout disallows (`/checkout/`,
  `/onestepcheckout/`, `/customer/`, `/customer/account/`, etc.) —
  irrelevant for product discovery but mirror the Magento 2 default.

## Product URL pattern

`/<slug>.html` — Magento 2 `url_key` with the default `.html` product URL
suffix. There is **no** product-id segment (unlike Vivid Racing's
`-p-<digits>.html`), so URL shape alone cannot distinguish product pages
from CMS / category pages (which also end in `.html` in Magento 2's default
config). The adapter therefore:

- Treats `_is_product_url()` as a shape guard only (reject query strings,
  reject off-host, reject an explicit list of CMS / account paths like
  `/about-us.html`, `/warranty.html`, `/dealers.html`).
- Relies on the sitemap urlset as the source of truth for "is this a
  product page."
- Falls back to "no JSON-LD Product and no `<h1>`/og-title ⇒ return None"
  so non-product pages that slip through the shape guard don't get ingested
  with garbage.

## Manufacturer default

Cobb's catalog is overwhelmingly their own hardware — AccessPort V3, SF
intakes, NexGen exhausts, Stage 1/2/3 packages, Tuner Protocol tools.
Third-party brands (Mishimoto, IAG, Grimmspeed, etc.) show up only as part
of Stage bundles. When JSON-LD brand is missing and
`part_manufacturer_from_title()` returns None, the adapter defaults to
**"COBB Tuning"**. Without this default the title-first-word heuristic
would write product words like "Accessport" or "Stage" as manufacturer
names, which is worse than just assigning the correct parent brand.

When JSON-LD *does* carry a brand (e.g. a co-branded SKU that names
Mishimoto), the adapter passes it through unchanged — the default only
fires on the fallback path.

## Paths forward

1. **TLS-impersonating adapter (done, this file).** First try — the block
   is methodology-based, not IP-based. `curl_cffi` with Chrome impersonation
   is enough to get past the same class of block on Vivid Racing. If Cobb
   also issues a JS challenge on top, promote `FETCHER_TIER` to `"browser"`
   (FlareSolverr) without touching the parser.

2. **Capture a real-browser sample for parser tuning.** Magento 2's default
   JSON-LD output is schema.org `Product` with `brand` / `sku` / `offers` /
   `image`, which the shared `extract_json_ld_product()` already handles.
   If Cobb's SEO app emits `ProductGroup` (MAPerformance-style), add a
   variant-aware branch mirroring `maperformance.py`. Easiest way to decide
   is to pull one product page via the Chrome extension and check the
   JSON-LD `@type`.
