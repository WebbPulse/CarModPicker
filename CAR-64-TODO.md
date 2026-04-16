# CAR-64: UUID v7 Migration — Remaining Work

Branch: `tyler/car-64-use-uuids-for-database-entities`

## Status

| Phase | State |
|---|---|
| Backend models → `Uuid(as_uuid=True)` + `default=uuid7` | ✅ Done |
| Backend Pydantic schemas → `UUID` | ✅ Done |
| Backend endpoint/router path params → `UUID` | ✅ Done |
| Backend services/utils/crawlers/jobs → `UUID` | ✅ Done |
| Alembic migration `5a381dff5fd1_migrate_all_pks_and_fks_to_uuid7.py` (destructive drop+recreate from metadata) | ✅ Done — applied against local Postgres; verified `users.id` column type is `uuid` |
| Frontend `types/Api.ts` → `string` IDs | ✅ Done |
| Frontend `services/Api.ts` → `string` IDs | ✅ Done |
| Frontend consumer files (pages, components, hooks, test mocks) | ✅ Done — `npx tsc -b` clean, `npm run build` clean |
| Chrome extension types | ✅ Done — `npm run build` clean |
| Backend test suite | ❌ **180 failing** — primary remaining blocker |
| Git commit + PR against `main` | ⏳ Pending tests green |

---

## Remaining work

### 1. Fix backend test failures (primary blocker — 180 tests failing)

`pytest -n auto` results: `180 failed, 556 passed, 111 warnings`.

**Root cause categories:**

1. **Hardcoded integer IDs in test URLs.** Tests call endpoints like `/api/users/9999999` expecting `404 Not Found`; FastAPI now returns `422 Unprocessable Entity` because `9999999` isn't a valid UUID. Fix: replace integer sentinels with valid-but-nonexistent UUIDs (e.g., `"00000000-0000-0000-0000-000000000000"` or `str(uuid.uuid4())`). First confirmed case: `tests/api/endpoints/test_users.py:159` — `test_read_user_by_id_not_found`.

2. **Test fixtures / factories producing integer IDs.** Any helper that builds entities and returns `id: int` needs to return `UUID`. Check `tests/conftest.py` and any `tests/factories.py` or similar.

3. **Mock service-layer calls passing integers.** Service-layer tests (`tests/utils/test_authorization.py::test_can_edit_build_list_part_build_list_owner` is one) likely construct mock objects with integer IDs. Switch to UUIDs.

4. **Test assertions comparing against integer IDs.** `assert response.json()["id"] == 1` won't work — server now returns a UUID string.

**Suggested approach:**
- Start by running `pytest -n auto tests/api/endpoints/test_users.py 2>&1 | head -50` and fixing that file end-to-end. The patterns it exposes apply to all other test files.
- Look at `tests/conftest.py` first for shared fixtures.
- Likely helpful: introduce a helper like `invalid_uuid = "00000000-0000-0000-0000-000000000000"` in conftest for the "not found" pattern.
- Consider delegating to a subagent: the work is mechanical across ~30 test files once the patterns are established.

**Files with failures (representative):**
- `tests/api/endpoints/test_users.py`, `test_users_admin.py`
- `tests/api/endpoints/test_global_parts.py`
- `tests/api/endpoints/test_build_lists.py`, `test_build_list_parts.py`, `test_build_logs.py`, `test_build_list_phases.py`
- `tests/api/endpoints/test_reports.py`, `test_votes.py`
- `tests/api/endpoints/test_search.py`, `test_categories.py`, `test_retailers.py`, `test_images.py`
- `tests/test_crawled_page_storage.py`
- `tests/utils/test_authorization.py`

### 2. Manual smoke test (after backend tests pass)

Per the plan's verification section:
- Start postgres (already running), `alembic upgrade head` (already applied), `uvicorn app.main:app --reload`, `npm run dev`.
- Create a new entity (car, build list, global part) and confirm the `id` in the API response is a UUID string like `"019687a2-3f4e-7abc-..."`.
- Visit a URL like `/builder/buildlist/<uuid>` and confirm the page loads.
- Vote and report flows should still work.

### 3. Commit and open PR

Once tests are green:
- `git add -A` (review for `.env` or anything secret — there should be none in this branch)
- Single squash-friendly commit, or multiple logically grouped commits
- `git push -u origin tyler/car-64-use-uuids-for-database-entities`
- `gh pr create` against `main` with summary referencing CAR-64

---

## Notes / gotchas for the continuing session

- **uuid7 source**: Python 3.13 does *not* have `uuid.uuid7` in stdlib (that lands in 3.14). Models use `uuid6==2025.0.1` via `from uuid6 import uuid7`. Already in `backend/requirements.txt`.
- **Alembic migration is destructive**: `Base.metadata.drop_all(bind) → create_all(bind)`. Dev-only, per the plan. Production would need a separate data-preserving strategy (not in scope for CAR-64 per the user's original request).
- **Pyright stale diagnostics**: Repeatedly observed Pyright complaining about `int`/`UUID` mismatches on lines I had just edited to `UUID`. Re-reading the file confirmed edits took. Ignore any such diagnostics that contradict the actual file contents.
- **`base_endpoint_router.py`**: The `update_entity` and `delete_entity` inner functions registered via `@router.put/@router.delete` decorators now take `entity_id: UUID`. FastAPI parses UUID path params natively.
- **ECS runners**: Both `app/crawlers/ecs_runner.py` and `app/crawlers/ecs_rescrape_runner.py` parse `JOB_ID`, `CRAWLER_USER_ID`, `CRAWLER_DEFAULT_CATEGORY_ID` from environment as `UUID(...)` now. The ECS task definition in Terraform may need the env-var docstrings updated if Terraform is the source of truth (check `terraform/`).
- **Existing migration chain**: Kept intact. The new migration (rev `5a381dff5fd1`) is the new head, built on `5f5924feaa24`. A fresh-DB bootstrap runs all migrations in order — older migrations create int tables, then this one drops and recreates with UUID schema. Slightly wasteful but preserves history.
