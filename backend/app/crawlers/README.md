# Crawler infrastructure

Per-retailer crawlers for scraping part information at scale. Run from the **backend** directory.

**PartManufacturers are central:** All crawlers and the chrome extension use the same database. `get_or_create_part_manufacturer_by_name` ensures a part_manufacturer is only defined once; you define or edit part_manufacturers in the app and they apply everywhere.

## Run

```bash
python -m app.crawlers --adapter <name> [--limit N] [--delay SEC]
```

**Required env:**

- **CRAWLER_USER_ID** – User ID that will own crawler-created parts (must have create permission).
- **CRAWLER_DEFAULT_CATEGORY_ID** or **CRAWLER_DEFAULT_CATEGORY_NAME** – Category for new parts (e.g. `exhaust`). If both unset, the first active category in the DB is used.

**Options:**

- `--adapter` – Adapter name (e.g. `example`). Required.
- `--limit` – Max product URLs to process (default: no limit).
- `--delay` – Seconds between requests (default: 2.5). If the site sets a higher **Crawl-delay** in robots.txt, that value is used. Jitter (±20%) is applied so traffic doesn't look robotic.

**Heavy runs:** A run is considered heavy when you're hitting a lot of pages in one go—e.g. no `--limit` (or a high limit), running all adapters, or a full sitemap. For heavy runs, use a higher delay (e.g. `--delay 5` or `delay_sec: 5` in the admin API) to stay well within polite-crawler norms and reduce the chance of rate limits or blocks.

**Robots.txt:** The crawler respects robots.txt per origin: before each product-page request it checks that the configured user agent is allowed to fetch the URL. Disallowed URLs are skipped (and logged). If a site specifies **Crawl-delay**, we use the larger of `--delay` and that value. If robots.txt is unreachable or errors, we allow the request (we do not block the crawl).

**Rate limiting:** Staying unbanned is prioritized over speed. On **429 (Too Many Requests)** or **503 (Service Unavailable)**, the crawler backs off and retries: it honors the **Retry-After** header when present, otherwise uses exponential backoff (2^n seconds, capped), with ±20% jitter to avoid synchronized retries. After 5 retries the request fails. All fetches (product pages and discovery, e.g. sitemaps) use this logic.

**Example (A90 Shop):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=wheels
python -m app.crawlers --adapter a90shop --limit 5
```

Optional: `CRAWLER_A90SHOP_START_URLS` (comma-separated) overrides the default product URLs for the a90shop adapter.

**Example (Studio RSR):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=roll-cage
python -m app.crawlers --adapter studiorsr --limit 5
```

Optional: `CRAWLER_STUDIORSR_START_URLS` (comma-separated) overrides product URLs for the studiorsr adapter. By default, product URLs are discovered via sitemap.xml (all URLs containing `/products/`).

**Example (ADRO):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=aero
python -m app.crawlers --adapter adro --limit 5
```

Optional: `CRAWLER_ADRO_START_URLS` (comma-separated) overrides product URLs for the adro adapter. By default, product URLs are discovered via sitemap.xml (all URLs containing `/products/`). Brand is always normalized to `ADRO` (titles lead with the target vehicle, so the generic title heuristic would otherwise pick the car make).

**Example (Summit Racing):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=brakes
python -m app.crawlers --adapter summitracing --limit 5
```

Optional: `CRAWLER_SUMMITRACING_START_URLS` (comma-separated) overrides the starting category/search URLs. Defaults to the diesel exhaust brakes category. Discovery walks `?page=N` pagination and collects all `/parts/<slug>` product URLs from the configured categories. Parsing uses the page's JSON-LD `Product` block and pulls the full image gallery from the `part-media-files` JSON. Summit's SKU is retailer-prefixed (e.g. `BDD-2001102`); the adapter uses the JSON-LD `mpn` (`2001102`) as the part number so cross-retailer dedupe still works.

**Example (MAPerformance):**

```bash
export CRAWLER_USER_ID=1
export CRAWLER_DEFAULT_CATEGORY_NAME=engine
python -m app.crawlers --adapter maperformance --limit 5
```

Optional: `CRAWLER_MAPERFORMANCE_START_URLS` (comma-separated) overrides product URLs. By default, product URLs are discovered via sitemap.xml (a Shopify sitemap index pointing at `sitemap_products_N.xml` children). MAP emits JSON-LD as `ProductGroup` with a `hasVariant` array (not the plain `Product` schema the shared extractor handles), so the adapter has its own ProductGroup-aware extractor that reads the first variant for sku/price/image. Brands are passed through unchanged (Perrin Performance, COBB Tuning, Cusco, Mishimoto, …) since MAP carries many third-party manufacturers.

**Full-page archive (optional):** To keep a copy of each product page for post-processing or re-parsing:

- **CRAWL_HTML_SAVE_DIR** – Directory to save HTML (e.g. `./crawl_cache`). When set, we save a full page copy for **new URLs only** (first time we see that product URL). Recrawls (known URLs) still fetch and update price but do not write HTML by default.
- **CRAWL_HTML_SAVE_ON_RECRAWL** – Set to `1`, `true`, or `yes` to also overwrite the saved HTML when recrawling known URLs (so you always have the latest page copy; overwriting is one write per URL).

Files are stored as `CRAWL_HTML_SAVE_DIR/<adapter>/<url_hash>.html` with a sidecar `<url_hash>.url` containing the product URL so you can re-parse later without re-fetching.

## Adding a retailer adapter

1. Create `adapters/<retailer>.py` (e.g. `summit_racing.py`).
2. Subclass `RetailerCrawlerAdapter` and implement:
   - `discover_product_urls()` – yield product page URLs (sitemap, category, search).
   - `parse_product_page(html, url)` – return a `ScrapedPayload` or `None`.
3. Register in `adapters/__init__.py`: add to `ADAPTER_REGISTRY` and optionally `get_adapter` choices.
4. If the retailer blocks plain `requests`, set `FETCHER_TIER` on the class (see *Fetcher tiers* below).

See `adapters/a90shop.py` and `adapters/studiorsr.py` for examples; `parsing.py` for shared helpers (JSON-LD, meta_content, extract_dom_price, part_manufacturer_from_title); and `base.py` for the `ScrapedPayload` contract.

## Fetcher tiers

Retailers vary wildly in how aggressively they block automated clients. Rather than always reach for a headless browser, each adapter declares which **fetcher tier** it needs and the runner constructs a matching fetcher at startup. See `app/crawlers/fetchers.py` for the implementations.

| Tier | `FETCHER_TIER` | Class | When to use |
| --- | --- | --- | --- |
| 0 | `"http"` (default) | `HttpFetcher` | Plain `requests` + existing retry/backoff logic. The right choice for any retailer that isn't actively blocking you. |
| 1 | `"tls"` | `TlsFetcher` (`curl_cffi`, Chrome impersonation) | Cloudflare TLS/JA3 fingerprint blocks where a real browser from the same IP works fine (e.g. Vivid Racing). No JavaScript execution. |
| 2 | `"browser"` | `FlareSolverrFetcher` (HTTP client to a FlareSolverr service) | Cloudflare *managed JS challenges* — the `Just a moment…` interstitial that requires JS + cookie round-trips (e.g. JEGS, FCP Euro). |

Within `run_crawler()`, the fetcher is constructed from `adapter.FETCHER_TIER` before the adapter itself, injected into the adapter's constructor, and closed in a `finally` block. The adapter's `discover_product_urls()` should call `self.fetcher.fetch(...)` rather than the module-level `fetch_page()` when the sitemap or discovery endpoints are themselves behind the block.

Declaration on an adapter:

```python
class VividRacingAdapter(RetailerCrawlerAdapter):
    FETCHER_TIER = "tls"
    # ...
```

### Tier 1 — TLS impersonation (`curl_cffi`)

Installs as a pip dependency (`curl_cffi` in `requirements.txt`). Ships native libcurl-impersonate binaries and selects a Chrome profile (default `chrome124`). The impersonation is a full TLS/JA3 + HTTP/2 frame-order match, not just a user-agent string change.

**What can break:**
- Chrome fingerprints drift. If Cloudflare starts flagging a once-working profile, bump `DEFAULT_TLS_IMPERSONATE` in `fetchers.py` to a newer profile (`chrome131`, etc.) as curl_cffi adds them.
- AWS egress IPs have poor reputation with Bot Management. A working TLS handshake still isn't a guarantee; if the IP is scored badly enough, Cloudflare may challenge or block regardless. Symptom: persistent 403s on every URL from an adapter that worked in local testing.
- The `curl_cffi` wheel is glibc-based. Alpine-based container images need the musl wheel (available on PyPI as of 0.7.x) or a glibc base (Debian/Ubuntu slim works out of the box).

**Fallback when it stops working:**
1. Bump the Chrome profile (cheap).
2. Promote the adapter to Tier 2 (`FETCHER_TIER = "browser"`).
3. Fall back to extension-only ingest for that site.

### Tier 2 — FlareSolverr (browser)

[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) is a standalone service that wraps undetected-chromedriver to solve Cloudflare challenges and return post-challenge HTML. We run it as an external service — the crawler posts to its `/v1` endpoint; the service maintains a Chromium pool and a CF-clearance cookie jar keyed by session name.

**Configuration — all three values are Terraform-managed; do not set env vars by hand.**

Defined in `terraform/variables.tf` and wired through `terraform/apprunner.tf` (for background crawls driven by the API) and `terraform/ecs.tf` (for the Fargate crawler task). The Python code reads them only via `app.core.config.settings`; there is no environment-variable fallback in the fetcher factory.

| Setting | Terraform variable | Default | Purpose |
| --- | --- | --- | --- |
| `settings.FLARESOLVERR_URL` | `flaresolverr_url` | `""` (disabled) | Base URL of the service (e.g. `http://flaresolverr.crawler.local:8191`). Empty = Tier 2 disabled; adapters with `FETCHER_TIER="browser"` raise `FlareSolverrNotConfiguredError` at first fetch rather than silently falling back. |
| `settings.FLARESOLVERR_MAX_TIMEOUT_MS` | `flaresolverr_max_timeout_ms` | `60000` | Per-request budget sent to FlareSolverr. Most challenges resolve in <15s; the first request of a session pays the full solve cost. |
| `settings.FLARESOLVERR_SESSION_NAME` | `flaresolverr_session_name` | `carmodpicker-crawler` | Single long-lived session id so the CF-clearance cookie is reused across requests. Destroyed in the runner's `finally` block. |

Set these in your HCP Terraform workspace (or `.tfvars`) alongside the other crawler variables. The default — empty `flaresolverr_url` — leaves Tier 2 disabled, so Terraform applies cleanly before the FlareSolverr service is in place.

### Deploying FlareSolverr on AWS, no external vendor

FlareSolverr is a standalone HTTP service (POST `/v1`); any reachable instance works. The pattern below uses ECS Fargate with Cloud Map service discovery — it matches how the crawler task is already run, so no new networking primitives are needed.

**1. Build or reference the image.** The official `ghcr.io/flaresolverr/flaresolverr:latest` works. If GHCR rate limits bite, mirror it into our ECR repo and reference that ARN instead. Pin to a specific tag in production (e.g. `:v3.3.21`) so an upstream push can't silently break a working deploy.

**2. Create an ECS service** in the existing `${local.prefix}-crawler` cluster (same one as `aws_ecs_cluster.crawler` in `terraform/ecs.tf`). Outline:

```hcl
# terraform/flaresolverr.tf (new file)
resource "aws_cloudwatch_log_group" "flaresolverr" {
  name              = "/ecs/${local.prefix}-flaresolverr"
  retention_in_days = 30
}

resource "aws_security_group" "flaresolverr" {
  name   = "${local.prefix}-flaresolverr-sg"
  vpc_id = aws_vpc.main.id

  # Only the crawler task SG can talk to FlareSolverr on 8191.
  ingress {
    from_port       = 8191
    to_port         = 8191
    protocol        = "tcp"
    security_groups = [aws_security_group.crawler_task.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "flaresolverr" {
  family                   = "${local.prefix}-flaresolverr"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"  # 1 vCPU — Chromium is hungry
  memory                   = "2048"  # 2 GB — documented minimum
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "flaresolverr"
    image     = "ghcr.io/flaresolverr/flaresolverr:v3.3.21"  # pin, don't :latest
    essential = true
    portMappings = [{ containerPort = 8191, protocol = "tcp" }]
    environment = [
      { name = "LOG_LEVEL",     value = "info" },
      { name = "CAPTCHA_SOLVER", value = "none" },  # we don't pay for a solver
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.flaresolverr.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}
```

**3. Pick a service-discovery approach.** Two options:

- *Cloud Map (private DNS, recommended).* Create `aws_service_discovery_private_dns_namespace` + `aws_service_discovery_service` and attach the ECS service's `service_registries` to it. `flaresolverr_url` becomes `http://flaresolverr.<namespace>:8191`.
- *Internal ALB.* More AWS spend (~$16/mo for the ALB) but gives health checks + target-group metrics. Worth it only once you're running Tier 2 at real volume.

**4. Add `aws_ecs_service.flaresolverr`** with `desired_count = 1`, `launch_type = "FARGATE"`, `assign_public_ip = true` (for egress to the retailers we're crawling), and `network_configuration` pointing at the public subnets + the new SG. Attach `service_registries` if you went with Cloud Map.

**5. Set the Terraform vars:**

```
flaresolverr_url            = "http://flaresolverr.<cloudmap-namespace>:8191"
flaresolverr_max_timeout_ms = 60000     # default; bump only if solves are timing out
flaresolverr_session_name   = "carmodpicker-crawler"
```

`terraform apply`. App Runner will roll once to pick up the new env vars; the ECS crawler task definition gets a new revision but the next crawl run uses it automatically.

**6. Verify end-to-end** from inside the VPC (one-off EC2 or a Fargate exec session on the crawler task):

```bash
# sessions.create → should return {"status":"ok",...}
curl -sX POST http://flaresolverr.crawler.local:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.create","session":"test"}'

# Fetch a CF-challenged URL → should return HTML in solution.response
curl -sX POST http://flaresolverr.crawler.local:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"request.get","url":"https://www.jegs.com/","session":"test","maxTimeout":60000}' \
  | jq '.status, .solution.status, (.solution.response | length)'

curl -sX POST http://flaresolverr.crawler.local:8191/v1 \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"sessions.destroy","session":"test"}'
```

Then kick off a low-limit crawl of a browser-tier adapter (`python -m app.crawlers --adapter <name> --limit 3` from a Fargate exec session) and check CloudWatch logs for `Adapter X: using fetcher tier 'browser' (FlareSolverrFetcher)`.

**Operational budget:**

- Keep crawler concurrency modest (1–2 workers per Tier 2 adapter). FlareSolverr serializes through its Chromium pool; hammering it makes every request slower, not faster.
- Egress: challenge-solving involves full page loads with all assets. ~2–5 MB per fresh-session request, dropping to ~100 KB–1 MB per warm-session request.
- Cost estimate: 1 vCPU / 2 GB Fargate task running 24/7 ≈ $30/mo. For bursty crawl schedules, scale `desired_count` to 0 outside the crawl window with an EventBridge Scheduler rule and scale to 1 before each run.

**Known failure modes — what to watch for in production:**

1. **Cloudflare ships a detection update.** FlareSolverr is a cat-and-mouse project; when Cloudflare rolls out new anti-bot logic, FlareSolverr can take days to weeks to catch up. Symptom: consecutive `FlareSolverrError` entries in logs with `solution.status=403` even though the page was "solved." Check the FlareSolverr GitHub issues page when this happens.
2. **Upstream maintenance has been intermittent.** The project has gone months between releases. If a fix stalls, the realistic options are listed in the fallback table below.
3. **Chromium memory leak under load.** Long-running FlareSolverr instances occasionally bloat past their container memory limit. Mitigation: set an ECS `memory` hard limit and rely on OOMKill → ECS task replacement, or schedule a periodic task restart.
4. **Session expiry.** FlareSolverr sessions hold a Chromium instance; they can be reaped by the service when idle. Our code re-creates the session on the next request, but if the reaping happens mid-batch you'll see one `sessions.create` error followed by successful retries — treat as warning, not failure.
5. **AWS IP reputation.** Even with a real Chromium, AWS IPs can be scored so poorly that Cloudflare serves the hardest challenges every time, or outright blocks. Symptom: the first request of every session takes 30+ seconds and half of them fail. Diagnose by running the same URL through FlareSolverr from a residential network.
6. **JSON endpoints** (e.g. `/products.json`) may return content-type `application/json` — FlareSolverr still returns the body as a string in `solution.response`, but watch for HTML-escape artifacts if the site serves the JSON wrapped in an interstitial check.

**Fallback options if Tier 2 stops working or is unsustainable in production:**

| Option | What it means | Cost |
| --- | --- | --- |
| Upgrade / wait | Pin to a working FlareSolverr image tag and stay put; upgrade when the project ships a fix. | Engineering time to monitor + pin. No new spend. |
| Patchright-based in-house fetcher | Replace `FlareSolverrFetcher` with a Python + Patchright implementation. More code to own, but no external service. | Engineering time (~1–2 days to port). ECS Fargate task cost similar. Generally better-maintained than FlareSolverr. |
| Camoufox | Anti-detection Firefox fork; same idea as Patchright but with a non-Chromium engine (different fingerprint class). | Same shape as Patchright option. |
| Botasaurus | Python framework that bundles anti-detection + retry/session. Heavier buy-in; takes over more of the pipeline. | Several days of integration. Worth it if we end up wanting the retry machinery too. |
| Extension-only for affected sites | Stop trying to ingest server-side; rely on the Chrome-extension capture path. | Zero engineering, but low ingest throughput. Good fallback for a small number of stubborn sites. |
| Residential proxies | Route FlareSolverr (or any tier) egress through residential IPs. Fixes IP-reputation issues that Tier changes can't. | Monthly spend starting ~$50 (you've ruled this out as a starter option, keep as last resort). |
| Alt ASN egress | Route crawler egress through a Tailscale exit node on a home or small-VPS network instead of AWS. | Operational complexity + some trust on uptime; no vendor spend. |

**Operational tips:**

- Keep per-adapter concurrency low in `run_crawlers(parallel=...)` when running Tier 2 adapters. One worker per adapter is the safe default.
- When developing a new Tier 2 adapter, first verify FlareSolverr can reach the site at all (`curl -X POST $FLARESOLVERR_URL/v1 -H 'Content-Type: application/json' -d '{"cmd":"request.get","url":"...","maxTimeout":60000}'`). If that returns `status=ok` with 200, the rest is adapter parsing work.
- FlareSolverr logs are verbose. Ship them to CloudWatch with a higher filter-pattern threshold than normal so you can actually see the `ERROR`-level lines when things go sideways.
