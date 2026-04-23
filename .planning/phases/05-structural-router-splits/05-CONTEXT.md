# Phase 5: Structural Router Splits - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Decompose two oversized endpoint files into well-scoped sub-packages, swap the JWT library, document the Chrome-extension API contract, and prove the per-route auth dependency surface with integration tests. The ROADMAP-locked outcomes:

1. `backend/app/api/endpoints/admin.py` (2,068 lines, 23 routes) split into `admin/` package: `stats.py`, `jobs.py`, `crawlers.py`, `db_ops.py`, `parts.py`, `_helpers.py`. Old `admin.py` deleted in the same PR as the split.
2. `backend/app/api/endpoints/auth.py` (1,191 lines, 24 routes) split into `auth/` package: `core.py`, `two_factor.py`, `webauthn.py`, `oauth.py`, `_helpers.py`. Old `auth.py` deleted in the same PR as the split.
3. `python-jose[cryptography]==3.5.0` replaced with `PyJWT 2.12.1`; zero `JWTError` references remain; every `jwt.decode` call has an explicit `algorithms=[...]` argument.
4. Every split route explicitly redeclares its auth dependency (`Depends(get_current_user)` for auth, `Depends(get_current_admin_user)` for admin). A per-route 401/403 integration test covers the dependency surface.
5. Chrome extension's API contract documented at `chrome-extension/API_CONTRACT.md`. Extension end-to-end flow (log in on web app → token handoff to extension → scrape part → log out) succeeds post-refactor with zero extension-code changes.

Internal ordering (from ROADMAP): admin split (ADMIN-01—04) first — low-stakes dry run of the split pattern; Chrome extension is not in admin's critical path. Then PyJWT migration as its own dedicated PR. Then auth split (AUTH-01—06) — highest-stakes refactor, done last on the already-modernized library.

Out of scope for this phase: adding new routes, changing auth semantics, modifying subscription gating, refactoring `backend/app/api/dependencies/auth.py` beyond the PyJWT swap + `settings.JWT_ALGORITHM` hoist, rewriting `backend/app/services/job_service.py`.

</domain>

<decisions>
## Implementation Decisions

### PyJWT migration (AUTH-04)

- **D-01:** Swap timing: **dedicated PR between the admin split and the auth split**. Order across Phase 5: admin split PR(s) → PyJWT swap PR → auth split PR(s). Rationale: admin split exercises the sub-package pattern on the non-critical-path surface first; PyJWT swap lands on the un-split auth.py + dependencies/auth.py so the library change is reviewed in a narrow, focused diff; the auth split is then done in the new library with the new exception class from day one.
- **D-02:** Exception replacement literal: `from jwt import InvalidTokenError` (re-exported from `jwt.exceptions`). Every `except JWTError` / `except JWTError as e:` becomes `except InvalidTokenError` / `except InvalidTokenError as e:`. Touches 4 sites in `backend/app/api/endpoints/auth.py` and 3 sites in `backend/app/api/dependencies/auth.py`. Satisfies REQ-AUTH-04's "`JWTError` → `InvalidTokenError`" literal.
- **D-03:** Algorithm-explicit tightening: hoist `ALGORITHM = "HS256"` from `backend/app/api/dependencies/auth.py:18` to a new `settings.JWT_ALGORITHM` field in `backend/app/core/config.py` (default `"HS256"`). Every `jwt.encode(..., algorithm=settings.JWT_ALGORITHM)` and `jwt.decode(..., algorithms=[settings.JWT_ALGORITHM])` reads from config.
- **D-04:** Regression grep test: `backend/tests/test_jwt_algorithm_regression.py` — greps `backend/app/**/*.py` for `jwt.decode(` statements that do NOT contain `algorithms=[` in the same statement (within 2 lines). Assertion-based. Matches the Phase 3 QUAL-02 / QUAL-07 and Phase 4 session.query regression-guard pattern. Fails CI on any future bare `jwt.decode` call.
- **D-05:** Token compatibility parity test: `backend/tests/test_pyjwt_migration.py` — one test that encodes a dummy payload with `jose.jwt.encode(payload, secret, algorithm="HS256")`, decodes with `jwt.decode(token, secret, algorithms=["HS256"])` (PyJWT), asserts the payload matches bit-for-bit. Runs once in CI. Protects against theoretical library-behavioral drift. HS256 signatures are byte-identical across libraries, so this test is expected to pass — it's the explicit proof for the PR reviewer that the swap is safe for in-flight tokens. The test can stay in the repo post-migration (deletes one sanity check for future migrations) OR be deleted with the `python-jose` dependency (Claude's Discretion — see below).
- **D-06:** Requirements pin: `PyJWT==2.12.1` exact version per REQ-AUTH-04. Add to `backend/requirements.txt`; remove `python-jose[cryptography]==3.5.0` in the same PR.
- **D-07:** `ALGORITHM` in `dependencies/auth.py:18` becomes a reference to `settings.JWT_ALGORITHM` (not deleted — kept as a module-level constant that reads from settings, for import ergonomics inside dependency helpers). `ALGORITHM = settings.JWT_ALGORITHM`.

### Sub-package composition — URL restructure (ADMIN-01, ADMIN-03, AUTH-01, AUTH-02)

- **D-08:** Each sub-module exports its own `router = APIRouter()`. Routes are decorated with paths relative to the sub-module's mounted prefix. Each sub-router is registered directly in `backend/app/main.py` via `endpoint_registry.register_endpoint(...)` at its own sub-prefix — one registration per sub-module instead of one per package. This replaces the current 2 registrations (`auth.router` at `/auth`, `admin.router` at `/admin`) with 9 registrations (4 auth + 5 admin).
- **D-09:** Admin URL tree, post-restructure (**aggressive — all paths consolidate under sub-module prefixes**):

  | Sub-module | Prefix | Routes |
  |-----------|--------|--------|
  | admin/stats | `/admin/stats` | `/table-counts` (GET), `/crawl-bucket` (GET) |
  | admin/jobs | `/admin/jobs` | `/` (GET list), `/{job_id}` (GET), `/{job_id}/crawler-progress` (GET), `/{job_id}/cancel` (POST) |
  | admin/crawlers | `/admin/crawlers` | `/` (GET list), `/run` (POST) **[EventBridge]**, `/rescrape-archives` (POST) **[EventBridge, moved from `/admin/crawled-pages/rescrape-archives`]**, `/service-account` (GET, moved from `/admin/service-accounts/crawler`) |
  | admin/db_ops | `/admin/db-ops` | `/migrations/run` (POST, moved from `/admin/migrations/run`), `/migrations/current` (GET), `/init/car-generations` (POST), `/init/part-categories` (POST), `/cars/delete-all` (POST), `/parts/delete-all` (POST), `/part-manufacturers/delete-all` (POST) |
  | admin/parts | `/admin/parts` | `/lookup-by-url` (GET), `/{part_id}/link-group` (GET), `/promote-canonical` (POST), `/unlink` (POST), `/link` (POST), `/rescan` (POST) |

- **D-10:** Auth URL tree, post-restructure (**aggressive — `/auth/google/*` moves under `/auth/oauth/google/*`**):

  | Sub-module | Prefix | Routes |
  |-----------|--------|--------|
  | auth/core | `/auth` | `/token` (POST), `/token/2fa` (POST), `/verify-email` (POST), `/verify-email/confirm` (GET), `/reset-password` (POST), `/reset-password/confirm` (POST), `/logout` (POST) |
  | auth/two_factor | `/auth/2fa` | `/setup` (POST), `/verify` (POST), `/disable` (POST) |
  | auth/webauthn | `/auth/webauthn` | `/register/options` (POST), `/register/verify` (POST), `/login/options` (POST), `/login/verify` (POST), `/credentials` (GET), `/credentials/{credential_id}` (PATCH), `/credentials/{credential_id}` (DELETE) |
  | auth/oauth | `/auth/oauth` | `/google` (POST, moved from `/auth/google`), `/google/signup` (POST), `/google/link` (POST), `/google/connect` (POST), `/2fa` (POST), `/` (GET list), `/{account_id}` (DELETE) |

- **D-11:** EventBridge Terraform update lands in the same PR as the admin split. Two schedules change path:
  - `/admin/crawlers/run` — unchanged path
  - `/admin/crawled-pages/rescrape-archives` → `/admin/crawlers/rescrape-archives`
  The Terraform `aws_scheduler_schedule` resource(s) in `terraform/` get path updates. Deploy sequencing: Terraform `apply` must occur AFTER the backend image deploys the restructured routes (run `terraform plan` in CI, `apply` in the deploy pipeline after the backend rolls out). If Terraform applies before the backend, EventBridge will 404 for one deploy cycle — acceptable for staging but must be sequenced correctly for prod. Document the sequencing in the plan's SUMMARY.md.
- **D-12:** ADMIN-03 literal-path note: REQUIREMENTS.md mentions `/api/cron/run-crawler-schedule` as the EventBridge contract path, but the current codebase does not use this path — it uses `/admin/crawlers/run` + `/admin/crawled-pages/rescrape-archives` with `x_admin_cron_key` header for EventBridge invocations. The ADMIN-03 literal is interpreted as "EventBridge-invoked routes stay on their current paths or move deliberately with Terraform update in the same PR" — the aggressive restructure moves `rescrape-archives` but Terraform updates match. `/admin/crawlers/run` path is preserved for EventBridge consistency.
- **D-13:** Frontend web app update scope (in the same PR as each split): React frontend's API clients in `frontend/src/api/*.ts` update to the new URL paths. Grep scope: `/admin/migrations`, `/admin/init/`, `/admin/cars/delete-all`, `/admin/parts/delete-all`, `/admin/part-manufacturers/delete-all`, `/admin/crawled-pages/rescrape-archives`, `/admin/service-accounts/crawler`, `/auth/google/*`. Each reference updates to the new path. `frontend/npm run type-check` + existing unit tests are the regression guard.
- **D-14:** Chrome extension is NOT affected by the URL restructure. The extension's API calls (confirmed by scout): `/users/me`, `/categories/`, `/retailers/`, `/retailers/get-or-create`, `/parts/*`, `/part-manufacturers/`, `/car-generations/`, `/images/*`, `/crawled-pages/scrape`. NONE are under `/auth/*` or `/admin/*`. The extension holds a bearer token received via `chrome.runtime.sendMessage` from the web app (cross-origin handoff) and attaches `Authorization: Bearer <token>` to every API request. Zero extension-code changes needed.
- **D-15:** Route decorators use paths relative to the sub-module prefix. Example: `admin/db_ops.py` has `@router.post("/migrations/run")` (not `@router.post("/admin/db-ops/migrations/run")`) — the `/admin/db-ops` prefix is applied at main.py's `register_endpoint(...)` call.
- **D-16:** OpenAPI snapshot (Phase 1 SAFE-05) regenerates + commits in the restructure PR per Phase 1 D-26 convention. The snapshot diff IS the review artifact. The PR description calls out every moved route as intentional; reviewer verifies nothing else drifted.
- **D-17:** Import compat: hard migration. Update every caller of `from app.api.endpoints.auth import ...` / `from app.api.endpoints.admin import ...` in the same PR as the split. No re-export shim — REQ-AUTH-01 / REQ-ADMIN-01 lock "old file deleted in same PR", so there's no legacy to preserve. Expected callers: tests, possibly `backend/app/api/utils/admin_endpoint_patterns.py`, and `backend/app/main.py` itself.

### Helper file boundaries

- **D-18:** `auth/_helpers.py` (ROADMAP-locked filename) contains **only cross-module helpers**:
  - `_issue_login_response(user: DBUser) -> dict` — used by core.py (login, 2FA login) + oauth.py (Google sign-in, Google signup) + two_factor.py (2FA verify).
  - `_maybe_2fa_challenge(user: DBUser) -> Optional[dict]` — used by core.py (login) + oauth.py (Google sign-in).
- **D-19:** WebAuthn-local helpers stay in `auth/webauthn.py`: `_b64url_encode`, `_b64url_decode`, `_build_challenge_token`, `_decode_challenge_token`.
- **D-20:** OAuth-local helpers stay in `auth/oauth.py`: `_ensure_google_enabled`, `_verify_google_or_400`, `_suggest_username`, `_decode_purpose_token`.
- **D-21:** `admin/_helpers.py` (NEW — not named in ROADMAP but parallels `auth/_helpers.py` for package consistency). Contains background-job lifecycle helpers used by multiple admin sub-routers:
  - `_stamp_heartbeat(job_id: UUID)` — used by crawlers.py (run), potentially db_ops.py (migrations/run as a background job).
  - `_heartbeat_loop(job_id: UUID, interval: float)` — same.
  - `_get_superadmin_emails(db: Session) -> List[str]` — used by `_notify_job_completion`.
  - `_notify_job_completion(job_id: UUID)` — used by crawlers.py + any future async admin op.
- **D-22:** `_verify_cron_key` stays in `admin/crawlers.py` (only EventBridge-called routes use it; zero cross-module).
- **D-23:** `_get_alembic_directory` + `_init_result` stay in `admin/db_ops.py` (only migration/init endpoints use them).
- **D-24:** ECS task launchers (`_launch_ecs_crawler_task`, `_run_crawlers_in_process`, `_launch_ecs_rescrape_task`, `_run_rescrape_in_process` — ~300 lines total) stay inline in `admin/crawlers.py`. No extraction to a service module in this phase (would be cross-phase scope creep).
- **D-25:** Parts helpers (`_first_listing_for`, `_link_group_member`) stay in `admin/parts.py`.
- **D-26:** Every new file in `auth/` and `admin/` packages includes module-level `logger = logging.getLogger(__name__)` per Phase 3 D-33—D-37 convention. No `Depends(get_logger)` reintroduction; Phase 3's grep regression guard catches violations.

### 401/403 integration test shape (ADMIN-02, AUTH-03)

- **D-27:** Test shape: **parametrized over `(method, path, required_role)` tuples**, one parametrized test per package.
  - File 1: `backend/tests/test_admin_auth_coverage.py` — covers all 23 admin routes.
  - File 2: `backend/tests/test_auth_auth_coverage.py` — covers all auth routes that require `get_current_user` (logout, 2FA setup/verify/disable, WebAuthn credentials list/rename/delete, OAuth connect/list/delete — NOT public routes like `/token`, `/verify-email`, `/reset-password`, Google sign-in which are deliberately pre-auth).
- **D-28:** Per-route assertions (admin routes): (a) no auth header → 401, (b) regular-user token → 403, (c) admin-user token → 2xx or a non-auth business failure (e.g., 404 for a missing job_id). Test dispatches via FastAPI TestClient.
- **D-29:** Per-route assertions (auth-protected routes): (a) no auth header → 401, (b) valid-user token → 2xx or expected non-auth failure. No role split needed (only `get_current_user` gating).
- **D-30:** Drift guard: each test module ends with a sanity-check test: `assert len(_route_tuples) == len(app.routes filtered by /admin prefix)` (or `/auth` for the auth file, minus public routes). A new route added without a tuple fails this assertion; CI blocks the PR. Combined with the Phase 1 OpenAPI snapshot test, drift is double-gated.
- **D-31:** Public-route allow-list: the auth coverage test file maintains an inline list of auth routes that are INTENTIONALLY public (`/auth/token`, `/auth/token/2fa`, `/auth/verify-email`, `/auth/verify-email/confirm`, `/auth/reset-password`, `/auth/reset-password/confirm`, `/auth/oauth/google` POST, `/auth/oauth/google/signup`, `/auth/oauth/google/link`, `/auth/oauth/2fa`). These are excluded from the 401-assertion test. Any new public route requires a deliberate addition to this allow-list — review-gated.
- **D-32:** Fixtures reuse `create_and_login_user` (regular user token), plus a new `create_and_login_admin` fixture if one doesn't already exist in `backend/tests/conftest.py`. Scout confirmed `test_admin_user` fixture exists from Phase 1 context — reuse it.
- **D-33:** Tests run on the default SQLite in-memory fixture (no Postgres needed — these are auth-surface tests, not concurrency). `pytest -n auto` safe via the existing per-worker DB isolation.

### Chrome extension documentation and validation (AUTH-05, AUTH-06)

- **D-34:** `chrome-extension/API_CONTRACT.md` is **generated from `app.openapi()`** via a new script at `backend/scripts/generate_ext_api_contract.py`.
- **D-35:** Generator behavior:
  1. Instantiates the FastAPI app, calls `app.openapi()`.
  2. Filters the spec to endpoints the extension calls. Allow-list lives inline in the script as a constant `EXTENSION_ENDPOINTS = [...]` — a hand-maintained list of `(method, path)` tuples mirroring the paths identified by the scout (`/users/me` GET, `/categories/` GET, `/retailers/` GET, `/retailers/get-or-create` POST, `/parts/check-url` GET, `/parts/{part_id}` GET, `/parts/find-by-part-manufacturer-and-part-number` GET, `/parts/{part_id}/append-images` POST, `/parts/` POST, `/parts/{part_id}/listings` POST, `/part-manufacturers/` GET, `/car-generations/` GET, `/images/by-source-url` GET, `/images/upload` POST, `/crawled-pages/scrape` POST).
  3. For each endpoint, emits a Markdown section: method + path, description (from OpenAPI summary/description), request shape (headers, query params, body schema flattened), response shape (success + error statuses with schemas flattened), auth requirement.
  4. Writes to `chrome-extension/API_CONTRACT.md`.
- **D-36:** Drift guard: `backend/tests/test_ext_api_contract_up_to_date.py` — a pytest that runs the generator, captures the output, reads the committed `chrome-extension/API_CONTRACT.md`, asserts they match. Developer updates the extension endpoint list → regenerates locally → commits the new `.md`. CI fails if the committed doc is stale.
- **D-37:** Initial generation + commit happens in a PR that can land independently of the auth split (separable work). Recommended sequencing: generate the contract BEFORE the auth split, so the auth-split reviewer can verify the contract's auth claims against the split code.
- **D-38:** AUTH-05 validation: **manual UAT checklist, one-time post-deploy on staging**. Checklist recorded in `05-HUMAN-UAT.md` (or whatever the existing UAT artifact convention is). Steps:
  1. Log in on web app at staging (carmodpicker.com staging URL) — verify token received.
  2. Open extension popup, verify "Connected as <username>" state.
  3. Navigate to a retailer product page (a known-good retailer from Phase 1 characterization — e.g., briantooleyracing).
  4. Trigger scrape, verify POST `/parts/` returns 2xx and the part appears in the user's build-list workflow.
  5. Log out on web app, verify extension shows disconnected state within reasonable propagation time (the extension may still hold a cached token until the next action — acceptable per current design).
- **D-39:** No new Playwright / backend-simulated-extension-request tests in this phase. Rationale: the extension never calls `/auth/*` or `/admin/*`, so the "risk" surface for the AUTH split is limited to bearer-token decoding via `get_current_user`. That's already covered by the Phase 1 characterization tests, the PyJWT parity test (D-05), and the per-route 401/403 tests (D-27).
- **D-40:** The ext-ext integration test (backend simulating ext request with `Authorization: Bearer`) was considered and deferred. The ext's request shape is functionally identical to any other authenticated API call; per-route 401/403 coverage captures the auth dependency correctness. If a CORS-or-origin regression specifically affects the extension in the future, add a dedicated test at that time.

### Execution sequencing across Phase 5

- **D-41:** Phase 5 PR order (dependency-honest):
  1. **PR 1 (admin split):** Admin decomposition to `admin/` package + Terraform EventBridge path updates + frontend admin-UI path updates + `admin/_helpers.py` + OpenAPI snapshot regen + `test_admin_auth_coverage.py`. Single PR — the "dry run" for the split pattern. Low Chrome-extension stakes (ext doesn't touch `/admin/*`).
  2. **PR 2 (PyJWT migration):** Swap `python-jose` → `PyJWT 2.12.1` in place (before auth split). Swap `JWTError` → `InvalidTokenError`. Hoist `ALGORITHM` to `settings.JWT_ALGORITHM`. Add parity test (D-05) + algorithm-explicit regression grep test (D-04). Auth.py still monolithic at this point.
  3. **PR 3 (API_CONTRACT generator + initial contract):** Write `backend/scripts/generate_ext_api_contract.py` + `chrome-extension/API_CONTRACT.md` + `test_ext_api_contract_up_to_date.py`. Can land parallel to PR 2 if the contract doc generator is isolated.
  4. **PR 4 (auth split):** Auth decomposition to `auth/` package + `/auth/google/*` → `/auth/oauth/google/*` restructure + frontend web-app path updates + `auth/_helpers.py` + OpenAPI snapshot regen + `test_auth_auth_coverage.py`. Final PR; most hazardous; guarded by Phase 1 characterization + PyJWT parity + contract doc.
  5. **Post-merge (staging UAT):** Run the D-38 manual UAT checklist on staging. Record result in UAT artifact. If pass → phase closes. If fail → revert-or-fix depending on severity.
- **D-42:** Each PR is a discrete commit or small commit chain. Sub-module extraction commits inside PR 1 and PR 4 can be per-sub-module (5 commits for admin, 4 commits for auth) for reviewer navigation, but the PR lands atomically — old file is deleted in the same PR as the new package per REQ-AUTH-01 / REQ-ADMIN-01.

### Characterization + regression guardrails inherited

- **D-43:** Phase 1 auth characterization tests (SAFE-06, 7 happy-path flows — signup/verify, login, 2FA enroll/challenge, WebAuthn register/assert, Google sign-in, Google account link, password-reset) MUST stay green through every PR in Phase 5. They are the end-to-end guardrail for the refactor.
- **D-44:** Phase 1 OpenAPI snapshot test (SAFE-05) IS the URL-drift guard. Legitimate drift from the admin/auth URL restructure regenerates the snapshot (committed in the same PR per Phase 1 D-26).
- **D-45:** Phase 3 QUAL-02 / QUAL-07 regression grep tests + Phase 4 session.query regression grep test run on every PR — every new file inherits module-level `logger = logging.getLogger(__name__)` and `db.scalars(select(...))` patterns; grep guards catch violations.
- **D-46:** `settings.JWT_ALGORITHM` default stays `"HS256"`. No algorithm rotation in this phase.

### Claude's Discretion

- Exact filenames for internal scripts (e.g., `backend/scripts/generate_ext_api_contract.py` vs `backend/scripts/generate_api_contract.py`).
- Whether the PyJWT parity test (D-05) stays in the repo after migration or is deleted with the `python-jose` dependency. Recommendation: keep as a guard against future library swaps; delete if it becomes a flaky liability.
- Whether the drift-guard assertion in D-30 (tuple count vs app.routes count) lives at the top of the parametrized test function or in a separate `test_route_coverage_complete()` function within the same file.
- Whether fixture `create_and_login_admin` is added to the shared `conftest.py` or inlined in the two new coverage test files (recommend shared conftest for reuse by future admin tests).
- Per-sub-module commit granularity inside PR 1 + PR 4 (5 commits vs 1 squash — reviewer preference).
- Whether `admin/_helpers.py` gets a docstring pointing to the auth/_helpers.py convention for package consistency.
- Name of the `test_admin_auth_coverage.py` / `test_auth_auth_coverage.py` files (alternatives: `test_admin_route_protection.py`, `test_auth_dependency_coverage.py`).
- Exact Markdown structure of the generated `chrome-extension/API_CONTRACT.md` (sections, heading levels, code-block formatting for schemas) — script author's call.
- Whether the PyJWT parity test uses a static secret or `settings.SECRET_KEY`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone-level framing

- `.planning/PROJECT.md` — Vision, Active requirements (`Auth / account-flow refactor` and `General code-quality sweep` include admin.py split), Key Decisions (tech-debt milestone, no new features), Constraints (Chrome extension must keep working, backend tests stay on SQLite).
- `.planning/REQUIREMENTS.md` §"Auth Refactor" (AUTH-01 through AUTH-06) — precise acceptance criteria with locked literals (`PyJWT 2.12.1`, `InvalidTokenError`, `/api/auth/*` URL prefix, characterization tests pass, API_CONTRACT.md coverage).
- `.planning/REQUIREMENTS.md` §"Admin Module Split" (ADMIN-01 through ADMIN-04) — package file list, 401/403 test coverage literal, EventBridge contract preservation, service coupling reduction via Depends().
- `.planning/ROADMAP.md` §"Phase 5: Structural Router Splits" — Goal, Depends on (Phase 1, Phase 4), 5 Success Criteria TRUE conditions, Internal Note locking admin-before-auth order.
- `.planning/STATE.md` — Current progress, blockers carrying forward.
- `CLAUDE.md` (repo root) — Project instructions: Alembic autogenerate-only, `pytest -n auto` contract, `BaseEndpointRouter` / `EndpointRegistry` patterns, Chrome extension CORS allowances.

### Phase 1 decisions that carry forward

- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-11 — `MetaData(naming_convention=...)` on `Base` (no Phase 5 coupling, contextual).
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-15—D-19 — Auth characterization tests (7 happy-path flows). These MUST stay green through every Phase 5 PR. They are the end-to-end guardrail.
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-24—D-27 — OpenAPI snapshot test. Legitimate drift regenerates + commits per Phase 1 D-26 convention.
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §"Code Context" — Chrome extension auth flow (AUTH-05 in Phase 5) is called out; the 7 characterization tests MUST be green before Phase 5 starts.

### Phase 2 decisions that interact

- `.planning/phases/02-observability/02-CONTEXT.md` §D-09 — Sentry scope processor attaches `user_id` + `request_id`. Any new errors from Phase 5's refactor (e.g., unexpected JWT decode failures during PyJWT swap) surface in Sentry with full context.
- `.planning/phases/02-observability/02-CONTEXT.md` §D-44—D-48 — request_id / user_id log propagation. Phase 5's new files inherit the root logger + filter path via `logger = logging.getLogger(__name__)`.

### Phase 3 decisions that carry forward (directly applicable)

- `.planning/phases/03-non-breaking-internal-improvements/03-CONTEXT.md` §D-33—D-37 — Module-level `logger = logging.getLogger(__name__)` convention. **Every new file in auth/ and admin/ packages MUST use this pattern.** Phase 3 D-35 explicitly says "Phase 5 inherits this convention". No `Depends(get_logger)` reintroduction.
- `.planning/phases/03-non-breaking-internal-improvements/03-CONTEXT.md` §D-36 — `get_logger` export still available through Phase 5. Removal decision deferred to late Phase 5 / early Phase 6 depending on whether any callers remain post-auth-sweep.

### Phase 4 decisions that carry forward (directly applicable)

- `.planning/phases/04-db-parts-hardening/04-CONTEXT.md` §D-06—D-11 — `db.query()` → `db.scalars(select(...))` migration. Phase 4 §D-44 explicitly says Phase 5's new files "use the modern API from day one". `test_session_query_regression.py` grep guard (D-09) fails CI on any `db.query(` reintroduction.
- `.planning/phases/04-db-parts-hardening/04-CONTEXT.md` §D-33 — `query_counter` fixture. Phase 4 §D-45 invites Phase 5's admin + auth integration tests to use it to catch N+1 regressions introduced during the split. Not strictly required; useful if a plan surfaces ORM concerns.
- `.planning/phases/04-db-parts-hardening/04-CONTEXT.md` §D-01—D-05 — Postgres test side-car. Available for Phase 5 if needed; 401/403 coverage tests don't need it (SQLite-safe per D-33 above).

### Codebase context

- `.planning/codebase/STRUCTURE.md` — Backend package layout (`backend/app/api/endpoints/`, `services/`, `utils/`, `dependencies/`, `models/`, `schemas/`).
- `.planning/codebase/ARCHITECTURE.md` — Request flow: React frontend (port 4000) / Chrome extension → FastAPI (port 8000, prefix `/api`) → PostgreSQL.
- `.planning/codebase/CONVENTIONS.md` — `EndpointRegistry.register_endpoint(...)` pattern, `BaseEndpointRouter` / `BaseCRUDService` abstractions, pytest-xdist `-n auto`, Alembic autogenerate-only, `ENABLE_RATE_LIMITING=false` in tests.
- `.planning/codebase/CONCERNS.md` — Oversized files (admin.py 2,055 / auth.py 1,195 lines are explicit debt items this phase resolves).
- `.planning/codebase/TESTING.md` — Existing test fixture kit, `pytest-recording` (Phase 1 dep), per-worker DB isolation.
- `.planning/codebase/STACK.md` / `INTEGRATIONS.md` — Terraform-managed AWS + EventBridge scheduler + App Runner + ECS Fargate (crawler workers). Terraform is the source of truth for EventBridge schedule paths.

### Files directly touched by Phase 5

**Backend — new files**

- `backend/app/api/endpoints/admin/__init__.py` — may be empty or re-export conveniences; no router mounting (that happens in main.py per D-08).
- `backend/app/api/endpoints/admin/stats.py` — 2 routes.
- `backend/app/api/endpoints/admin/jobs.py` — 4 routes.
- `backend/app/api/endpoints/admin/crawlers.py` — 4 routes + inline ECS task launchers + `_verify_cron_key`.
- `backend/app/api/endpoints/admin/db_ops.py` — 7 routes + `_get_alembic_directory` + `_init_result`.
- `backend/app/api/endpoints/admin/parts.py` — 6 routes + `_first_listing_for` + `_link_group_member`.
- `backend/app/api/endpoints/admin/_helpers.py` — `_stamp_heartbeat`, `_heartbeat_loop`, `_get_superadmin_emails`, `_notify_job_completion`.
- `backend/app/api/endpoints/auth/__init__.py` — same pattern.
- `backend/app/api/endpoints/auth/core.py` — 7 routes.
- `backend/app/api/endpoints/auth/two_factor.py` — 3 routes.
- `backend/app/api/endpoints/auth/webauthn.py` — 7 routes + challenge-token helpers.
- `backend/app/api/endpoints/auth/oauth.py` — 7 routes + Google-specific helpers.
- `backend/app/api/endpoints/auth/_helpers.py` — `_issue_login_response`, `_maybe_2fa_challenge`.
- `backend/scripts/generate_ext_api_contract.py` — NEW. Generates `chrome-extension/API_CONTRACT.md` from `app.openapi()`.
- `backend/tests/test_admin_auth_coverage.py` — parametrized 401/403 per route.
- `backend/tests/test_auth_auth_coverage.py` — parametrized 401 per protected route.
- `backend/tests/test_pyjwt_migration.py` — jose/PyJWT parity test.
- `backend/tests/test_jwt_algorithm_regression.py` — grep for bare `jwt.decode` calls.
- `backend/tests/test_ext_api_contract_up_to_date.py` — generator-output equality check.
- `chrome-extension/API_CONTRACT.md` — NEW (generated).

**Backend — deleted**

- `backend/app/api/endpoints/admin.py` (deleted in PR 1 per REQ-ADMIN-01).
- `backend/app/api/endpoints/auth.py` (deleted in PR 4 per REQ-AUTH-01).

**Backend — modified**

- `backend/app/api/dependencies/auth.py` — swap `from jose import JWTError, jwt` → `import jwt` + `from jwt.exceptions import InvalidTokenError`; update `ALGORITHM` to read `settings.JWT_ALGORITHM`; update 3 `except JWTError` → `except InvalidTokenError`.
- `backend/app/core/config.py` — add `JWT_ALGORITHM: str = "HS256"` field.
- `backend/app/main.py` — replace 2 `register_endpoint(admin.router/auth.router, ...)` calls with 9 per-sub-module registrations.
- `backend/requirements.txt` — remove `python-jose[cryptography]==3.5.0`; add `PyJWT==2.12.1`.
- `backend/app/api/utils/admin_endpoint_patterns.py` — audit any imports from `app.api.endpoints.admin`; update if present.
- `backend/tests/**/*.py` — update any `from app.api.endpoints.admin import ...` / `from app.api.endpoints.auth import ...` to new sub-module paths.
- `backend/tests/fixtures/openapi_snapshot.json` — regenerate in PR 1 (admin restructure) and PR 4 (auth restructure).

**Frontend — modified**

- `frontend/src/api/*.ts` — update admin URL paths (PR 1) + Google OAuth paths (PR 4).

**Terraform — modified**

- `terraform/*.tf` (EventBridge schedule resources) — update `/admin/crawled-pages/rescrape-archives` path reference to `/admin/crawlers/rescrape-archives`. Landed in PR 1.

**Docs**

- `.planning/phases/05-structural-router-splits/05-CONTEXT.md` (this file).
- `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` (post-deploy UAT checklist — created during execute phase per Phase 4 UAT convention).

### No external specs required

Requirements are fully captured in REQUIREMENTS.md + ROADMAP.md + prior CONTEXT.md decisions above. No ADRs or external design docs referenced for Phase 5.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`backend/app/api/dependencies/auth.py`** — Houses `get_current_user`, `get_current_admin_user`, `get_optional_current_user`, `get_current_superuser`, `oauth2_scheme`, `verify_password`, `create_access_token`, `ALGORITHM`. **Stays outside the endpoints/auth/ package** — shared across the app. Only touched for PyJWT swap + ALGORITHM hoist.
- **`backend/app/main.py:226-307`** — Existing `EndpointRegistry.register_endpoint(...)` call sites. Phase 5 replaces `auth.router` + `admin.router` registrations (2 calls) with 9 sub-module registrations (4 auth + 5 admin).
- **`backend/app/api/utils/EndpointRegistry`** — Unchanged pattern. Each new sub-module router registers the same way.
- **`backend/tests/conftest.py`** — `test_user`, `test_admin_user`, `test_superuser_user`, `create_and_login_user`, `client` fixtures. The new `test_admin_auth_coverage.py` test file reuses these.
- **`backend/tests/test_openapi_snapshot.py`** — Phase 1 SAFE-05 artifact. The snapshot-regeneration convention (Phase 1 D-26) handles the restructure.
- **`backend/tests/test_session_query_regression.py`** / `test_pydantic_v1_regression.py` / `test_logger_migration_regression.py` — Phase 3+4 guard tests. Phase 5's new files pass them automatically if D-26 module-level logger + D-45 `db.scalars(select(...))` patterns are followed.
- **`chrome-extension/manifest.json`** — `externally_connectable.matches` locks the web app → extension messaging domains. No change needed for Phase 5.
- **`chrome-extension/src/background.ts`** — Bearer-token-based API client. Reads `authToken` from `chrome.storage.local`; attaches `Authorization: Bearer` to every request. Unchanged by Phase 5.

### Established Patterns

- **One sub-router per file with `router = APIRouter()`** — Already the pattern across `backend/app/api/endpoints/*.py`. Phase 5's sub-modules follow the same shape.
- **Per-route `current_user: DBUser = Depends(get_current_admin_user)` / `Depends(get_current_user)`** — Already the pattern. AUTH-03 / ADMIN-02 lock "explicit" which the current per-route declaration satisfies; just carries into the new sub-module files.
- **Module-level logger** (Phase 3 D-33—D-37) — Every new file gets `logger = logging.getLogger(__name__)` at module top.
- **`EndpointRegistry.register_endpoint(router, prefix=..., tags=[...], description=...)`** — Unchanged pattern for registering routers to the FastAPI app. Just called 9 times instead of 2.
- **Alembic autogenerate-only** (CLAUDE.md) — Not triggered by Phase 5 (no schema changes). If a planner surfaces one, reconsider phase boundary.
- **OpenAPI snapshot as review artifact** (Phase 1 D-26) — Intentional drift regenerates + commits in the same PR as the change.
- **Regression-grep tests for CI gates** (Phase 3 QUAL-02/QUAL-07, Phase 4 D-09) — Pattern for `test_jwt_algorithm_regression.py` (D-04) follows this shape.
- **`# SAFE:` annotation** (Phase 1 SAFE-04) — Not triggered (no schema migrations in Phase 5).

### Integration Points

- **Phase 1 OpenAPI snapshot test** — Legitimate drift regenerates (two PRs in this phase: admin restructure + auth restructure).
- **Phase 1 auth characterization tests (7 happy-path flows)** — Must stay green through every Phase 5 PR. End-to-end guardrail for the refactor.
- **Phase 3 logger regression test** — Catches any `Depends(get_logger)` reintroduction in new sub-module files.
- **Phase 4 session.query regression test** — Catches any `db.query(...)` reintroduction in new sub-module files.
- **Phase 4 query_counter fixture** — Available but not required by Phase 5. If a plan's scope surfaces an ORM concern, the fixture's there.
- **Terraform EventBridge schedule paths** — Admin restructure PR updates Terraform in the same commit. Deploy sequencing: backend image rolls out before Terraform apply (or both simultaneously if the deploy pipeline can atomic-swap).
- **`backend/app/api/dependencies/auth.py::get_current_user`** — Downstream of the PyJWT swap. The 3 `except JWTError` sites in this file become `except InvalidTokenError` in PR 2.
- **`settings.JWT_ALGORITHM`** — NEW config field introduced in PR 2. Default `"HS256"`. Read by both `backend/app/api/dependencies/auth.py` and `backend/app/api/endpoints/auth/core.py` (post-split).

</code_context>

<specifics>
## Specific Ideas

- **"Admin is the dry run, auth is the main event"** — PROJECT.md + ROADMAP Internal Note. Admin split lands first because Chrome extension is not in admin's critical path. Pattern established in PR 1 flows into PR 4 with less surprise. Auth split is the highest-stakes refactor of the milestone.
- **"PyJWT in a narrow, focused PR"** — D-01. Library swap gets its own PR between the two splits. Reviewer sees the library diff cleanly, not tangled with structural refactor. HS256 signatures are byte-compatible — the parity test (D-05) proves it.
- **"Explicit over magic"** — D-03 (hoist ALGORITHM to config + lint rule), D-27 (per-route 401/403 tests with drift guard). Each explicit surface catches a class of regression that convention alone cannot.
- **"Tree-shaped URLs for explicit sub-module authority"** — D-09, D-10. The aggressive restructure means each sub-module's URL surface is visible at a glance. Costs: frontend + Terraform update. Benefits: API hygiene, easier navigation, sub-modules can't bleed into each other's URL spaces.
- **"Characterization is the guardrail"** — Phase 1 SAFE-06 + OpenAPI snapshot. Both MUST stay green through every PR. If they go red, the refactor has broken a contract; fix immediately or revert.
- **"Generator + drift test = live doc"** — D-34—D-36. `chrome-extension/API_CONTRACT.md` is auto-generated and drift-gated. Developers update the allow-list, regenerate, commit. CI catches stale docs.
- **"Manual UAT is proportional"** — D-38. Chrome extension runs in Chrome runtime — a full Playwright + loaded-extension E2E is expensive for a surface that doesn't touch `/auth/*` or `/admin/*`. 5-minute staging checklist is the right tool.
- **"Old file deleted in the same PR"** — REQ-AUTH-01 + REQ-ADMIN-01 literal. Hard cut, no shim, no backwards-compat. Phase 4's D-44 reinforces the principle: new sub-modules use modern APIs from day one.

</specifics>

<deferred>
## Deferred Ideas

### Deferred within or beyond this milestone

- **Extract ECS task launchers to `backend/app/services/ecs_task_service.py`** — D-24 keeps them inline. A future service-layer extraction phase could take them up; not a Phase 5 deliverable.
- **Playwright E2E with loaded Chrome extension** — D-39. Manual UAT covers Phase 5. If a regression surfaces in production that manual UAT didn't catch, consider adding automated E2E in a future testing-infra phase.
- **Backend integration test simulating extension requests (Authorization: Bearer, Origin: chrome-extension://...)** — D-40. Deferred; per-route 401/403 tests capture the auth dependency correctness. If a CORS-or-origin regression specifically affects the extension, add targeted test then.
- **Remove `get_logger` export entirely** — Phase 3 D-36 deferred this to "late Phase 5 / early Phase 6". After PR 4 completes, run `grep -rn "from app.core.logging import get_logger" backend/app/` — if zero callers, remove the export + its test file. Otherwise defer further.
- **Remove `python-jose[cryptography]` dependency + PyJWT parity test (D-05)** — Keep through Phase 5. Consider removing the parity test in Phase 6+ if dependency management cleanups happen there.
- **Retroactive historical admin/auth endpoint test renames to the new sub-module paths** — Phase 5 updates imports in tests; renaming test files to match sub-module structure (e.g., `test_admin_endpoints.py` → `test_admin_stats.py` + `test_admin_jobs.py` + ...) is a cleanup task, out of Phase 5 scope.
- **ALGORITHM rotation / RS256 migration** — D-46 preserves `"HS256"`. Moving to asymmetric signing (e.g., for token introspection by a separate auth service) is a future security-hardening arc per PROJECT.md's "attainable 90%" posture — not this milestone.
- **Admin UI URL routing update in the Frontend Structure phase (Phase 6 or later)** — Any opportunistic UX polish on admin pages during Phase 6's frontend refactor should align with the new URL tree from D-09.
- **ADMIN-04 "service-level coupling reduced"** — The ROADMAP lists ADMIN-04 ("admin sub-routers inject specific services via `Depends()`, not a single god-service"). Scout did not surface a current "god-service" pattern in admin.py; the functions mostly use direct DB calls + a few imports from `backend/app/services/*`. Plan author should confirm during research whether ADMIN-04 has a concrete target or is preventive language. If concrete → plan addresses it; if preventive → document in SUMMARY.md that current state already satisfies.

### Noted but not a Phase 5 deliverable

- **Split `auth/webauthn.py` further into `webauthn/core.py` + `webauthn/credentials.py`** — Over-decomposition. Current proposed scope has 7 webauthn routes in one file; at ~400 lines it's reasonable.
- **Parallel split of `backend/app/services/*.py`** — Service-layer files aren't oversized by the current CONCERNS.md inventory. Out of scope.
- **Rewrite Chrome extension to use a typed API client generated from OpenAPI** — Valuable but separate scope (frontend milestone).

</deferred>

---

*Phase: 05-structural-router-splits*
*Context gathered: 2026-04-22*
