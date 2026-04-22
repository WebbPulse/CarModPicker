# Codebase Concerns

**Analysis Date:** 2026-04-22

## Tech Debt

**Large car data file causing startup overhead:**
- Issue: `backend/app/core/car_generations_data.py` is 8,412 lines — a Python data structure containing the full car generations dataset. Imported by `car_inference.py` during crawler initialization, which adds non-trivial startup latency.
- Files: `backend/app/core/car_generations_data.py`, `backend/app/core/car_inference.py`
- Impact: Slow crawler initialization, slower local development with `uvicorn --reload`
- Fix approach: Move data to a JSON file loaded lazily on first use, or pre-load into Redis/memory cache. Consider database-native seeding if queries become heavy.

**Complex car inference logic with brittle ambiguity handling:**
- Issue: `backend/app/core/car_inference.py` (2,742 lines) uses hardcoded lists of ambiguous car codes and regex matching to disambiguate (e.g., "E90" matches both BMW E90 M3 and Toyota Corolla E90). The AMBIGUOUS_STANDALONE_CODES set requires constant manual maintenance as new parts/models are added.
- Files: `backend/app/core/car_inference.py` (lines 21–80+ listing ~40 ambiguous codes)
- Impact: Risk of false car associations in crawler results when new product naming conventions emerge; requires regular audits as parts database grows
- Fix approach: Consider machine-learning approach (keyword embeddings) or move ambiguity resolution to admin UI during part curation rather than inference.

**Admin endpoint file size and complexity:**
- Issue: `backend/app/api/endpoints/admin.py` is 2,055 lines, containing job scheduling, ECS orchestration, crawler management, admin stats, and database operations. High coupling with job service, crawler runner, and storage layers.
- Files: `backend/app/api/endpoints/admin.py`
- Impact: Difficult to test; changes to any subsystem (jobs, crawlers, S3) risk breaking admin operations. Hard to isolate failure root causes.
- Fix approach: Split into domain-specific routers: `admin_jobs.py`, `admin_crawlers.py`, `admin_stats.py`. Reduce coupling by injecting service dependencies.

**Loose coupling between crawler adapters and registry:**
- Issue: Each adapter in `backend/app/crawlers/adapters/` is independently registered in `adapters/__init__.py`. Adding a new adapter requires manual registration. No automated discovery or validation.
- Files: `backend/app/crawlers/adapters/__init__.py` (manual registration)
- Impact: Easy to forget to register new adapters; silent failures if an adapter's import fails. Hard to audit which adapters are active.
- Fix approach: Use Python entry points or directory-scan-based auto-discovery with validation.

## Known Bugs

**N+1 query in build log post listing:**
- Symptoms: Each call to `GET /build-logs/build-list/{id}` with paginated posts fetches the author (DBUser) once per post in a loop, not as a batch.
- Files: `backend/app/api/endpoints/build_logs.py:119` — loop over posts calling `db.query(DBUser).filter(...)` per item
- Trigger: Any request to get build log posts with multiple posts returned
- Impact: Linear query count per post fetched. With 10 posts, 10 separate User queries. With 50+ posts, severe performance hit.
- Workaround: None currently; posts render but slowly
- Fix approach: Use SQLAlchemy `joinedload` or explicit join to fetch authors in a single query before the loop

**Adapter parse failures not well-surfaced in crawler logs:**
- Symptoms: When a crawler adapter returns None on a real product page (parsing fails), it's logged as "parse failure" but doesn't bubble to the job report email prominently. Recent commit (7831fda) fixed 6 adapters, but the pattern is fragile.
- Files: `backend/app/crawlers/runner.py`, `backend/app/crawlers/base.py`, recent fixes in `backend/app/crawlers/adapters/tier0_http/{ie.py,amsperformance.py,rallysportdirect.py,briantooleyracing.py,mackinindustries.py,wheelsboutique.py}`
- Trigger: Retailer DOM structure changes (removed JSON-LD, rewrote page layout, added redirects)
- Impact: Silent data loss — valid products on retailer sites aren't scraped; users don't know parts are missing
- Workaround: Admin must audit job reports and check parse-failure counts manually
- Fix approach: Implement per-adapter parse-failure alert threshold in crawler config; auto-email superadmins if failures exceed baseline.

**Chrome extension auth state TTL is short (10 minutes):**
- Symptoms: If a user initiates extension auth but doesn't complete login within 10 minutes, the state nonce expires. The web page still has a valid token but can't hand it off to the extension.
- Files: `chrome-extension/src/background.ts:156` — `AUTH_NONCE_TTL_MS = 10 * 60 * 1000`
- Trigger: User starts login, gets interrupted, resumes after 10+ minutes
- Impact: User must restart auth flow; minor UX friction
- Fix approach: Extend TTL to 30–60 minutes; or auto-retry with a fresh nonce if the auth tab is still open.

## Security Considerations

**CORS config allows chrome-extension:// origin (correct, but nonstandard):**
- Risk: Chrome extensions running on any site could theoretically bypass origin checks if CORS is misconfigured. Current implementation is correct (manifest restricts externally_connectable), but worth auditing.
- Files: `backend/app/main.py` (CORS middleware config)
- Current mitigation: `externally_connectable.matches` in manifest restricts to *.carmodpicker.com subdomains; background.ts validates sender hostname with `isAllowedWebHost()`
- Recommendations: Maintain strong sender validation in background.ts. Consider short-lived CORS tokens (not JWT) for extension-to-API calls if moving to sensitive operations.

**Email templates stored as React HTML files:**
- Risk: Email sent via SES is generated server-side from React Email components. If email content is user-generated or includes unsanitized input, XSS in email clients is possible.
- Files: `email-templates/` (React Email templates sent via SES)
- Current mitigation: Email templates are admin-only (job reports, crawler alerts). User-generated content in build logs is not emailed.
- Recommendations: If user-generated content ever enters email templates, sanitize with DOMPurify or equivalent before rendering.

**JWT expiry is configurable and may be set too high in production:**
- Risk: `backend/app/core/config.py` allows JWT lifetime from 15 minutes to 7 days via settings. If set to 7 days, a compromised token could be used to impersonate a user for a week.
- Files: `backend/app/core/config.py:JWT_EXPIRATION_HOURS`
- Current mitigation: Defaults to 24 hours; 2FA adds another layer
- Recommendations: Log and alert on suspicious login patterns (e.g., login from new IP, multiple failed 2FA). Consider 2–4 hour default for web sessions, longer for mobile app (not yet implemented).

**Rate limiting can be disabled globally via env var (useful for testing, risky in prod):**
- Risk: `ENABLE_RATE_LIMITING=false` disables DDoS/brute-force protection. If this env var leaks or is accidentally set in production, the API becomes vulnerable.
- Files: `backend/app/api/middleware/rate_limiter.py:234`
- Current mitigation: Rate limiting is OFF by default in tests (see conftest.py); defaults to ON in production via config
- Recommendations: Remove the env var toggle in production builds. Use feature flags (database-backed) instead for ops to disable rate limiting per-endpoint in emergencies.

## Performance Bottlenecks

**Crawler runner processes adapters sequentially; discovery is parallelized but parsing is single-threaded:**
- Problem: `run_crawlers()` in `backend/app/crawlers/runner.py` calls `run_crawler()` for each adapter serially. Within each adapter, URL discovery is fast (fetches sitemap), but parsing happens in a thread pool.
- Files: `backend/app/crawlers/runner.py:321+` (run_crawlers loop), `backend/app/crawlers/runner.py:400+` (ThreadPoolExecutor per adapter)
- Impact: A slow adapter blocks subsequent adapters. With 100+ adapters and some hanging on retailer rate limits, total crawl time grows linearly.
- Improvement path: (1) Parallelize adapter execution with asyncio + separate DB sessions per worker, (2) Add per-adapter timeout to bail early if hanging.

**Crawler rate limit circuit breaker threshold is high (5 consecutive failures):**
- Problem: `RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5` in `backend/app/crawlers/runner.py:70` means a rate-limited retailer will retry 5 times, each with exponential backoff (2+4+8+16+32s = 62s), before bailing on the whole adapter.
- Files: `backend/app/crawlers/runner.py:70–71`
- Impact: Hammers rate-limited retailers; wastes time on clearly-unreachable sites
- Improvement path: Reduce threshold to 2–3; or check for 429/503 status and bail immediately.

**No query-result caching for frequently-accessed data (cars, categories, part manufacturers):**
- Problem: Every API request to `GET /car-generations/`, `GET /categories/`, `GET /part-manufacturers/` hits the database, even though this data changes infrequently.
- Files: `backend/app/api/endpoints/{car_generations,categories,part_manufacturers}.py` (list endpoints)
- Impact: Database load spikes when frontend makes parallel requests to populate dropdowns. At scale (1K+ users), becomes a bottleneck.
- Improvement path: Cache GET requests with 1-hour TTL in Redis or in-memory; invalidate on write.

**Search endpoint joins build_lists with parts/categories but doesn't use column-specific indexes:**
- Problem: `backend/app/api/endpoints/search.py` builds complex queries joining multiple tables but may do full table scans if indexes are missing on join keys.
- Files: `backend/app/api/endpoints/search.py:93+`
- Impact: Slow search at scale
- Improvement path: Audit and add missing indexes on all foreign key columns (already done on primary tables, but verify join columns).

**Approximate row count function used in admin stats may be stale:**
- Problem: `backend/app/api/utils/approximate_count.py` uses PostgreSQL's `pg_stat_user_tables` to estimate row counts. Estimates can be off by 10–20% after bulk inserts; exact counts require table scan.
- Files: `backend/app/api/utils/approximate_count.py`
- Impact: Admin dashboard stats are slightly inaccurate; not critical, but confusing
- Improvement path: Use exact counts when called from non-time-critical endpoints (e.g., setup page); keep approximate for dashboards.

## Fragile Areas

**Chrome extension reload quirks:**
- Files: `chrome-extension/manifest.json`, `chrome-extension/src/background.ts`, content/popup scripts
- Why fragile: Files requiring extension reload (manifest.json, background.ts, popup.html/css) won't auto-update. Content/popup scripts that don't require reload can cause stale-state bugs where users interact with old version while new version loads.
- Safe modification: Always test extension reload after modifying manifest or background.ts. For popup/content changes, document the reload requirement in commit message.
- Test coverage: Extension smoke tests exist but don't cover edge cases like version-mismatch interactions.

**Build log auto-creation on first access:**
- Files: `backend/app/api/endpoints/build_logs.py:87–98` — auto-creates DBBuildLog if missing
- Why fragile: If a build list exists but no build log, the endpoint creates one mid-request. If creation fails partway (DB error, transaction rollback), caller sees inconsistent state.
- Safe modification: Wrap auto-creation in a try/except; return 500 if creation fails. Better: eagerly create build log when build list is created, not lazily.
- Test coverage: Test file `test_build_logs.py` covers basic reads, but not the auto-create failure path.

**Adapter sitemap discovery filters are regex-based and easy to accidentally relax:**
- Files: `backend/app/crawlers/adapters/tier0_http/*/discover_product_urls()` methods
- Why fragile: Regex patterns to filter out non-product URLs (e.g., `/category/`, `/blog/`) can fail silently if a retailer reorganizes. Recent commit (7831fda) fixed 4 adapters' discover filters.
- Safe modification: When modifying a filter, add a test for both true positives and true negatives. Document the retailer's URL structure in the adapter's docstring.
- Test coverage: Most adapters have discovery tests, but coverage is adapter-specific; no integration test across all adapters.

**Part linking logic (canonical parts) is not transactional:**
- Files: `backend/app/api/endpoints/parts.py` (part link/unlink endpoints), `backend/app/api/services/` (part service)
- Why fragile: If two requests simultaneously unlink/link the same part, race conditions can leave orphaned canonical references or circular links.
- Safe modification: Wrap part linking in database-level locks (SELECT FOR UPDATE) or use unique constraints on canonical_part_id.
- Test coverage: No concurrency tests for part linking; coverage assumes serial execution.

## Scaling Limits

**In-memory adapter registry grows with each adapter:**
- Current capacity: 114 adapters loaded in memory at startup
- Limit: Each adapter occupies ~5–10KB (class, methods, docstrings); 114 adapters ≈ 600KB. Not yet a problem.
- Scaling path: At 500+ adapters, consider lazy-loading via importlib or database-backed adapter registry.

**Database connection pool defaults may be undersized for concurrent crawlers:**
- Current capacity: `DB_POOL_SIZE=20` (default in `backend/app/db/session.py`), with `API_CONNECTION_RESERVE=2` reserved for app requests
- Limit: With 18 available crawler connections, 2+ parallel crawlers can block. Under heavy crawl + API traffic, connection pool exhausts.
- Scaling path: Increase pool size to 50 for prod; use read replicas for read-heavy queries (reports, stats).

**S3 bucket for crawled page HTML storage may grow unbounded:**
- Current capacity: Recent crawl stats show ~5GB in `carmodpicker-prod-user-images` for the entire site. HTML snapshots will add significant volume.
- Limit: S3 API list operations slow down (ListObjects paginates after 1000 keys); no built-in retention policy
- Scaling path: (1) Implement S3 lifecycle policies to archive old crawls to Glacier, (2) consider Parquet/columnar format for bulk analysis instead of storing raw HTML.

## Dependencies at Risk

**python-dotenv recent security fix (1.1.0 → 1.2.2):**
- Risk: See commit 8aa77c2 — `python-dotenv 1.1.0 → 1.2.2` fixed GHSA symlink vulnerability. Upgrade already applied; no action needed.
- Impact: None (fixed)
- Migration plan: N/A

**curl_cffi transitive dependency for TlsFetcher:**
- Risk: `curl_cffi` is a C extension wrapping libcurl, subject to version-specific memory safety issues. No public CVE at time of writing, but C extensions are riskier than pure Python.
- Impact: TlsFetcher (used for JavaScript-heavy retailer sites) could crash or leak memory under certain conditions.
- Migration plan: Monitor curl-cffi releases; switch to a pure-Python async TLS client (e.g., httpx with custom adapter) if memory leaks are discovered.

**Chrome extension uses native Fetch API (no polyfill):**
- Risk: Fetch is standard but older browser versions (pre-2017) don't support it. CarModPicker targets modern Chrome, so this is acceptable.
- Impact: Extension won't work on outdated Chrome versions
- Migration plan: Keep as-is; document minimum Chrome version (current is 90+).

## Missing Critical Features

**No metrics/observability for crawler performance:**
- Problem: Crawlers run but there's no dashboard showing per-adapter success rate, average parse time, or error trends. Admins must manually inspect job reports.
- Blocks: Can't easily identify which adapters are consistently failing or slow. Hard to optimize prioritization.
- Impact: Low visibility into data quality; maintenance is reactive, not proactive.
- Fix approach: Emit crawler metrics (parse_time, success_rate, parse_failures) to CloudWatch or Prometheus. Build admin dashboard.

**No automated crawler recovery or retry scheduling:**
- Problem: If a crawler job fails (e.g., DB timeout, FlareSolverr crash), it doesn't auto-retry. Admin must manually re-trigger.
- Blocks: Lost crawl windows; parts not updated on schedule.
- Impact: Data staleness; users see outdated prices.
- Fix approach: Implement exponential backoff for failed jobs using background-job service. Mark high-priority adapters for immediate retry.

**No pre-crawl validation (e.g., retailer availability check):**
- Problem: Crawler starts on a retailer and hammers it for an hour before discovering the site is down or rate-limiting. Wasted resources.
- Blocks: Can't quickly detect retailer-wide outages or WAF blocks.
- Impact: Wasted crawler capacity; slow overall crawl.
- Fix approach: Add quick health-check endpoint (robots.txt fetch, GET homepage) before starting per-adapter crawl.

## Test Coverage Gaps

**End-to-end Chrome extension auth flow not tested:**
- What's not tested: The full browser-extension auth handoff (extension opens tab → user logs in → page sends token via runtime.sendMessage → extension closes tab). Only unit tests exist for state validation.
- Files: `chrome-extension/src/background.ts` auth handler, but no e2e test
- Risk: Regression in auth flow goes unnoticed until users report login failures.
- Priority: High (auth is critical path)
- Fix approach: Add Playwright test that opens extension popup, initiates login, simulates web app message send, verifies token stored.

**Crawler adapter parsing robustness for real retailer pages:**
- What's not tested: Full integration where adapter is tested against live retailer pages (vs. mocked HTML). Recent adapter fixes (7831fda) addressed real failures, but coverage is incomplete.
- Files: `backend/tests/crawlers/test_*_adapter.py` (unit tests with mocked HTML), but no integration tests against live sites
- Risk: Retailer DOM changes silently break adapters until next crawl cycle (days later).
- Priority: Medium
- Fix approach: Run monthly integration test suite against live retailer pages; auto-alert if parse success rate drops below baseline.

**Concurrent part linking / canonical part updates:**
- What's not tested: Race conditions when two users simultaneously link/unlink the same part or merge canonicals.
- Files: `backend/app/api/endpoints/parts.py` (link endpoints), but no concurrency tests
- Risk: Orphaned or circular canonical references.
- Priority: Medium
- Fix approach: Add pytest-asyncio tests using concurrent.futures to simulate race conditions.

**Build log post author N+1 query fix validation:**
- What's not tested: After fixing the N+1 query (when fixed), test that bulk author fetches use single query, not N.
- Files: `backend/app/api/endpoints/build_logs.py:119+`, but no assertion on query count
- Risk: Regression if future developer reintroduces the loop.
- Priority: Low (only matters after fix is implemented)
- Fix approach: Use SQLAlchemy query profiler in test to assert query count == expected.

---

*Concerns audit: 2026-04-22*
