# Phase 4: DB & Parts Hardening - Context

**Gathered:** 2026-04-22 (auto mode — recommended defaults selected for all gray areas)
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the database layer end-to-end before any Phase 5 structural router split can touch it. Phase 4 delivers five locked outcomes: (1) the N+1 query in `GET /build-logs/build-list/{id}` is fixed with `selectinload(Post.author)` and a CI-gated query-count regression test, (2) part-link / unlink / re-elect operations are pessimistic-lock-safe under the canonical-parts refactor with a concrete 10-thread concurrency test that proves no orphaned or circular references, (3) every FK join key across the 25 models has an `Index()` declaration (closing a known Performance Insights gap), (4) the `session.query()` legacy API is eliminated across 304 call sites in ~20 files and replaced with `select() + session.scalars()`, and (5) build-log rows are created eagerly alongside the parent build list (deleting the inconsistent lazy mid-request auto-create branches in `build_logs.py`).

Additional hardening that fits inside the DB-layer boundary: prod pool reconciliation (DATA-07), `lazy="raise"` applied surgically to N+1-prone relationships (DATA-10), and an Alembic downgrade-testing convention documented in CONVENTIONS.md (DATA-09). Parts-side hardening rounds it out: canonical-flow integration coverage (PARTS-03) and a maintainability pass on `car_inference.AMBIGUOUS_STANDALONE_CODES` (PARTS-02 — no ML this milestone).

No router splits, no auth changes, no new endpoints. External API contracts are unchanged. Phase 4 is the last gate before Phase 5 begins the admin.py / auth.py structural splits.

</domain>

<decisions>
## Implementation Decisions

### Gray Area 1 — Concurrency test infrastructure (DATA-03, DATA-04, PARTS-01)

- **D-01:** The concurrency test (10-thread `ThreadPoolExecutor` simulating simultaneous link/unlink against `link_new_part`, `reelect_canonical`, `unlink_part`) runs against a **real Postgres database** via a Docker side-car, NOT the default SQLite in-memory fixture. Rationale: SQLite does not support pessimistic row locking via `with_for_update()`; testing the fix on SQLite proves nothing about the production behavior. STATE.md already flags "Postgres Docker test environment — Phase 4 migration testing needs a docker-compose step" as a Phase-4 decision point; this plan closes it.
- **D-02:** Introduce a new `@pytest.mark.postgres` marker. Tests carrying this marker skip when `POSTGRES_TEST_URL` is unset (local `pytest -n auto` keeps the existing SQLite contract from `backend/tests/conftest.py:31-58`) and require a reachable Postgres when set. CI sets the env var via a `services:` block on the `backend-ci.yml` job step that runs the concurrency test. Everything else in the suite keeps using SQLite in-memory; this is an opt-in marker, not a global switch.
- **D-03:** `docker-compose.test.yml` at repo root adds a `postgres-test` service (Postgres 16, matching RDS). The backend-ci.yml step uses GitHub Actions `services.postgres` rather than docker-compose directly (faster, less setup — single image, tmpfs data dir, 5s startup). Local developers can opt in via `POSTGRES_TEST_URL=postgresql://...@localhost:5432/cmp_test pytest -n auto -m postgres`.
- **D-04:** Scope of Postgres-backed tests in this phase: (a) the DATA-04 10-thread link-contention test, (b) the DATA-09 downgrade round-trip test if it ever lands as CI automation (decided deferred below — see Gray Area 7), (c) any future test that relies on Postgres-specific SQL. Every other backend test keeps running on SQLite. No blanket migration to Postgres fixtures.
- **D-05:** The concurrency test fixture creates N distinct `Part` rows with overlapping dedup keys (gtin / url / manufacturer+part_number), then kicks off 10 threads that each call `link_new_part` concurrently. After the pool drains, assertions: (a) exactly one canonical exists (canonical_part_id IS NULL), (b) all other parts point at it, (c) no cycles (chase canonical_part_id > 0 hops), (d) `_point_siblings_at` merges produced no orphans (every sibling's canonical_part_id resolves to a live Part row with canonical_part_id IS NULL). Also run `unlink_part` under the same load and assert link-group invariants hold.

### Gray Area 2 — `session.query()` → `select()` migration scope (DATA-06)

- **D-06:** One atomic sweep PR covering **all 304 `db.query(...)` / `session.query(...)` call sites** across ~20 files. Matches the Phase 3 QUAL-07 logger-migration pattern — mechanical, greppable, single-PR. Incremental per-file PRs were considered and rejected: the grep-based regression test that locks this in cannot go CI-green until the sweep is complete, so partial PRs would leave CI broken or the guard disabled.
- **D-07:** Migration pattern, apply identically everywhere (mechanical):
  ```python
  # Before
  user = db.query(DBUser).filter(DBUser.id == user_id).first()
  parts = db.query(DBPart).filter(DBPart.is_verified).all()
  count = db.query(DBPost).filter(DBPost.build_log_id == bl_id).count()

  # After
  user = db.scalars(select(DBUser).where(DBUser.id == user_id)).first()
  parts = db.scalars(select(DBPart).where(DBPart.is_verified)).all()
  count = db.scalar(select(func.count()).select_from(DBPost).where(DBPost.build_log_id == bl_id))
  ```
- **D-08:** File priority order (largest-fan-in first, so test breakage surfaces at the base layers):
  1. `backend/app/api/utils/common_patterns.py` (12 sites; feeds most endpoints)
  2. `backend/app/api/utils/base_endpoint_router.py` + `base_vote_router.py` + `base_report_router.py` + `admin_endpoint_patterns.py`
  3. `backend/app/api/services/*.py` (11 files, ~60 sites)
  4. `backend/app/api/endpoints/*.py` (~15 files, ~170 sites)
  5. `backend/app/services/job_service.py` + `backend/app/crawlers/*.py` (~30 sites)
- **D-09:** Regression guard: a pytest in `backend/tests/test_session_query_regression.py` that greps `backend/app/**/*.py` and asserts zero matches for `\.query\(` (with a tight pattern that excludes legitimate non-SQLAlchemy `.query()` usages — the `requests` library and `urllib.parse` are the only false-positive candidates, neither currently used in repo). Matches the pattern established by `backend/tests/test_pydantic_v1_regression.py` (Phase 3, QUAL-02) and `backend/tests/test_logger_migration_regression.py` (Phase 3, QUAL-07).
- **D-10:** OpenAPI snapshot (Phase 1 SAFE-05) must stay green. The sweep does not change endpoint signatures or response shapes, so the snapshot should match; verify by regenerating once and committing the diff if it shifts (unlikely but documented).
- **D-11:** Transaction boundaries, session lifecycle, and commit/flush semantics are PRESERVED. The sweep is purely a query-API modernization — `db.scalars(...)` / `db.scalar(...)` execute inside the existing `get_db()` generator-scoped transaction, identical to `db.query(...)` today. No Unit-of-Work changes.

### Gray Area 3 — FK index audit methodology (DATA-05)

- **D-12:** Add `index=True` (for single-column FKs) or `Index(...)` in `__table_args__` (for composite indexes) directly in the ORM model files under `backend/app/api/models/`. Run `alembic revision --autogenerate -m "add missing FK indexes"` and let Alembic emit `op.create_index()` calls for every new index. Per CLAUDE.md, migrations are autogenerate-only.
- **D-13:** Phase 1 SAFE-09 landed `MetaData(naming_convention=...)` in `backend/app/db/base_class.py` — autogenerated indexes automatically get `ix_<table>_<column>` names. No name collision with pre-existing indexes.
- **D-14:** Audit scope: every `mapped_column(..., ForeignKey(...))` across 25 model files. Exception rule: a single-column FK that is the **leading column of a committed composite index** (e.g., `vote.user_id` is the leading column of `ix_votes_user_entity_type`) is treated as already-indexed via the Postgres left-prefix rule — do NOT add a duplicate index. Document the exception in the audit results (one-line note per skipped FK).
- **D-15:** Specific FKs confirmed missing indexes by the scout (non-exhaustive — planner produces the full list):
  - `build_lists.user_id` (ForeignKey with no `index=True`, no composite cover)
  - `build_lists.car_id` (same)
  - `parts.user_id`, `parts.category_id` (both have ForeignKey with no `index=True` in model)
  - `build_list_parts.build_list_id`, `build_list_parts.part_id`, `build_list_parts.added_by` (FKs without `index=True`)
  - `reports.user_id`, `reports.reviewed_by` (`ix_reports_user_entity_type` covers user_id via left-prefix; reviewed_by does not)
  - Others surface during planner's systematic pass
- **D-16:** Separate the autogenerated add-index migration from any other schema work. This one migration contains ONLY `op.create_index(...)` calls — zero drops, zero alters, zero data mutations. Keeps the review surface narrow and rollback trivial (drop-index is always safe). Annotate the file with a `# SAFE:` comment is NOT required since there are no destructive ops — but the PR description must call out the index-only scope for reviewer focus.
- **D-17:** Index strategy for polymorphic tables (votes, reports): prefer composite indexes `(entity_type, entity_id)` over separate single-column indexes. `votes` and `reports` already have those per their current `__table_args__`. Confirm during audit; do not duplicate.

### Gray Area 4 — Production pool configuration (DATA-07)

- **D-18:** DEVIATION FROM REQUIREMENTS.md DATA-07 LITERAL. REQ-07 says `DB_POOL_SIZE=50, pool_pre_ping=True, pool_recycle=1800`. Current `backend/app/db/session.py` has `DB_POOL_SIZE=25, DB_MAX_OVERFLOW=75, API_CONNECTION_RESERVE=20, pool_pre_ping=True, pool_recycle=3600`. The REQ-07 literal `pool_size=50` is already exceeded by current total capacity (`25 + 75 = 100`), which is intentionally sized for the crawler parallelism formula (Phase 3 D-14). Keep the existing `pool_size=25 + max_overflow=75 = 100` envelope; only change `pool_recycle` from 3600 to 1800.
- **D-19:** `pool_pre_ping=True` already in place (`session.py:33`). No-op for this requirement.
- **D-20:** `pool_recycle=3600` → `pool_recycle=1800`. Rationale for the REQ-locked 30min value: RDS idle-connection garbage-collection timing + App Runner cold-start behavior. Existing 3600 is inherited from an earlier era; 1800 tightens staleness.
- **D-21:** Document the deviation in the plan's SUMMARY.md with a link to Phase 3 D-14 (crawler worker formula) + the Phase 4 D-18 calculation. The verifier reads this to confirm the literal-value miss is intentional, not a regression.
- **D-22:** `API_CONNECTION_RESERVE=20` stays. Phase 3 D-14 depends on it for the ThreadPoolExecutor sizing; changing it would ripple into Phase 3's crawler runner config.

### Gray Area 5 — Build-log eager creation (DATA-08)

- **D-23:** Eager build-log creation already exists in `backend/app/api/services/build_list_service.py:82-88` (new build lists get a `BuildLog` row via `db.flush()` inside the same transaction). DATA-08's target is the DELETION of the lazy mid-request auto-create branches in `backend/app/api/endpoints/build_logs.py:86-98` and `:191-201` — those fallback branches are now dead weight since new build lists always have a log, and legacy build lists need a one-shot backfill.
- **D-24:** Backfill strategy: an Alembic **data migration** (autogenerate scaffolds the revision, the body is a hand-written `op.execute(sa.text(...))` INSERT ... SELECT ... WHERE NOT EXISTS). Must be idempotent — re-running the upgrade after a partial apply is safe.
  ```sql
  INSERT INTO build_logs (id, build_list_id, title, created_at, updated_at)
  SELECT gen_random_uuid(), bl.id, 'Build Log: ' || bl.name, NOW(), NOW()
  FROM build_lists bl
  WHERE NOT EXISTS (SELECT 1 FROM build_logs bl2 WHERE bl2.build_list_id = bl.id)
  ```
  (Exact UUID strategy matches existing `uuid7` default; either `gen_random_uuid()` or equivalent Python-side generator works — planner picks based on what Postgres version / extensions are available in prod RDS.)
- **D-25:** The data migration is **separate** from the code change that deletes the lazy branches. Order: data migration lands first (backfill → every existing build list has a log), then the code-change PR deletes the lazy branches + updates the logic to `get_entity_or_404(db, DBBuildLog, ...)` for read paths that previously auto-created. This ordering is safe: after the backfill, every build list the read path can see has a log, so the fallback branch is unreachable; deleting it is purely structural.
- **D-26:** Downgrade path: the data migration's `downgrade()` does NOT delete the backfilled build_log rows (would lose user-created posts). It's a no-op with a `# SAFE: forward-only data backfill; no reversal needed` annotation per Phase 1 SAFE-04 convention. The code-change PR's Git revert is the functional rollback; the data doesn't need to unwind.
- **D-27:** Verification: add a startup assertion (or a pytest that exercises it against a seeded DB) confirming `SELECT COUNT(*) FROM build_lists WHERE id NOT IN (SELECT build_list_id FROM build_logs) = 0`. Runs once on first dev re-deploy to catch any orphaned build_list rows introduced between migration merge and deploy.

### Gray Area 6 — `lazy="raise"` scope (DATA-10)

- **D-28:** Apply `lazy="raise"` SELECTIVELY to relationships known to N+1 — NOT globally. Scope:
  - `BuildLogPost.author` (or the equivalent relationship introduced by D-32 below for DATA-01 — this is THE relationship that triggered the N+1 fix)
  - `BuildList.build_list_parts` (large lists can N+1 on read)
  - `BuildList.build_list_phases` (same)
  - `Part.listings` (already `lazy="selectin"` per `part.py:65`; leave as-is)
- **D-29:** Global `lazy="raise"` was considered and rejected. Rationale: applying globally would require auditing every single `relationship()` use in endpoint + service code and adding `.options(selectinload(...))` everywhere the ORM is used lazily on purpose (e.g., admin detail pages, canonical-parts flow). That is a Phase-5-plus sweep; scope-contained applies to relationships actually known to cause production perf pain, avoiding a test-fixture earthquake.
- **D-30:** Every `lazy="raise"` addition pairs with a green `.options(selectinload(...))` (or `joinedload(...)`) in every caller path. The Phase 4 plan's DATA-01 work already adds `selectinload(Post.author)` to the build-log read path — the same PR flips the relationship to `lazy="raise"`. Each subsequent `lazy="raise"` addition lives in its own plan step with its own verified callers.

### Gray Area 7 — Migration downgrade-testing convention (DATA-09)

- **D-31:** `.planning/codebase/CONVENTIONS.md` gets a new "Alembic downgrade testing" subsection under the existing "Migrations" section. Content: every migration PR must include documented evidence that `alembic upgrade head → alembic downgrade -1 → alembic upgrade head` round-trips cleanly against a local Docker Postgres (`docker-compose up -d postgres-test` / equivalent). Required for merge; enforced at review, not CI (CI-automated downgrade testing deferred per STATE.md Phase-4 decision-point guidance — see Deferred Ideas below).

### Gray Area 8 — Query-count regression test (DATA-01, DATA-02)

- **D-32:** Fix the N+1 in `backend/app/api/endpoints/build_logs.py:119` by loading authors via `selectinload`. Replace the per-post `db.query(DBUser).filter(DBUser.id == post.user_id).first()` with a single `selectinload(BuildLogPost.author)` on the posts query. This requires adding a `user: Mapped["User"] = relationship(...)` relationship to `BuildLogPost` if one doesn't already exist (scout shows the model has `user_id: ForeignKey("users.id")` but the relationship declaration is present — planner verifies exact shape).
- **D-33:** Query-count regression test fixture. New `backend/tests/conftest.py` (or a sibling test module) fixture using SQLAlchemy's `event.listen(engine, "before_execute", ...)` to increment a per-test counter. Exposed via a pytest fixture `query_counter` that returns a context manager:
  ```python
  def test_build_log_n_plus_one_fixed(client, create_and_login_user, query_counter):
      # seed: 1 build list + 10 posts by different authors
      ...
      with query_counter() as counter:
          response = client.get(f"/build-logs/build-list/{build_list_id}?limit=10")
      assert response.status_code == 200
      assert counter.count == 2, f"Expected 2 queries (posts + authors batch), got {counter.count}"
  ```
- **D-34:** Test is SQLite-backed (inherits default conftest fixtures). SQLite's query profile matches Postgres closely enough for query-count semantics (both emit the same # of SELECT statements for a given ORM traversal); the value of this test is catching ORM-usage regressions, not driver-level differences.
- **D-35:** Counter semantics: count DISTINCT emitted `SELECT` statements. `selectinload` emits one additional `SELECT ... WHERE id IN (:id_1, :id_2, ...)` regardless of result-set size; that's the second query the test expects. Pagination metadata query (the `count(...)`) is the third if the current code keeps it as a separate statement — revisit assertion to match what the fixed code actually emits.

### Gray Area 9 — PARTS-02 car_inference maintainability

- **D-36:** `backend/app/api/services/part_inference/car_inference.py`'s `AMBIGUOUS_STANDALONE_CODES` set gets a multi-line docstring enumerating (a) what the set is for (codes that cannot disambiguate vehicle generation without a make+model adjacent in context), (b) the criterion for adding / removing codes, (c) known counterexamples.
- **D-37:** Regression test pinning current behavior: a new `backend/tests/test_car_inference_ambiguity.py` with ~20 fixed input vectors — each an input string + expected inference behavior. The test documents "this is how ambiguity resolution behaves today," not "this is correct." Downstream PARTS-V2-01 (ML-based disambiguation, deferred to v2) will rewrite this test.
- **D-38:** NO new ML this milestone. PARTS-V2-01 is explicitly deferred in REQUIREMENTS.md.

### Gray Area 10 — PARTS-03 canonical-flow integration coverage

- **D-39:** Integration test suite for canonical parts in `backend/tests/services/test_part_linker_integration.py` (or extend existing). Coverage: (a) create isolated canonical, (b) link new part into existing canonical group, (c) new part with richer metadata re-elects itself as canonical, (d) merge case (multiple candidates — new part has shared gtin with canonical A and shared url with canonical B → canonicals merge under the chosen one), (e) unlink detaches and promotes to standalone canonical.
- **D-40:** SQLite-only. Concurrency behavior under row locks is covered by D-01 through D-05 (Postgres-backed). Canonical-logic correctness is data/algorithm, not lock-dependent.
- **D-41:** Use the existing `db_session` + factory fixtures. No new fixture plumbing.

### Execution sequencing inside Phase 4

- **D-42:** Plan order (dependency-honest):
  1. **Wave 1 (parallel):** DATA-05 (FK index audit + single add-index migration) + DATA-07 (pool_recycle change) — both trivial, no coupling
  2. **Wave 2:** DATA-08 (build_log backfill migration + code-change PR) — depends on Wave 1's migration ordering (no coupling but serialize migrations)
  3. **Wave 3 (parallel):** DATA-01 + DATA-02 (N+1 fix + query-count regression test) + DATA-06 (session.query sweep)
  4. **Wave 4:** DATA-03 + DATA-04 + PARTS-01 (with_for_update + Postgres concurrency test) — depends on Wave 2 (build_log backfill) for a clean DB surface
  5. **Wave 5 (parallel):** DATA-10 (lazy="raise" on 2-3 relationships) + DATA-09 (CONVENTIONS.md docs) + PARTS-02 (car_inference docstring + test) + PARTS-03 (canonical integration tests)
- **D-43:** Rationale for the ordering: indexes + pool are the lowest-risk, fastest-to-verify items; get them in first to de-risk prod. Eager build_log cleanup unblocks all subsequent DB-layer work by removing the mid-request auto-create branch that complicated read-path reasoning. N+1 fix + session.query sweep can parallelize because they touch different call sites (build_logs endpoint vs. ~20 other files). Row-lock concurrency test comes after the session.query sweep so the tests themselves are written in the new API. lazy="raise" and docs come last as cleanup.

### Phase 5 handoff

- **D-44:** Phase 5's admin.py / auth.py splits inherit the session.query → select() migration. Every new file Phase 5 creates uses the modern API from day one — no regression, no partial-state work.
- **D-45:** Phase 5's admin and auth integration tests can freely use the `query_counter` fixture (D-33) to catch accidental N+1s introduced during the split.
- **D-46:** The Postgres test side-car (D-03) stays available for Phase 5 if any admin / auth test needs Postgres-specific locking behavior.

### Claude's Discretion

- Exact naming of the `query_counter` fixture and the per-test counter object's public API
- Whether to add a dedicated test file per DATA-requirement or pack related tests into existing files
- Exact SQL dialect for the build-log backfill INSERT (hand-written `op.execute` in the Alembic migration) — planner verifies Postgres 16 syntax
- The selectinload implementation exact shape (e.g., `load_only(User.id, User.username, User.image_urls)` to avoid fetching the full User row)
- Whether the `query_counter` counts all SQL statements or just `SELECT` statements — planner picks based on what produces the tightest assertions
- Whether the FK-index-only migration commits alongside an `autogenerate_diff.md` note or just lives as the standalone revision

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone-level framing

- `.planning/PROJECT.md` — Vision, Active requirements (DB/migrations/perf pass, Parts & canonical dedup consolidation), Key Decisions (canonical model consolidated-not-redesigned; AWS RDS Postgres 16 prod target)
- `.planning/REQUIREMENTS.md` §"Database, Migrations & Performance" — DATA-01 through DATA-10 with locked parameters (`selectinload`, `with_for_update`, `pool_size`, `session.scalars`, `lazy="raise"`, etc.)
- `.planning/REQUIREMENTS.md` §"Parts & Canonical Dedup Consolidation" — PARTS-01 (covered by DATA-03/04), PARTS-02 (car_inference docs + test), PARTS-03 (canonical-flow integration coverage)
- `.planning/REQUIREMENTS.md` §"v2 Requirements / Parts Data Model Deepening" — PARTS-V2-01 (ML-based ambiguity resolution) and PARTS-V2-03 (optimistic concurrency) are explicitly deferred
- `.planning/ROADMAP.md` §"Phase 4: DB & Parts Hardening" — Goal, Depends on (Phase 1), Success Criteria (5 TRUE conditions)
- `.planning/STATE.md` §"Blockers/Concerns" — "Postgres Docker test environment" Phase-4 decision point + "`lazy=\"raise\"` scope" Phase-4 decision point (D-01, D-02, D-28 close these)

### Phase 1 decisions that carry forward

- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-11 — `MetaData(naming_convention=...)` in `backend/app/db/base_class.py`. All autogenerated indexes in Phase 4 inherit this convention (ix_<table>_<column>).
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-07 through D-10 — Migration DROP-guard CI step. Phase 4's data-migration downgrade() for DATA-08 backfill uses the `# SAFE:` annotation convention.
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-01 through D-06 — Coverage floors (`--cov-fail-under=51` backend, `lines: 60` frontend). Phase 4's new tests bring their own coverage so the gate doesn't regress.
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §"Deferred Ideas" — "Postgres-backed migration testing in CI (DATA-09)" explicitly punted to Phase 4; this CONTEXT.md punts the CI-automation further (see Deferred Ideas) and lands the documentation-only CONVENTIONS.md update.
- `.planning/phases/01-safety-nets-ci-hardening/01-VERIFICATION.md` — Characterization tests (auth + crawler) must stay green under all Phase 4 changes.

### Phase 2 decisions that interact with Phase 4

- `.planning/phases/02-observability/02-CONTEXT.md` §D-09 — Sentry scope processor attaches `user_id` + `request_id`. Any new ORM errors in Phase 4 (e.g., FK-constraint violations during backfill) surface in Sentry with context; verify during UAT.
- `.planning/phases/02-observability/02-CONTEXT.md` §D-17 — CloudWatch EMF emission is logs-only, no DB coupling. Phase 4 does not touch.

### Phase 3 decisions that interact with Phase 4

- `.planning/phases/03-non-breaking-internal-improvements/03-CONTEXT.md` §D-14 — Crawler ThreadPoolExecutor sizing formula `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE = 80`. Phase 4 D-18 keeps `DB_POOL_SIZE=25 + DB_MAX_OVERFLOW=75 - API_CONNECTION_RESERVE=20` intact so the crawler formula does not break. CHANGING pool size requires Phase 3 D-14 re-evaluation.
- `.planning/phases/03-non-breaking-internal-improvements/03-CONTEXT.md` §D-15 — Per-worker `SessionLocal()`. Phase 4's row-lock tests (D-01) run against the SAME `SessionLocal` path; the Postgres test DB must provide an engine with non-trivial transaction isolation (default READ COMMITTED is correct).
- `.planning/phases/03-non-breaking-internal-improvements/03-CONTEXT.md` §D-33 through D-37 — Module-level `logger = logging.getLogger(__name__)` pattern. Phase 4's new modules + modified files keep this convention; no `Depends(get_logger)` reintroduction.

### Codebase context

- `.planning/codebase/STRUCTURE.md` — Backend package layout (`backend/app/api/models/`, `services/`, `endpoints/`, `utils/`)
- `.planning/codebase/ARCHITECTURE.md` — App Runner + RDS Postgres 16 topology; connection pool sizing rationale
- `.planning/codebase/CONVENTIONS.md` — Alembic autogenerate-only (CLAUDE.md rule), pytest-xdist `-n auto`, ENABLE_RATE_LIMITING=false in tests
- `.planning/codebase/CONCERNS.md` — N+1 in build_logs.py, part-linking race condition, FK index gaps, session.query legacy calls (exactly the debt Phase 4 pays down)
- `.planning/codebase/TESTING.md` — conftest fixture conventions; DATA-04's Postgres marker extends existing shape without replacing

### Files Phase 4 will touch

**Models / DB layer (FK index audit + naming_convention inheritance)**
- `backend/app/api/models/build_list.py` — add `index=True` on `user_id`, `car_id`
- `backend/app/api/models/part.py` — add `index=True` on `user_id`, `category_id` (confirm during audit)
- `backend/app/api/models/build_list_part.py` — add `index=True` on `build_list_id`, `part_id`, `added_by`
- `backend/app/api/models/build_log.py` — verify `build_log_id` index on `BuildLogPost`
- `backend/app/api/models/*.py` — full audit sweep per D-12 through D-17 (planner enumerates)
- `backend/app/db/session.py` — `pool_recycle=3600` → `1800` (D-20)

**Alembic**
- `backend/alembic/versions/YYYYMMDD_NN_add_missing_fk_indexes.py` — NEW, autogenerated (D-12)
- `backend/alembic/versions/YYYYMMDD_NN_backfill_build_logs_for_legacy_build_lists.py` — NEW, data migration (D-24)

**Endpoints / services (session.query sweep + DATA-08 lazy-branch deletion)**
- `backend/app/api/endpoints/build_logs.py` — fix N+1 (D-32), delete lazy auto-create branches at `:86-98` and `:191-201` (D-25)
- `backend/app/api/endpoints/auth.py` (33 sites), `admin.py` (28), `build_lists.py` (19), `parts.py` (18), `users.py` (9), `build_list_parts.py` (9), `crawled_pages.py` (7), `images.py` (6) — session.query sweep (D-06 through D-11)
- `backend/app/api/services/part_linker_service.py` — wrap `link_new_part`, `reelect_canonical`, `unlink_part` in `with_for_update()` row locks (D-01, D-05)
- `backend/app/api/services/{report_service, part_listing_service, bug_report_service, base_report_service, vote_service, build_list_service, base_vote_service}.py` — session.query sweep
- `backend/app/api/utils/common_patterns.py` (12 sites), `base_endpoint_router.py`, `base_vote_router.py`, `base_report_router.py`, `admin_endpoint_patterns.py`, `bucket_orphan_utils.py` — session.query sweep
- `backend/app/services/job_service.py` (8 sites) — session.query sweep
- `backend/app/crawlers/runner.py` (9 sites), `ecs_runner.py`, `ecs_rescrape_runner.py`, `archive_rescrape.py`, `base.py` — session.query sweep
- `backend/app/api/services/part_inference/car_inference.py` — docstring on AMBIGUOUS_STANDALONE_CODES (D-36)

**Tests**
- `backend/tests/conftest.py` — add `query_counter` fixture (D-33), add `postgres` marker registration
- `backend/tests/test_session_query_regression.py` — NEW, grep-based guard (D-09)
- `backend/tests/test_build_log_n_plus_one.py` — NEW, query-count regression (D-33)
- `backend/tests/services/test_part_linker_concurrency.py` — NEW, Postgres-backed 10-thread test (D-01, D-05)
- `backend/tests/services/test_part_linker_integration.py` — NEW, SQLite integration tests (D-39)
- `backend/tests/test_car_inference_ambiguity.py` — NEW, fixed-vector regression (D-37)

**CI**
- `.github/workflows/backend-ci.yml` — add Postgres `services` block (D-03) for the concurrency-test step; keep SQLite as default for the rest of the suite
- `docker-compose.test.yml` — add `postgres-test` service for local developer use (D-03)
- `backend/pytest.ini` — register `postgres` marker

**Docs**
- `.planning/codebase/CONVENTIONS.md` — add "Alembic downgrade testing" subsection (D-31)
- `backend/CLAUDE.md` (project-level) — optional one-line pointer to `query_counter` fixture for future ORM work

### No external specs required

Requirements are fully captured in REQUIREMENTS.md + decisions above. No ADRs or external design docs referenced.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`backend/app/api/services/build_list_service.py:82-88`** — Build log eager-create already implemented for new build lists. DATA-08's target is deleting the lazy fallback branches in `build_logs.py`, not adding new eager logic.
- **`backend/app/api/services/part_linker_service.py`** — Complete canonical-parts logic (`link_new_part`, `reelect_canonical`, `unlink_part`, `_point_siblings_at`, `resolve_canonical`, `link_group_part_ids`). Phase 4's DATA-03 work is a surgical addition of `db.query(DBPart).filter(...).with_for_update()` (or the `select().with_for_update()` equivalent after D-06) at the read sites inside these functions — the algorithm stays.
- **`backend/app/db/session.py`** — Current pool config `pool_size=25, max_overflow=75, API_CONNECTION_RESERVE=20, pool_pre_ping=True, pool_recycle=3600`. The trio of pool-size constants is consumed by Phase 3's crawler worker formula (`DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE = 80`). Phase 4 changes ONLY `pool_recycle`.
- **`backend/tests/conftest.py`** — Existing `engine` (session-scoped SQLite in-memory with SAVEPOINT-based per-test isolation), `db_session`, `client`, `create_and_login_user` fixtures. Phase 4 adds `query_counter` + `postgres` marker WITHOUT touching the existing fixture set.
- **`backend/app/db/base_class.py`** — `MetaData(naming_convention=...)` landed in Phase 1 SAFE-09. All Phase 4 autogenerated indexes inherit deterministic names (`ix_<table>_<column>`).
- **Existing `__table_args__` on `vote`, `report`, `webauthn_credential`, `crawled_page`, `part_listing`** — Composite indexes already in place. FK-index audit preserves these and only adds single-column indexes for uncovered FKs.
- **`backend/tests/test_pydantic_v1_regression.py` + `test_logger_migration_regression.py`** (Phase 3 QUAL-02, QUAL-07) — Grep-based regression-guard test pattern. Phase 4's `test_session_query_regression.py` (D-09) follows the same shape.

### Established Patterns

- **Alembic autogenerate-only** (CLAUDE.md) — Every Phase 4 schema change (FK indexes, build_log backfill) uses `alembic revision --autogenerate`. Data migrations (D-24) scaffold the revision file via autogenerate and hand-write the body; the skeleton is autogenerated.
- **`pytest -n auto --dist=loadfile`** — All new tests must be worker-safe. The Postgres-marked concurrency test (D-01) is marked with `postgres` AND uses `@pytest.mark.serial` (if that marker exists — planner verifies) OR grabs a per-worker Postgres database to avoid cross-worker interference.
- **`# SAFE:` annotation convention** (Phase 1 SAFE-04) — Data migration's `downgrade()` method (D-26) annotates "no-op intentional" with `# SAFE: forward-only data backfill; no reversal needed` so the DROP-guard CI step doesn't false-positive.
- **Env-gate by `APP_ENVIRONMENT` / `TESTING`** (Phase 2 D-01, Phase 3) — `POSTGRES_TEST_URL` (new, D-02) follows the same pattern: unset = SQLite default; set = Postgres-backed for marked tests.
- **Module-level logger** (Phase 3 D-33 through D-37) — Any new Phase 4 test or service code uses `logger = logging.getLogger(__name__)` at module top. No `Depends(get_logger)`.
- **`MetaData.naming_convention`** (Phase 1 SAFE-09 / D-11 through D-14) — All autogenerated Phase 4 indexes inherit deterministic names. No manual naming.
- **Transactional-test pattern with SAVEPOINTs** (conftest.py:60-80) — Every existing test rolls back cleanly. Phase 4 concurrency test BREAKS this pattern intentionally (real transactions, not SAVEPOINTs, to exercise row locks) — that's the reason the Postgres marker is opt-in.

### Integration Points

- **Phase 1 migration DROP-guard** — Phase 4's data-migration `downgrade()` (D-26) is a no-op; the `# SAFE:` annotation satisfies the guard.
- **Phase 1 OpenAPI snapshot (`backend/tests/test_openapi_snapshot.py`)** — Phase 4 makes no endpoint-signature changes; snapshot stays green.
- **Phase 1 auth + crawler characterization tests** — Phase 4 adds selectinload + session.scalars but does not change response shapes or HTTP semantics; characterization tests stay green.
- **Phase 2 Sentry LoggingIntegration** — FK-constraint violations during migration surface in Sentry with `request_id` + `user_id` + (if applicable) `adapter` tag. Phase 4 does not change Sentry config.
- **Phase 3 ThreadPoolExecutor worker count** — D-14's `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE = 80` depends on Phase 4 NOT lowering these. D-18 preserves them.
- **Phase 5 (upcoming) admin.py + auth.py splits** — Every new file Phase 5 creates inherits Phase 4's session.scalars API. No mixed-regime work.
- **ECS crawler `SessionLocal()` per worker** — Phase 4's session.query sweep reaches into `backend/app/crawlers/runner.py` + `ecs_runner.py` + `ecs_rescrape_runner.py` + `archive_rescrape.py` + `base.py`. Tests stay Sentry-transport-stubbed; no cascading change.
- **`pytest.ini addopts`** — Phase 1 D-03 enforces `--cov-fail-under=51` via `pytest.ini addopts`. Phase 4's new tests add coverage; do not regress.

</code_context>

<specifics>
## Specific Ideas

- **"Postgres in CI because SQLite can't prove row-lock fixes"** — D-01, D-02. The FOR UPDATE test is meaningless on SQLite. Adding Postgres as an opt-in `services:` block in CI is the correct scope for a row-lock fix; NOT converting the entire suite.
- **"Pool sizing is a capacity envelope, not a literal constant"** — D-18. REQUIREMENTS.md's `pool_size=50` is a floor; total capacity (pool_size + max_overflow = 100) already exceeds it. The REQ literal reading would CUT total capacity by half and break Phase 3's crawler worker formula — so the deviation is deliberate, documented, and safer for the crawler subsystem.
- **"Delete lazy branches, backfill the data, then assert"** — D-23, D-24, D-27. The eager-create logic already lives in `build_list_service.py`; DATA-08's value is removing dead fallback code (preconditions change: every build list has a log). Data migration backfills the preconditions, code change enforces the new invariant.
- **"Selective lazy=raise, not global"** — D-28, D-29. Global `lazy="raise"` is a fixture earthquake across 50+ test files and every endpoint using ORM relationships. Scoped to 2-3 N+1-prone relationships, it catches the actual debt without collateral damage.
- **"Grep + regression test = the audit trail"** — D-09. Phase 3's pattern (QUAL-02 / QUAL-07) proves this works. The `test_session_query_regression.py` grep is a live CI gate, not a one-time audit.
- **"One migration per concern"** — D-16, D-24. FK-index-only migration is structurally separate from build_log backfill; each is small, focused, and trivially revertable. Keeps the review surface narrow.
- **"Autogenerate resolves the naming-convention mismatch for free"** — D-12, D-13. Phase 1 SAFE-09 landed naming_convention on Base.metadata; autogenerated indexes inherit it automatically. No manual naming in the new migration.
- **"Session.query sweep is mechanical, not architectural"** — D-06, D-11. The sweep preserves every transaction boundary, every flush / commit, every session lifecycle. It is the smallest surface-change possible that delivers the REQUIREMENTS literal (`db.scalars(select(...))`).

</specifics>

<deferred>
## Deferred Ideas

### Deferred to Phase 5 or later

- **Global `lazy="raise"` on every relationship** — D-29 scopes Phase 4 to 2-3 N+1-prone relationships. A codebase-wide audit + fix sweep is a future tech-debt task, not Phase 4 scope.
- **CI-automated migration downgrade testing** — D-31 lands documentation in CONVENTIONS.md. Running `alembic upgrade → downgrade → upgrade` in CI as a gated step requires Postgres service side-car availability for migration CI (currently only the concurrency test uses it), and handling migrations that fail round-trip cleanly. Defer until that infra proves out in Phase 4.
- **`car_inference` ML-based disambiguation (PARTS-V2-01)** — Explicitly deferred to v2 per REQUIREMENTS.md. Phase 4 just pins current behavior (D-37).
- **Optimistic concurrency control (`version_id_col`)** — PARTS-V2-03 in REQUIREMENTS.md. Pessimistic `with_for_update` suffices at current low traffic; optimistic concurrency is for scale that hasn't arrived.
- **Async SQLAlchemy migration** — PERF-V2-03 explicitly deferred. Phase 4 stays on sync SQLAlchemy.
- **Query-result caching (Redis)** — PERF-V2-01 explicitly deferred.
- **Retroactive rename of historic constraints to match Phase 1's naming_convention** — Explicitly deferred in Phase 1 (01-CONTEXT.md D-12). Phase 4 inherits the same posture: NEW indexes use the convention; OLD constraints keep their historic names.
- **Admin UI for part-curation-time ambiguity resolution (PARTS-V2-02)** — Out of scope.

### Deferred to late Phase 5 or Phase 6

- **Remove `session.query` redundant imports** — After the sweep, `from sqlalchemy.orm import Session` stays; `Session.query` is still callable (deprecated API, not removed). Phase 4's grep regression guard catches new usages; cleaning up unused imports is a follow-up pass.
- **Benchmark pool_recycle change** — D-20 changes `pool_recycle=3600` → `1800`. No A/B in Phase 4; measure in production post-deploy. If staleness / reconnect rate spikes or drops, adjust.
- **Global `__table_args__` normalization** — Some models use `__table_args__` tuples, others use `index=True` on mapped_column. Phase 4 follows local convention (add where missing, don't restructure). Normalizing style is a future polish task.

### Noted but not a Phase 4 deliverable

- **Postgres readonly replica (`PERF-V2-02`)** — Explicitly deferred to v2. Not a Phase 4 concern.
- **Alembic `--sql` mode for offline migration review** — Worth exploring for destructive migrations; not needed for Phase 4's index-only + backfill migrations.
- **`get_logger` export removal** — Phase 3 D-36 deferred this to late Phase 5 / early Phase 6. Phase 4 inherits the deferral.

</deferred>

---

*Phase: 04-db-parts-hardening*
*Context gathered: 2026-04-22 (auto mode)*
