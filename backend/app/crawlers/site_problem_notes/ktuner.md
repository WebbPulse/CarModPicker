# KTuner (ktuner.com)

Plain WordPress on Apache. No Cloudflare, no TLS fingerprinting, no JS
challenge — straight HTTP `GET`s work. Tier-0.

## The single-page catalog

KTuner does **not** have per-product detail pages. The entire retail
hardware lineup (four SKUs as of 2026-04) is rendered inline on a single
`/products/` page as `<p>`/`<ul>` blocks separated by `<hr />` rules.
There is no:

- JSON-LD `Product` schema
- `og:product:*` / product-price meta tags
- Add-to-cart flow (KTuner sells via dealer network or direct email)
- Dedicated product URL per SKU

### Workaround

`discover_product_urls()` emits four virtual URLs, one per SKU, with a
distinct `?sku=<slug>` query parameter:

```
https://ktuner.com/products/?sku=ktunerflash-v2-touch
https://ktuner.com/products/?sku=ktunerflash-v1-2
https://ktuner.com/products/?sku=ktunerecu-rev1
https://ktuner.com/products/?sku=ktuner-flex-fuel-converter
```

`sku` is not in `canonicalize_url`'s tracking-param blocklist so the
canonical URLs stay distinct. WordPress ignores the unknown parameter and
returns identical catalog HTML for all four, so the crawler fetches the
same page four times per run — acceptable trade-off given the catalog is
only four items and this is the shape of the site.

`parse_product_page` reads the slug, walks the `<hr />`-delimited
sections of `.post-content`, and picks the section whose header
`<strong>` text matches the slug's keyword set.

## SKUs

Only the Flex Fuel Converter prints a real MPN on the page (`FFC100`). The
three flash-tuning hardware units are sold by name without a public SKU,
so we fall back to a stable slug-derived code
(`KTUNERFLASH-V2-TOUCH`, `KTUNERFLASH-V1.2`, `KTUNERECU-REV1`). If we
ever crawl a KTuner dealer site, use matching codes there so
cross-retailer dedupe lines up.

## Out of scope

The "TunerView Android App" section at the bottom of `/products/` lists a
$4.99 Google Play app. It's not a KTuner-sold hardware SKU — pricing lives
on Google Play, and the product isn't what the backlog wanted us to cover
("competing flash-tuning hardware" for Honda). Not in the discovery list.

## Images

KTuner's theme writes image `src` attributes as
`http://www.ktuner.com/images/...` even though the site serves fine over
HTTPS. We upgrade `http://` → `https://` in the adapter so stored image
URLs don't mixed-content-block on the HTTPS frontend.

## robots.txt

Only `/wp-admin/` is disallowed (with `admin-ajax.php` re-allowed).
`/products/` is permitted.
