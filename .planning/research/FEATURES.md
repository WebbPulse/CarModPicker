# Feature Research: Quality Capabilities

**Domain:** Tech-debt audit milestone — quality/health capabilities for a mature Python + TypeScript + AWS monolith
**Researched:** 2026-04-21
**Confidence:** HIGH (grounded in CONCERNS.md inventory + verified tooling docs)

---

## Framing

This is not a product-feature document. "Features" here means **quality capabilities**: what a healthy production codebase at CarModPicker's shape and stage must have, should have, and must not prematurely build. All entries are anchored to the 8 active debt areas from PROJECT.md and the concrete gaps in CONCERNS.md.

The 8 debt areas:
1. **Auth** — auth.py split, 2FA/WebAuthn/OAuth accretion
2. **Crawler** — adapter auto-discovery, parse-failure alerting, parallelization, retry, health-check
3. **Observability** — structured logs, crawler metrics, request tracing, production monitoring
4. **DB/Migrations** — N+1 fix, indexes, migration hygiene, connection pool
5. **Parts/Dedup** — transactional part linking, inference engine maintainability
6. **Frontend** — page/component organization, API client consistency, type-safety
7. **Tests/CI** — backend + frontend coverage, pyright/eslint/bandit gates, concurrency tests
8. **Code-quality** — admin.py split, car_generations_data.py load, dead code, Base* compliance

---

## Table Stakes

Missing these means the team is flying blind, shipping is risky, or quality regression is invisible.

### Observability

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Error tracking (Sentry) | CONCERNS.md: "None detected — no Sentry, LogRocket". Unhandled exceptions in prod are invisible. Low-traffic window is the time to get baseline — not after launch. | S | `sentry-sdk[fastapi]` — auto-instruments FastAPI via `FastApiIntegration` + `StarletteIntegration`; init before app creation; `traces_sample_rate=0.1` for prod to cap cost | #3 Observability |
| Structured log enrichment: correlation ID on every line | Already uses `python-json-logger` + `RequestContextFilter` with correlation ID + user ID. Gap is ensuring crawler jobs emit the same correlation IDs so a job run is traceable end-to-end. | S | Extend `RequestContextFilter` to propagate job_id into log context for crawler runs | #3 Observability |
| Per-adapter crawler metrics | CONCERNS.md: "Admins must manually inspect job reports." No dashboard for success rate, parse time, or failure trends. | M | Emit CloudWatch `PutMetricData` calls at adapter teardown: `parse_success_count`, `parse_failure_count`, `parse_time_ms`, `urls_discovered`. One CloudWatch namespace per adapter. Costs ~$0.30/1000 custom metrics. | #2 Crawler, #3 Observability |
| CloudWatch alarm on parse-failure rate | Parse failures are currently silent data loss. CONCERNS.md: "auto-email superadmins if failures exceed baseline." | S | CloudWatch Alarm on `parse_failure_count / (parse_success_count + parse_failure_count) > 0.5` per adapter, SNS → SES email. Terraform-managed. | #2 Crawler, #3 Observability |
| RDS Performance Insights (query-level) | Already enabled (7-day retention). Gap: nobody is looking at it. Make it part of the N+1 fix validation workflow. | S | No new infra; wire into DB/Migrations phase as the verification tool. | #4 DB/Migrations |

### Testing

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Backend coverage threshold enforced in CI | TESTING.md: coverage XML generated but no `--cov-fail-under` gate. Coverage can silently drop. | S | Add `--cov-fail-under=70` to `pytest.ini` `addopts`. Start at 70, raise incrementally as debt is paid. | #7 Tests/CI |
| Frontend tests run in CI | TESTING.md: "Tests are NOT run in CI for frontend." Frontend logic has zero regression protection. | S | Add `npm test -- --run` step to `frontend-ci.yml` before the build step. Add `coverage.thresholds` in `vitest.config.ts` (`lines: 60` initially). | #7 Tests/CI |
| N+1 regression gate (build logs) | CONCERNS.md: N+1 query in build log posts is a known bug. After fix, must prevent regression. | S | Use `pytest-capquery` (2025-era tool) or manual SQLAlchemy event listener to assert `SELECT` count on `test_build_log_posts` equals 2 (one for posts, one for authors), not N+1. | #4 DB/Migrations, #7 Tests/CI |
| Concurrency test for part linking | CONCERNS.md: "No concurrency tests for part linking; coverage assumes serial execution." Race → orphaned canonical references. | M | `concurrent.futures.ThreadPoolExecutor` with 10 threads simultaneously calling link/unlink; assert no orphans after join. Runs in SQLite in-memory, no external dep. | #5 Parts/Dedup, #7 Tests/CI |
| Adapter smoke test harness | CONCERNS.md: "no integration test across all adapters." Every adapter has unit tests with mocked HTML but no shape validation. | M | A lightweight pytest parametrize over all registered adapter classes; assert they implement required interface methods, have non-empty `discover_product_urls` patterns, and parse fixtures produce `PartData` with required fields. Not live-site — uses fixture HTML. | #2 Crawler, #7 Tests/CI |

### CI/CD Gates

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| pyright in CI (already present, strengthen) | Already runs `pyright` in CI. Gap: strictness level may be too loose. | S | Add `"strict": true` for new files in `pyrightconfig.json` via per-directory overrides. Do not flip global strict — too noisy on brownfield. | #7 Tests/CI, #8 Code-quality |
| bandit in CI (already present, tune) | Already runs `bandit -r app`. Gap: no severity threshold. High-severity findings must fail the build. | S | Add `-l -i` (high severity, high confidence) or `--exit-zero` removal so bandit fails CI on HIGH severity. | #7 Tests/CI |
| eslint no-unused-vars and type-safety rules enforced | CONCERNS.md flags frontend type-safety gaps. eslint already runs but unclear if `@typescript-eslint/no-explicit-any` is error-level. | S | Audit `frontend/.eslintrc` / `eslint.config.*`: ensure `@typescript-eslint/no-explicit-any: error` and `@typescript-eslint/no-unsafe-*` rules are enabled. | #6 Frontend, #7 Tests/CI |
| Migration safety check: no destructive ops without explicit comment | Alembic autogenerate can silently emit `DROP COLUMN` if a model field is removed. A CI lint catches this before it reaches staging. | S | Add CI step: `grep -E "(drop_column|drop_table|drop_constraint)" alembic/versions/*.py` on changed files; fail if found without a `# SAFE:` annotation comment. Script-level, no new dep. | #4 DB/Migrations |
| pip-audit in CI (already present) | Already runs `pip-audit`. Confirms. Keep as-is; no gap. | — | Existing. Note: `python-dotenv` 1.1.0 → 1.2.2 already fixed. | #7 Tests/CI |

### Migration Hygiene

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Backwards-compatible migration discipline | CONCERNS.md: part linking is not transactional. When adding constraints (e.g., `UNIQUE` on `canonical_part_id`), a naive migration will fail on existing data with dupes. | M | Three-phase pattern: (1) add column nullable, (2) backfill data, (3) add constraint. All three phases as separate Alembic revisions. Document the pattern in CONVENTIONS.md. | #4 DB/Migrations, #5 Parts/Dedup |
| Index audit on all FK columns | CONCERNS.md: "full table scans if indexes are missing on join keys." 25+ models, many FK columns. | M | `alembic revision --autogenerate` will catch missing indexes only if `Index()` is declared in models. Audit: run `SELECT * FROM pg_indexes WHERE tablename = '...'` against local Postgres for all FK columns in all 22+ tables. Add `Index()` declarations to models, then autogenerate. | #4 DB/Migrations |
| Connection pool sizing for concurrent crawlers | CONCERNS.md: `DB_POOL_SIZE=20` exhausts under heavy crawl + API concurrency. | S | Set `DB_POOL_SIZE=50, max_overflow=10` for prod App Runner env. Add a connection pool monitoring CloudWatch metric: `pool_checkedout` from SQLAlchemy pool events. | #4 DB/Migrations |

### Crawler Health

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Adapter auto-discovery | CONCERNS.md: "Easy to forget to register new adapters; silent failures if an adapter's import fails." With 114 adapters this is a real maintenance tax. | M | Python `importlib` + directory scan of `crawlers/adapters/` subdirectories; auto-register classes that subclass `RetailerCrawlerAdapter`. Validate each loads without import error at startup. | #2 Crawler, #8 Code-quality |
| Pre-crawl retailer health check | CONCERNS.md: "Crawler starts on a retailer and hammers it for an hour before discovering the site is down." | S | Before `run_crawler()` per adapter: `GET robots.txt` with 5s timeout. 4xx/5xx or timeout → skip adapter, emit `adapter_skipped` CloudWatch metric, log warning. | #2 Crawler |
| Circuit breaker threshold reduction | CONCERNS.md: `RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5` wastes 62s of backoff on clearly-rate-limited sites. | S | Reduce to 2; add 429/503-specific bail path that skips remaining retries immediately and emits `adapter_rate_limited` CloudWatch event. | #2 Crawler |
| Adapter parallelization (inter-adapter) | CONCERNS.md: "sequential adapter execution" — one slow adapter blocks all subsequent. 100+ adapters × slow retailer = hours. | M | `asyncio.gather()` with a semaphore (e.g., max 10 concurrent adapters) over the adapter list in `run_crawlers()`. Each adapter gets its own DB session (already the case per-adapter). | #2 Crawler |

### Dependency Management

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Automated dependency update PRs | No Renovate or Dependabot configured. `python-dotenv` was updated reactively (CONCERNS.md). | S | Enable GitHub Dependabot (`dependabot.yml`) for `pip` (backend), `npm` (frontend + chrome-extension), and `github-actions`. Weekly cadence. Group patch updates into single PR. | #7 Tests/CI |
| curl_cffi monitoring | CONCERNS.md: "C extension, subject to version-specific memory safety issues." Dependabot won't catch CVEs in C extensions until NVD records them. | S | Add `curl_cffi` to a watched list in `pip-audit` run. Subscribe to `curl_cffi` GitHub releases via watch. No automated fix — just awareness. | #7 Tests/CI |

---

## Differentiators

These raise quality meaningfully above table stakes. Build selectively — each requires justification relative to the current traffic level and team size (solo dev).

| Capability | Value Proposition | Complexity | Tool/Library | Debt Area | Build Trigger |
|------------|-------------------|------------|--------------|-----------|---------------|
| OpenTelemetry request tracing | Correlates a user request across FastAPI → DB → S3 → SES. Reveals latency breakdowns invisible in logs. Real value: when a user says "search is slow" you can see exactly which query took 800ms. | L | `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, ADOT collector → CloudWatch. Significant setup; defer unless CloudWatch Insights isn't enough. | #3 Observability | After Sentry + CloudWatch alarms are live and you have a specific "this is still opaque" problem |
| Database-backed feature flags | CONCERNS.md notes rate-limiter `ENABLE_RATE_LIMITING=false` env-var is a risk in prod. Feature flags let ops toggle per-endpoint rate limiting without a deploy. Also enables dark-launching crawler changes. | L | Flagsmith (self-hosted, PostgreSQL-backed) or a lightweight custom `feature_flags` table + FastAPI `Depends()` helper. Flagsmith adds infra complexity (another service). Custom table is ~2 hours of work and fits the existing pattern. Recommend custom table first. | #1 Auth, #2 Crawler | After crawler parallelization lands and you want safe dark-launch of new adapter behavior |
| Optimistic concurrency on part linking | CONCERNS.md: "Part linking logic is not transactional — race conditions can leave orphaned canonical references." A `version_id` column on `canonical_parts` catches concurrent writes. | S | SQLAlchemy `__mapper_args__ = {"version_id_col": version_id}` on the canonical part model. Raises `StaleDataError` on concurrent write; caller retries. Pairs with the concurrency test above. | #5 Parts/Dedup | Schedule with the transactional part-linking fix |
| Query profiling assertions in CI (pytest-capquery) | Prevents N+1 regressions from being introduced after fixes are made. Once the build-log N+1 is fixed, the fix must not regress. | M | `pytest-capquery` wraps SQLAlchemy engine at driver level; snapshot the expected query count per test; fail on deviation. Requires careful fixture scoping with xdist. | #4 DB/Migrations, #7 Tests/CI | Immediately after the N+1 fix lands |
| Synthetic canary crawler run | Run a known-good adapter against a known-stable retailer on a schedule (e.g., daily) and alert if parse success drops to 0. Catches retailer DOM changes within 24h instead of during the next manual crawl audit. | M | EventBridge rule → Lambda or App Runner task that runs a single "canary" adapter (pick the most stable retailer). Compare against expected part count ± 10%. Emit CloudWatch alarm if diverges. | #2 Crawler, #3 Observability | After per-adapter CloudWatch metrics are live |
| S3 lifecycle policy for crawl archive | CONCERNS.md: "S3 HTML snapshots will add significant volume. No built-in retention policy." | S | Terraform: `aws_s3_bucket_lifecycle_configuration` on `carmodpicker-prod-crawl-html` — transition to Glacier after 90 days, delete after 365 days. 30-minute Terraform task. | #2 Crawler | Alongside any crawler storage work |

---

## Anti-Features

Explicitly deferred. These will be requested, seem reasonable, but create disproportionate complexity at the current scale.

| Anti-Feature | Why Requested | Why Avoid | What to Do Instead | Debt Area |
|--------------|--------------|-----------|-------------------|-----------|
| Custom Prometheus + Grafana stack | Full metric visibility, custom dashboards | Ops burden: another two services to run (Prometheus server + Grafana), alerting pipeline complexity, no native AWS integration. App Runner doesn't expose a scrape endpoint by default. | CloudWatch custom metrics (`PutMetricData`) + CloudWatch dashboards. Same data, managed service, zero new infra. | #3 Observability |
| Microservices split (crawler as separate service) | Crawlers are a distinct subsystem; decoupling seems clean | At 114 adapters and solo-dev velocity, splitting crawler into a separate service adds a deployment pipeline, cross-service auth, and network overhead with zero scaling benefit at current traffic. App Runner + ECS Fargate tasks already give you "run crawlers independently." | Keep crawler in the monolith. The ECS Fargate task path already isolates crawler runs from API traffic. | #2 Crawler |
| K8s migration | Container orchestration, horizontal scaling | App Runner handles auto-scaling with zero ops. K8s adds ~40h of migration and ongoing ops tax. Revisit only if App Runner pricing or limits become a constraint. | Stay on App Runner. Add read replica on RDS if DB becomes the bottleneck. | Infra |
| LaunchDarkly or full Flagsmith hosted | Enterprise feature flags | Overkill for a solo dev / low-traffic platform. LaunchDarkly is $200+/mo. Flagsmith hosted adds a vendor dependency. | Simple `feature_flags` DB table + cache. If complexity grows, self-host Flagsmith later. | #1 Auth |
| OpenAPI contract tests / Pact | API schema drift detection between frontend and backend | Valuable at team scale. At solo dev + monorepo the contract is enforced by pyright (shared types) and the TypeScript API client is the single consumer. Pact adds test infrastructure without solving a real current problem. | Keep TypeScript API client as the contract. Add `tsc --noEmit` on the client types against the OpenAPI schema using `openapi-typescript` if drift becomes a problem. | #6 Frontend |
| Error-budget-based deploys | SRE practice: block deploys if error rate exceeds budget | No SLO exists; traffic is near zero. Without an SLO the error budget is meaningless. Adds process overhead with no signal. | Add Sentry + CloudWatch alarms first. Define an SLO (e.g., 99.5% requests < 500ms) only once you have baseline data. | #3 Observability |
| SBOM generation + supply chain signing | Compliance, SLSA provenance | Not a B2B SaaS; no compliance requirement. pip-audit + npm audit already cover known CVEs. SBOM adds tooling (Syft/Grype) with no actionable output for this context. | Continue pip-audit + npm audit in CI. Revisit when serving enterprise customers or when compliance is a sales requirement. | #7 Tests/CI |
| Real-time WebSocket crawler progress | Live admin dashboard showing crawl progress | High complexity (needs SSE or WebSocket endpoint, state broadcast, reconnect logic). Admin already gets email on job completion. | Background job status polling via existing `GET /api/admin/jobs/{id}` endpoint is sufficient. Polish the admin dashboard UI instead. | #2 Crawler |

---

## Feature Dependencies

```
[Per-adapter CloudWatch metrics]
    └──enables──> [CloudWatch parse-failure alarm]
                      └──enables──> [Canary crawler run]

[N+1 fix (build logs)]
    └──requires──> [N+1 regression gate (pytest-capquery)]

[Adapter parallelization]
    └──requires──> [Pre-crawl health check]  (parallelizing without health checks amplifies hammering)
    └──enables──> [Canary crawler run]  (stable parallel runner makes canary meaningful)

[Optimistic concurrency (part linking)]
    └──requires──> [Concurrency test for part linking]  (gate must exist before the fix to catch regressions)

[Coverage threshold CI gate]
    └──enables──> [Frontend tests in CI]  (threshold only meaningful once tests run in CI)

[Adapter auto-discovery]
    └──enables──> [Adapter smoke test harness]  (harness parametrizes over auto-discovered adapters)
```

---

## Prioritization Matrix

| Capability | Dev Impact | Risk Reduction | Cost (S/M/L) | Priority |
|------------|-----------|---------------|------------|---------|
| Sentry error tracking | HIGH — ends "flying blind" | HIGH | S | P1 |
| Frontend tests in CI | HIGH — closes zero-protection gap | HIGH | S | P1 |
| Backend coverage threshold (--cov-fail-under) | MEDIUM | MEDIUM | S | P1 |
| Migration safety CI check (no DROP without annotation) | MEDIUM | HIGH | S | P1 |
| Per-adapter CloudWatch metrics | HIGH — crawler visibility | HIGH | M | P1 |
| Pre-crawl retailer health check | MEDIUM | MEDIUM | S | P1 |
| Circuit breaker threshold reduction | LOW | MEDIUM | S | P1 |
| N+1 regression gate (pytest-capquery) | MEDIUM | HIGH | M | P1 |
| Concurrency test for part linking | MEDIUM | HIGH | M | P1 |
| Adapter auto-discovery | MEDIUM | MEDIUM | M | P1 |
| CloudWatch parse-failure alarm | HIGH | HIGH | S | P1 |
| Index audit + FK index additions | MEDIUM | MEDIUM | M | P1 |
| Connection pool resize (prod env) | LOW | MEDIUM | S | P1 |
| Dependabot configuration | LOW | MEDIUM | S | P2 |
| Backwards-compatible migration discipline (documented pattern) | MEDIUM | HIGH | S | P2 |
| Optimistic concurrency on part linking | MEDIUM | HIGH | S | P2 |
| Adapter smoke test harness | MEDIUM | MEDIUM | M | P2 |
| bandit severity threshold | LOW | MEDIUM | S | P2 |
| eslint any/unsafe rules to error | MEDIUM | MEDIUM | S | P2 |
| S3 lifecycle policy (crawl archive) | LOW | LOW | S | P2 |
| Adapter parallelization | HIGH — crawl speed | LOW | M | P2 |
| Query profiling assertions in CI | MEDIUM | HIGH | M | P2 |
| Feature flags (custom DB table) | MEDIUM | MEDIUM | M | P3 |
| Canary crawler run | MEDIUM | MEDIUM | M | P3 |
| OpenTelemetry tracing | LOW at current traffic | LOW | L | P3 |

**Priority key:**
- P1: Build this milestone — directly closes a CONCERNS.md gap, low/medium complexity
- P2: Build this milestone if the phase addresses the related debt area — medium complexity, high value
- P3: Defer or build only if adjacent work makes it cheap

---

## Sources

- CONCERNS.md (authoritative debt inventory, 2026-04-22) — all table-stakes items are directly traceable to entries there
- TESTING.md (testing patterns audit, 2026-04-22) — CI gaps, coverage configuration, frontend test absence
- INTEGRATIONS.md (integration audit, 2026-04-22) — observability gaps, CloudWatch setup, no Sentry confirmed
- [Sentry FastAPI integration docs](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [pytest-capquery for N+1 detection](https://dev.to/fmartins/stop-testing-your-code-and-ignoring-your-database-catching-n1-in-pytest-4pd5)
- [Vitest coverage thresholds](https://vitest.dev/guide/coverage)
- [SQLAlchemy optimistic locking](https://oneuptime.com/blog/post/2026-01-25-optimistic-locking-sqlalchemy/view)
- [Flagsmith FastAPI integration](https://medium.com/@r_bilan/integrating-flagsmith-with-fastapi-a-step-by-step-guide-for-ff-f85ac90bc6a3)
- [OpenTelemetry + FastAPI + CloudWatch](https://aws.amazon.com/blogs/mt/introducing-opentelemetry-promql-support-in-amazon-cloudwatch/)
- [Alembic backwards-compatible migrations](https://medium.com/exness-blog/alembic-migrations-without-downtime-a3507d5da24d)
- [Renovate vs Dependabot 2025](https://www.turbostarter.dev/blog/renovate-vs-dependabot-whats-the-best-tool-to-automate-your-dependency-updates)

---
*Feature research for: CarModPicker tech-debt milestone — quality capabilities*
*Researched: 2026-04-21*
