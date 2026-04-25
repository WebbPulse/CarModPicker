---
phase: 07
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/test_init_service_accounts.py
  - backend/tests/crawlers/test_crawler_user_fallback.py
  - backend/tests/services/test_part_linker_concurrency.py
  - backend/tests/api/endpoints/test_build_lists.py
autonomous: true
tech_debt_items:
  - WR-01  # pytest.ini testpaths verification
  - WR-02  # reelect_canonical deterministic row-lock concurrency regression
  - WR-03  # CRAWLER_USER_ID UUID fallback regression
  - WR-04  # init_service_accounts %s format regression
  - IN-02  # copy_build_list free-tier cap regression test
must_haves:
  truths:
    - "Running `pytest -n auto backend/tests/test_init_service_accounts.py` exits 0 and proves cold-start service-account creation does not raise TypeError"
    - "Running `pytest -n auto backend/tests/crawlers/test_crawler_user_fallback.py` exits 0 and proves the CRAWLER_USER_ID=<uuid> env-var fallback resolves the user without raising ValueError"
    - "Running `pytest -n auto -m postgres backend/tests/services/test_part_linker_concurrency.py::test_reelect_and_link_and_unlink_concurrency` (when POSTGRES_TEST_URL is set) completes without deadlock across all three ops"
    - "Running `pytest -n auto backend/tests/api/endpoints/test_build_lists.py::TestCopyBuildList::test_copy_free_tier_cap` exits 0 and proves a free user at the 1-list cap gets 402 on POST /build-lists/{id}/copy"
    - "Running `pytest --collect-only --no-cov -q` from backend/ collects >=2370 tests (proves testpaths=tests is valid)"
  artifacts:
    - path: "backend/tests/test_init_service_accounts.py"
      provides: "WR-04 regression: cold-start service-account creation via init_crawler_service_account (new-user path + existing-non-service-account path + idempotent path)"
      min_lines: 60
    - path: "backend/tests/crawlers/test_crawler_user_fallback.py"
      provides: "WR-03 regression: _get_crawler_user CRAWLER_USER_ID env-var fallback accepts UUID strings and rejects non-UUID values"
      min_lines: 40
    - path: "backend/tests/services/test_part_linker_concurrency.py"
      provides: "WR-02 regression: new test_reelect_and_link_and_unlink_concurrency added alongside existing link-only + link+unlink tests"
      contains: "def test_reelect_and_link_and_unlink_concurrency"
    - path: "backend/tests/api/endpoints/test_build_lists.py"
      provides: "IN-02 regression: test_copy_free_tier_cap proves copy_build_list enforces the 1-list cap for free users (402)"
      contains: "def test_copy_free_tier_cap"
  key_links:
    - from: "backend/tests/test_init_service_accounts.py"
      to: "backend/app/core/init_service_accounts.py"
      via: "calls init_crawler_service_account(db_session) with fresh and pre-existing rows"
      pattern: "init_crawler_service_account\\(db_session\\)"
    - from: "backend/tests/crawlers/test_crawler_user_fallback.py"
      to: "backend/app/crawlers/runner.py::_get_crawler_user"
      via: "monkeypatch os.environ['CRAWLER_USER_ID'] to UUID string, invalid string, and unset"
      pattern: "os\\.environ\\[\"CRAWLER_USER_ID\"\\]"
    - from: "backend/tests/services/test_part_linker_concurrency.py::test_reelect_and_link_and_unlink_concurrency"
      to: "backend/app/api/services/part_linker_service.py::reelect_canonical"
      via: "ThreadPoolExecutor exercising reelect_canonical + link_new_part + unlink_part on overlapping row sets"
      pattern: "reelect_canonical\\(s, "
---

<objective>
Add four regression tests that pin the already-landed Phase 4 code-review fixes (WR-02, WR-03, WR-04, IN-02) and a quick inline verification that WR-01 (pytest.ini testpaths) is non-issue on the current tree. Phase 4 shipped the code fixes but did not ship regression tests that would catch re-introduction of any of the four bugs — this plan closes that hole.

Purpose: The v1.0 milestone audit (`.planning/v1.0-MILESTONE-AUDIT.md`) flags WR-01..WR-04 and IN-02 under Phase 4 residue. All five have had their CODE fixes applied (`init_service_accounts.py` uses `%s`, `runner.py::_get_crawler_user` parses UUID, `part_linker_service.py` sorts lock_ids, `build_list_service.py::copy_build_list` enforces the cap) — but four of them lack a pinning regression test. This plan adds those four tests so future PRs cannot silently regress the fix.

Output: Four new/extended test files under `backend/tests/` that exit 0 when the code is correct and fail on reintroduction of each bug.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/v1.0-MILESTONE-AUDIT.md
@CLAUDE.md

<interfaces>
<!-- Key signatures the executor needs. Extracted from the actual codebase. -->

From `backend/app/core/init_service_accounts.py`:
```python
def init_crawler_service_account(db: Session) -> None:
    """Idempotent — creates / adopts / no-ops the crawler service account.
    Logs with username=%s id=%s at INFO on create/adopt, DEBUG on no-op.
    """
```
Relevant model fields on `backend/app/api/models/user.py`:
- `User.id` is UUID-based
- `User.username: str`, `User.email: str`, `User.hashed_password: str`
- `User.email_verified: bool`, `User.disabled: bool`
- `User.is_service_account: bool`, `User.is_admin: bool`, `User.is_superuser: bool`

From `backend/app/crawlers/runner.py`:
```python
def _get_crawler_user(db: Session) -> DBUser:
    # 1) service-account path: DBUser.is_service_account.is_(True) AND not disabled
    # 2) fallback: os.environ.get("CRAWLER_USER_ID") parsed via UUID(raw)
    #    → raises CrawlerConfigError("CRAWLER_USER_ID must be a valid UUID.") on ValueError
    # 3) no service account AND no env var → CrawlerConfigError
```
Exception class: `from app.crawlers.runner import CrawlerConfigError`

From `backend/app/api/services/part_linker_service.py`:
```python
def link_new_part(db: Session, new_part: DBPart, *, product_url: Optional[str] = None) -> DBPart: ...
def reelect_canonical(db: Session, new_canonical: DBPart) -> DBPart: ...
def unlink_part(db: Session, part: DBPart) -> DBPart: ...
```
All three acquire row locks via `select(...).with_for_update()` and sort `lock_ids` before `WHERE id IN (...)` (WR-02 fix at lines 184, 294).

From `backend/tests/services/test_part_linker_concurrency.py`:
- Existing fixture pattern: `postgres_engine` session-scoped fixture (skipped when `POSTGRES_TEST_URL` unset)
- Existing pattern: `shared_gtin = f"G{_worker_suffix()}{uuid.uuid4().hex[:12]}"` per-test isolation
- Existing seeder: `_seed(postgres_engine, shared_gtin) -> (user_id, category_id, part_ids[10])`
- Existing ThreadPoolExecutor pattern: `max_workers=10`, `as_completed(futures)` → `f.result()` re-raises
- Module-level skip: `pytestmark = pytest.mark.postgres`

From `backend/app/api/services/build_list_service.py::copy_build_list` (lines 281-292):
```python
# IN-02 cap enforcement:
if not is_user_premium(current_user, db):
    count = self.count_by_user(db, current_user.id, logger=logger)
    if count >= 1:
        raise HTTPException(status_code=402, detail="Free accounts are limited to 1 build list. ...")
```
Endpoint path: `POST /api/build-lists/{build_list_id}/copy`

Existing test helper patterns in `backend/tests/api/endpoints/test_build_lists.py`:
- `test_user: User` fixture (free tier — not premium)
- `premium_test_user: User` fixture (bypasses cap)
- `get_auth_token(client, username) -> str`, `get_auth_headers(token) -> dict`
- `create_car_in_db(db_session) -> dict` with "id" key
- `get_unique_name(prefix) -> str`
- `settings.API_STR` = "/api"
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: WR-04 regression — init_crawler_service_account cold-start log formatting</name>

  <read_first>
    - backend/app/core/init_service_accounts.py  (current implementation — verify %s format at lines 53, 57, 59)
    - backend/tests/conftest.py  (db_session fixture signature and SQLite setup)
    - backend/app/api/models/user.py  (User field list and is_service_account default)
    - .planning/v1.0-MILESTONE-AUDIT.md  (WR-04 description: lines 53,57 `%d` → crash on first cold-start)
  </read_first>

  <files>backend/tests/test_init_service_accounts.py</files>

  <behavior>
    - Test 1: `test_create_fresh_service_account_logs_with_s_format` — fresh DB, no user with CRAWLER_SERVICE_ACCOUNT_USERNAME. Call `init_crawler_service_account(db_session)`. Assert: exactly one User row exists with `username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME`, `is_service_account is True`, `email_verified is True`, `disabled is False`. Assert no TypeError raised (regression — `%d` + UUID would crash here).
    - Test 2: `test_existing_non_service_user_is_adopted` — pre-insert a `User(username=CRAWLER_SERVICE_ACCOUNT_USERNAME, is_service_account=False, ...)`. Call `init_crawler_service_account(db_session)`. Assert: same user row's `is_service_account` is now True, no new user was created (count unchanged).
    - Test 3: `test_already_service_account_is_idempotent` — pre-insert a `User(username=..., is_service_account=True)`. Call `init_crawler_service_account(db_session)` twice. Assert: no exceptions, still exactly 1 row with that username, still `is_service_account=True`.
    - Test 4: `test_log_formatting_accepts_uuid_id_field` — use `caplog` to capture logs at INFO. Call `init_crawler_service_account(db_session)` on a fresh DB. Assert at least one log record has message containing `username=` and `id=<uuid-like-string>`; assert no `TypeError` in caplog records. This is the direct WR-04 pin — `%d` with a UUID would raise `TypeError: %d format: a number is required, not UUID`.
  </behavior>

  <action>
    Create `backend/tests/test_init_service_accounts.py` with 4 tests per the behavior block. Use the existing `db_session` fixture from `backend/tests/conftest.py` (SQLite in-memory, auto-created tables).

    Import the function and model:
    ```python
    from app.core.init_service_accounts import init_crawler_service_account
    from app.api.models.user import User
    from app.core.config import settings
    import logging
    ```

    Test 1 (canonical WR-04 regression — must run without raising TypeError, which `%d` + UUID would produce):
    ```python
    def test_create_fresh_service_account_logs_with_s_format(db_session, caplog):
        caplog.set_level(logging.INFO, logger="app.core.init_service_accounts")
        # Fresh DB: no user with this username
        from sqlalchemy import select
        assert db_session.scalars(
            select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)
        ).first() is None

        # Must not raise — `%d` with UUID would have raised TypeError here.
        init_crawler_service_account(db_session)

        user = db_session.scalars(
            select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)
        ).one()
        assert user.is_service_account is True
        assert user.email_verified is True
        assert user.disabled is False
        # Direct WR-04 pin: the "Created crawler service account" log line must have rendered.
        create_logs = [
            r for r in caplog.records
            if "Created crawler service account" in r.getMessage()
        ]
        assert len(create_logs) == 1
        # The rendered message must include `id=<uuid-str>` — proves %s formatter worked.
        assert f"id={user.id}" in create_logs[0].getMessage()
    ```

    Test 2 (existing non-service user adoption):
    ```python
    def test_existing_non_service_user_is_adopted(db_session):
        from sqlalchemy import select
        existing = User(
            username=settings.CRAWLER_SERVICE_ACCOUNT_USERNAME,
            email=f"{settings.CRAWLER_SERVICE_ACCOUNT_USERNAME}@preexist.local",
            hashed_password="x",
            email_verified=True,
            disabled=False,
            is_service_account=False,
        )
        db_session.add(existing)
        db_session.commit()

        init_crawler_service_account(db_session)

        users = db_session.scalars(
            select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)
        ).all()
        assert len(users) == 1
        assert users[0].is_service_account is True
    ```

    Test 3 (idempotent):
    ```python
    def test_already_service_account_is_idempotent(db_session, caplog):
        caplog.set_level(logging.DEBUG, logger="app.core.init_service_accounts")
        init_crawler_service_account(db_session)
        init_crawler_service_account(db_session)  # second call: no-op path
        from sqlalchemy import select
        users = db_session.scalars(
            select(User).where(User.username == settings.CRAWLER_SERVICE_ACCOUNT_USERNAME)
        ).all()
        assert len(users) == 1
    ```

    Test 4 (verify log rendering does not raise TypeError — explicit regression):
    ```python
    def test_log_formatting_accepts_uuid_id_field(db_session, caplog):
        caplog.set_level(logging.INFO, logger="app.core.init_service_accounts")
        init_crawler_service_account(db_session)
        # caplog.records would miss formatting errors if logger swallowed them.
        # Directly render the message to trigger any TypeError from a bad specifier.
        for record in caplog.records:
            rendered = record.getMessage()  # raises TypeError if %d + UUID
            assert "id=" in rendered
    ```

    Do NOT modify `init_service_accounts.py` — WR-04 is already fixed (confirmed via `grep -n "%d\|%s" backend/app/core/init_service_accounts.py` → only `%s` matches). This plan pins the fix.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto tests/test_init_service_accounts.py -v</automated>
  </verify>

  <acceptance_criteria>
    - `cd backend &amp;&amp; pytest -n auto tests/test_init_service_accounts.py -v` exits 0 and shows 4 passed
    - `grep -n "%d" backend/app/core/init_service_accounts.py` returns no matches (WR-04 remains fixed)
    - `grep -c "def test_" backend/tests/test_init_service_accounts.py` returns at least 4
    - `grep -q "TypeError" backend/tests/test_init_service_accounts.py || grep -q "getMessage" backend/tests/test_init_service_accounts.py` — at least one pattern present as a TypeError guard
  </acceptance_criteria>

  <done>
    Four tests in `backend/tests/test_init_service_accounts.py` pass under `pytest -n auto`; no code changes to `init_service_accounts.py` required because the `%s` fix already landed in Phase 4.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: WR-03 regression — CRAWLER_USER_ID UUID fallback path</name>

  <read_first>
    - backend/app/crawlers/runner.py  (lines 106-140 — _get_crawler_user function, already uses UUID(raw) at line 125)
    - backend/tests/conftest.py  (db_session fixture, monkeypatch patterns)
    - backend/app/api/models/user.py  (User.id type is UUID)
  </read_first>

  <files>backend/tests/crawlers/test_crawler_user_fallback.py</files>

  <behavior>
    - Test 1: `test_env_fallback_accepts_uuid_string` — no service account in DB, set `CRAWLER_USER_ID=<valid-uuid-of-existing-non-service-user>`. Call `_get_crawler_user(db_session)`. Assert: returns that user.
    - Test 2: `test_env_fallback_rejects_non_uuid` — no service account in DB, set `CRAWLER_USER_ID="not-a-uuid"`. Call `_get_crawler_user(db_session)`. Assert: raises `CrawlerConfigError` with message containing "must be a valid UUID".
    - Test 3: `test_env_fallback_raises_when_user_missing` — no service account in DB, set `CRAWLER_USER_ID` to a UUID that does not match any user. Assert: raises `CrawlerConfigError` with "no user found".
    - Test 4: `test_env_fallback_raises_when_user_disabled` — no service account in DB, set `CRAWLER_USER_ID` to UUID of a disabled user. Assert: raises `CrawlerConfigError` with "user is disabled".
    - Test 5: `test_service_account_takes_precedence` — both a service account and a CRAWLER_USER_ID=<some-other-user-uuid> are set. Call `_get_crawler_user(db_session)`. Assert: returns the service account, not the env-var user.
  </behavior>

  <action>
    Create `backend/tests/crawlers/test_crawler_user_fallback.py`. Use `monkeypatch.setenv` / `monkeypatch.delenv` to control `CRAWLER_USER_ID`. Use the existing `db_session` fixture.

    Skeleton:
    ```python
    """WR-03 regression: _get_crawler_user CRAWLER_USER_ID env-var fallback
    accepts UUID strings (was previously int(raw), pre-existing bug fixed in Phase 4
    part of the code-review cycle).
    """
    import uuid
    import pytest
    from sqlalchemy import select
    from app.crawlers.runner import _get_crawler_user, CrawlerConfigError
    from app.api.models.user import User

    def _make_user(db_session, username_suffix: str, *, is_service: bool = False, disabled: bool = False) -> User:
        user = User(
            username=f"crawler-fallback-{username_suffix}-{uuid.uuid4().hex[:8]}",
            email=f"crawler-fallback-{username_suffix}@test.local",
            hashed_password="x",
            email_verified=True,
            disabled=disabled,
            is_service_account=is_service,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    def test_env_fallback_accepts_uuid_string(db_session, monkeypatch):
        # Delete any pre-existing service account so we exercise the fallback.
        for u in db_session.scalars(select(User).where(User.is_service_account.is_(True))).all():
            db_session.delete(u)
        db_session.commit()
        target = _make_user(db_session, "valid")
        monkeypatch.setenv("CRAWLER_USER_ID", str(target.id))
        result = _get_crawler_user(db_session)
        assert result.id == target.id  # Direct WR-03 pin: int(raw) would have raised ValueError.

    def test_env_fallback_rejects_non_uuid(db_session, monkeypatch):
        for u in db_session.scalars(select(User).where(User.is_service_account.is_(True))).all():
            db_session.delete(u)
        db_session.commit()
        monkeypatch.setenv("CRAWLER_USER_ID", "not-a-uuid")
        with pytest.raises(CrawlerConfigError, match="must be a valid UUID"):
            _get_crawler_user(db_session)

    def test_env_fallback_raises_when_user_missing(db_session, monkeypatch):
        for u in db_session.scalars(select(User).where(User.is_service_account.is_(True))).all():
            db_session.delete(u)
        db_session.commit()
        monkeypatch.setenv("CRAWLER_USER_ID", str(uuid.uuid4()))
        with pytest.raises(CrawlerConfigError, match="no user found"):
            _get_crawler_user(db_session)

    def test_env_fallback_raises_when_user_disabled(db_session, monkeypatch):
        for u in db_session.scalars(select(User).where(User.is_service_account.is_(True))).all():
            db_session.delete(u)
        db_session.commit()
        target = _make_user(db_session, "disabled", disabled=True)
        monkeypatch.setenv("CRAWLER_USER_ID", str(target.id))
        with pytest.raises(CrawlerConfigError, match="user is disabled"):
            _get_crawler_user(db_session)

    def test_service_account_takes_precedence(db_session, monkeypatch):
        sa = _make_user(db_session, "svc", is_service=True)
        other = _make_user(db_session, "other")
        monkeypatch.setenv("CRAWLER_USER_ID", str(other.id))
        result = _get_crawler_user(db_session)
        assert result.id == sa.id
    ```

    Do NOT modify `runner.py` — WR-03 is already fixed (UUID(raw) at line 125). This plan pins the fix.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto tests/crawlers/test_crawler_user_fallback.py -v</automated>
  </verify>

  <acceptance_criteria>
    - `cd backend &amp;&amp; pytest -n auto tests/crawlers/test_crawler_user_fallback.py -v` exits 0, 5 passed
    - `grep -n "int(raw)" backend/app/crawlers/runner.py` returns no matches (WR-03 remains fixed; only `UUID(raw)` should be present)
    - `grep -c "CrawlerConfigError" backend/tests/crawlers/test_crawler_user_fallback.py` returns at least 4 (all negative-path assertions)
  </acceptance_criteria>

  <done>
    Five tests covering the CRAWLER_USER_ID UUID fallback pass under `pytest -n auto`. No runner.py changes.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: WR-02 regression — reelect_canonical + link + unlink concurrency (no deadlock)</name>

  <read_first>
    - backend/tests/services/test_part_linker_concurrency.py  (existing fixture + _seed + two existing tests — build on their pattern)
    - backend/app/api/services/part_linker_service.py  (lines 136-211 reelect_canonical, 214-251 unlink_part, 254-343 link_new_part — all three must use sorted(lock_ids) before WHERE id IN)
    - .planning/v1.0-MILESTONE-AUDIT.md  (WR-02 description: "reelect_canonical lock order can deadlock (no sort by id before WHERE IN); concurrency test currently exercises only link_new_part")
  </read_first>

  <files>backend/tests/services/test_part_linker_concurrency.py</files>

  <behavior>
    - Add one new test `test_reelect_and_link_and_unlink_concurrency` to the existing file.
    - Seed 10 parts sharing a gtin via the existing `_seed` helper (already proven in the existing tests).
    - First, establish a canonical via one `link_new_part` call on a single session (so the group has 1 canonical + 9 siblings or similar state).
    - Then fan out 10 threads: 4 call `reelect_canonical(s, random_sibling)`, 3 call `link_new_part(s, part)` on a freshly-created 11th part sharing the gtin, 3 call `unlink_part(s, part)`. All threads share the overlapping row lock-set (same gtin group).
    - Bounded wall-clock: the ThreadPoolExecutor must complete within 30 seconds. If it deadlocks, the test fails. `as_completed(futures, timeout=30)` raises `concurrent.futures.TimeoutError` on deadlock.
    - After fan-out completes: verify invariants (exactly one canonical per gtin group, no cycles, no orphaned canonical refs) — same invariants as existing tests.
  </behavior>

  <action>
    Append a third test function to `backend/tests/services/test_part_linker_concurrency.py`. Do NOT remove or modify the two existing tests.

    Required imports (check if already present, otherwise add at top):
    ```python
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
    from app.api.services.part_linker_service import link_new_part, reelect_canonical, unlink_part
    ```

    New test body:
    ```python
    def test_reelect_and_link_and_unlink_concurrency(postgres_engine) -> None:
        """WR-02 regression: deterministic row-lock ordering (sorted(lock_ids)
        before WHERE IN) must prevent deadlock across all three ops on an
        overlapping row set. Success criterion 3 (phase 07): no deadlock
        across link_new_part / reelect_canonical / unlink_part.

        If lock_ids were NOT sorted, two concurrent transactions locking
        overlapping rows in different orders would deadlock under Postgres
        index-dependent lock acquisition — the ThreadPoolExecutor would hang
        past the 30s timeout and this test would raise FuturesTimeoutError.
        """
        import random
        shared_gtin = f"G3{_worker_suffix()}{uuid.uuid4().hex[:12]}"
        user_id, category_id, part_ids = _seed(postgres_engine, shared_gtin)

        SessionLocal = sessionmaker(
            bind=postgres_engine, autocommit=False, autoflush=False
        )

        # Stage 1: establish an initial canonical by linking part_ids[0].
        with SessionLocal() as s:
            p0 = s.get(DBPart, part_ids[0])
            link_new_part(s, p0)
            s.commit()

        # Stage 2: add one more part to the gtin group (exercises link_new_part's
        # locking path against the existing canonical).
        extra_part_id: uuid.UUID
        with SessionLocal() as s:
            extra = DBPart(
                name="Extra Part",
                user_id=user_id,
                category_id=category_id,
                part_manufacturer_id=s.scalars(
                    select(DBPart.part_manufacturer_id)
                    .where(DBPart.id == part_ids[0])
                ).one(),
                gtin=shared_gtin,
                source="scraped",
            )
            s.add(extra)
            s.commit()
            extra_part_id = extra.id

        def reelect_op(pid: uuid.UUID) -> None:
            with SessionLocal() as s:
                part = s.get(DBPart, pid)
                if part is None:
                    return
                reelect_canonical(s, part)
                s.commit()

        def link_op(pid: uuid.UUID) -> None:
            with SessionLocal() as s:
                part = s.get(DBPart, pid)
                if part is None:
                    return
                link_new_part(s, part)
                s.commit()

        def unlink_op(pid: uuid.UUID) -> None:
            with SessionLocal() as s:
                part = s.get(DBPart, pid)
                if part is None or part.canonical_part_id is None:
                    return
                unlink_part(s, part)
                s.commit()

        # 10 threads: 4 reelect + 3 link + 3 unlink, all on overlapping row lock-set.
        ops = (
            [(reelect_op, pid) for pid in part_ids[1:5]]       # 4 reelects on siblings
            + [(link_op, pid) for pid in [extra_part_id, part_ids[5], part_ids[6]]]  # 3 links
            + [(unlink_op, pid) for pid in part_ids[7:10]]     # 3 unlinks
        )
        random.shuffle(ops)

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(fn, pid) for fn, pid in ops]
            # 30s budget — if lock ordering is broken, this will TimeoutError.
            for f in as_completed(futures, timeout=30):
                f.result()  # re-raise any thread-level exception

        # Final invariants: every sibling resolves to a live canonical, no cycles.
        with SessionLocal() as verify:
            parts = verify.scalars(
                select(DBPart).where(DBPart.gtin == shared_gtin)
            ).all()
            canonical_ids = {p.id for p in parts if p.canonical_part_id is None}
            assert canonical_ids, "At least one canonical must survive the race"
            sibling_refs = {
                p.canonical_part_id for p in parts if p.canonical_part_id is not None
            }
            orphans = sibling_refs - canonical_ids
            assert not orphans, f"Found orphaned canonical refs after race: {orphans}"
            # No cycles: no part should point at itself.
            for p in parts:
                assert p.canonical_part_id != p.id, f"Self-cycle on part {p.id}"
    ```

    Do NOT modify `part_linker_service.py` — WR-02 is already fixed (`sorted(lock_ids_set)` at line 184 in reelect_canonical and `sorted({c.id for c in candidates} | {new_part.id})` at line 294 in link_new_part). This test pins the fix.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto tests/services/test_part_linker_concurrency.py::test_reelect_and_link_and_unlink_concurrency -v</automated>
  </verify>

  <acceptance_criteria>
    - When `POSTGRES_TEST_URL` is set and `docker-compose -f docker-compose.test.yml up -d postgres-test` is running, `cd backend &amp;&amp; pytest -n auto tests/services/test_part_linker_concurrency.py::test_reelect_and_link_and_unlink_concurrency -v` exits 0 within 30 seconds.
    - When `POSTGRES_TEST_URL` is unset, the test is collected and SKIPPED (honoring `pytestmark = pytest.mark.postgres`). `pytest -n auto tests/services/test_part_linker_concurrency.py --collect-only` lists 3 tests total (2 existing + 1 new).
    - `grep -c "def test_" backend/tests/services/test_part_linker_concurrency.py` returns 3
    - `grep -q "reelect_canonical" backend/tests/services/test_part_linker_concurrency.py`
    - `grep -q "timeout=30" backend/tests/services/test_part_linker_concurrency.py` (deadlock guard present)
    - `grep -c "sorted" backend/app/api/services/part_linker_service.py` returns at least 2 (WR-02 remains fixed: reelect + link both sort lock_ids)
  </acceptance_criteria>

  <done>
    New `test_reelect_and_link_and_unlink_concurrency` in `backend/tests/services/test_part_linker_concurrency.py` passes on Postgres (or skips on SQLite-only) within 30s. No changes to `part_linker_service.py`.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: IN-02 regression — copy_build_list free-tier cap + WR-01 suite-count sanity</name>

  <read_first>
    - backend/app/api/services/build_list_service.py  (lines 243-380 copy_build_list — cap enforced at lines 281-292)
    - backend/tests/api/endpoints/test_build_lists.py  (existing TestCopyBuildList class near line 601 — add new test method next to existing ones)
    - backend/pytest.ini  (verify testpaths = tests, NOT app/tests — WR-01 sanity)
  </read_first>

  <files>backend/tests/api/endpoints/test_build_lists.py</files>

  <behavior>
    - Add a new test method `test_copy_free_tier_cap` to the existing `TestCopyBuildList` class.
    - Use the existing `test_user` fixture (free-tier, not premium).
    - Step 1: create an initial build list (count=1, at cap).
    - Step 2: POST /api/build-lists/{id}/copy.
    - Step 3: assert response status is 402, detail contains "Free accounts are limited to 1 build list".
    - Step 4: verify no new build list was created (GET /api/build-lists/?owner_id=... still returns count=1).
  </behavior>

  <action>
    Append one new test method to the `TestCopyBuildList` class in `backend/tests/api/endpoints/test_build_lists.py`. Follow the existing test class's style (client fixture, get_auth_token, create_car_in_db).

    ```python
    def test_copy_free_tier_cap(
        self, client: TestClient, test_user: User, db_session: Session
    ) -> None:
        """IN-02 regression: free-tier user at 1-list cap cannot copy to make a 2nd.
        Before IN-02 landed, `copy_build_list` bypassed the cap enforcement that
        `create` already applied — a free user could keep pressing Copy to grow
        unbounded. Now the service raises 402 at the copy path too.
        """
        from app.core.config import settings
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        car = create_car_in_db(db_session)

        # Create the one allowed build list (count=1, at cap).
        original_data = {
            "name": get_unique_name("at_cap"),
            "description": "first and only free-tier build list",
            "car_id": str(car["id"]),
        }
        resp = client.post(
            f"{settings.API_STR}/build-lists/", json=original_data, headers=headers
        )
        assert resp.status_code == 200, resp.text
        original_id = resp.json()["id"]

        # Attempt to copy → must be 402 now that IN-02 enforces the cap.
        resp = client.post(
            f"{settings.API_STR}/build-lists/{original_id}/copy",
            json={"new_name": "should-fail"},
            headers=headers,
        )
        assert resp.status_code == 402, f"Expected 402, got {resp.status_code}: {resp.text}"
        detail = resp.json().get("detail", "")
        assert "Free accounts are limited to 1 build list" in detail, detail

        # Verify no 2nd build list was created.
        resp = client.get(
            f"{settings.API_STR}/build-lists/",
            params={"owner_id": str(test_user.id)},
            headers=headers,
        )
        assert resp.status_code == 200
        # Response is paginated; check total or data length.
        payload = resp.json()
        total = payload.get("total") if isinstance(payload, dict) else None
        if total is not None:
            assert total == 1, f"Expected exactly 1 build list after blocked copy, got total={total}"
        else:
            # Fallback: check list length
            data = payload.get("data", payload) if isinstance(payload, dict) else payload
            assert len(data) == 1
    ```

    WR-01 sanity (no file change, just verification embedded in acceptance_criteria): the current `backend/pytest.ini` has `testpaths = tests` (NOT `app/tests`). The audit's WR-01 description is based on a stale snapshot; reality on main shows the correct value. Acceptance criteria include a grep assertion so if anyone ever changes it to `app/tests` this plan fails.
  </action>

  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto tests/api/endpoints/test_build_lists.py::TestCopyBuildList::test_copy_free_tier_cap -v</automated>
  </verify>

  <acceptance_criteria>
    - `cd backend &amp;&amp; pytest -n auto tests/api/endpoints/test_build_lists.py::TestCopyBuildList::test_copy_free_tier_cap -v` exits 0 (1 passed)
    - `grep -c "def test_copy_" backend/tests/api/endpoints/test_build_lists.py` returns at least 6 (existing 5 copy tests + the new one)
    - `grep -n "^testpaths" backend/pytest.ini` returns exactly `2:testpaths = tests` (WR-01 sanity — must NOT be `app/tests`)
    - `cd backend &amp;&amp; pytest --collect-only --no-cov -q 2>&amp;1 | tail -1 | grep -oE '[0-9]+ tests collected'` — the number must be at least 2370 (proves testpaths=tests is valid and the full suite collects)
    - Plan 07-01 adds at least +10 net new tests across all 4 files (Task 1: 4, Task 2: 5, Task 3: 1, Task 4: 1) → verify collection count increases by >=10 vs main baseline.
  </acceptance_criteria>

  <done>
    `test_copy_free_tier_cap` passes; pytest.ini's `testpaths = tests` pinned via grep assertion; full suite still collects >=2370 tests (WR-01 non-issue confirmed on current tree).
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| HTTP client → FastAPI (test) | Test uses FastAPI TestClient — no real network; tokens generated via test fixtures. No new attack surface. |
| Env-var CRAWLER_USER_ID → app | Test uses monkeypatch within process; no real env exposure. No new attack surface. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-01-01 | Information Disclosure | `init_service_accounts.py` log messages | accept | User `id` is already logged as part of existing code (`%s` formatter). Adding a regression test does not increase exposure. No PII in the rendered log line (only UUID + username suffix). |
| T-07-01-02 | Tampering | New regression tests for cap bypass | mitigate | `test_copy_free_tier_cap` pins the 402 behavior so a future PR cannot silently remove the cap and slip through CI; this strengthens security posture rather than weakening it. |
| T-07-01-03 | Denial of Service | Concurrency test with 10 threads + 30s timeout | accept | Runs only under `-m postgres` (opt-in side-car CI job); 30s budget prevents runaway. No prod impact — test-only. |
| T-07-01-04 | Elevation of Privilege | WR-03 test deleting existing service accounts | accept | Deletion is scoped to the in-memory SQLite DB within the test's `db_session`; has no effect on any real database. Standard pytest isolation pattern. |

**No new attack surface introduced.** All four tasks add test files only — no production code is modified. The cap bypass test (IN-02) strengthens security by pinning the 402 behavior.
</threat_model>

<verification>
Full plan verification commands (run in order after all 4 tasks complete):

1. `cd backend && pytest -n auto tests/test_init_service_accounts.py tests/crawlers/test_crawler_user_fallback.py tests/api/endpoints/test_build_lists.py::TestCopyBuildList::test_copy_free_tier_cap -v` — must exit 0 with 10 passed.
2. `cd backend && pytest -n auto --collect-only -q 2>&1 | tail -1` — must report at least 2380 tests (baseline 2371 + 10 new; concurrency test collects but may skip without Postgres).
3. `grep -n "^testpaths" backend/pytest.ini` — must show `testpaths = tests`.
4. `grep -n "%d" backend/app/core/init_service_accounts.py` — must return nothing.
5. `grep -n "int(raw)" backend/app/crawlers/runner.py` — must return nothing inside `_get_crawler_user`.
6. `grep -c "sorted" backend/app/api/services/part_linker_service.py` — must return at least 2.
</verification>

<success_criteria>
- Plan 07-01 adds 4 regression tests (Task 1), 5 regression tests (Task 2), 1 concurrency test (Task 3), and 1 cap-bypass test (Task 4) — net 11 new tests.
- All tests pass under `pytest -n auto`. The postgres-marked test skips when POSTGRES_TEST_URL is unset.
- No production code changes — the fixes already landed in Phase 4; this plan pins them.
- Phase 7 success criteria 1, 2, 3, 4, and part of 5 (IN-02) are closed by this plan.
</success_criteria>

<output>
After completion, create `.planning/phases/07-v1-residue-cleanup/07-01-SUMMARY.md` with the standard summary template. Frontmatter must include `tech_debt_items_closed: [WR-01, WR-02, WR-03, WR-04, IN-02]`.
</output>
