# TODO

## Before launch

- Update `CHROME_EXTENSION_STORE_URL` in `frontend/src/constants/index.ts` to the real Chrome Web Store listing URL once the extension is published. Used by the nav "Get Extension" link and the `ChromeExtensionPromo` banner.

## AdSense approval

### Deploy the current in-house prerender setup

- Clear `prerender_token` from the HCP Terraform workspace variables (no longer referenced).
- Queue a terraform run. Plan should delete `aws_lambda_function.prerender`, `aws_iam_role.prerender_lambda`, `aws_cloudfront_cache_policy.frontend_bot_aware` and create `aws_cloudfront_function.frontend_uri_rewrite`. Lambda@Edge replicas take ~1h to release — first apply may need a retry.
- Deploy a fresh frontend build to S3 so the prerendered route directories (`/about/index.html`, etc.) land in the bucket.
- Smoke test:
  - `curl -A "Googlebot" https://www.carmodpicker.com/about` → real About page HTML with `<title>About | CarModPicker</title>` in the head and hero content in the body.
  - `curl https://www.carmodpicker.com/parts/1` → still the SPA shell (expected — dynamic routes aren't prerendered).

### Content / positioning (do before applying)

- **Scraped retailer content on parts pages is the #1 rejection risk.** A reviewer landing on `/parts/123` will see name, price, and spec mirrored from a retailer. Before applying, decide one of:
  - `noindex` thin/crawled part pages until they have user context (build list usage, votes, comments).
  - Add enough original framing (community compatibility notes, curated descriptions, categorization) so the page reads as our own content, not a retailer mirror.
  - Only surface crawled parts in catalog/search results, not as standalone indexable pages.
- Hide or tone down the sitewide `BetaBanner` during AdSense review — "under construction" banners trigger thin-site rejections.
- Seed enough build lists/parts that `/` "Featured Builds" and "Popular Parts" aren't mostly empty. A sparse landing page reads as thin.
- Consider adding a short curated About/Guide section with original editorial content (e.g., "What makes a good build log", "Intro to modding your first car") — helps content-volume signal.

### Polish / nice-to-haves

- Per-route Open Graph images — today every route uses `/car.png` as the OG image. Generate branded OG images for the landing page and deep routes (can be done dynamically via a small image service or pre-generated).
- Dynamic `sitemap.xml` — the current static one lists 10 canonical routes. Add a build-time or backend-generated sitemap that includes indexable parts and build lists so Google can discover deep content.
- Revisit prerendering catalog pages (`/parts`, `/build-lists`, `/search`) once the build environment can reach the backend — currently they snapshot as loading-skeleton shells.
- Set up Google Search Console, submit the sitemap, and monitor coverage after AdSense approval is in flight.
- Implement Consent Mode v2 region targeting — right now every visitor starts at all-denied. For non-EEA visitors, consider defaulting `ad_storage` etc. to `granted` (Google allows this per jurisdiction) to boost ad fill rate without hurting EU compliance.

### When to apply

- Wait until the deploy tasks above are done **and** at least the scraped-content decision is made. First AdSense submissions stick in your memory — a rejection adds 2–4 weeks to the next attempt. Aim to apply once.
