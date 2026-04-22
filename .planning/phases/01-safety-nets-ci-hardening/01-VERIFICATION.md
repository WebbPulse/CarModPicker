---
phase: 01-safety-nets-ci-hardening
verified: 2026-04-22T10:00:00Z
status: human_needed
score: 9/10 must-haves verified
overrides_applied: 0
deferred:
  - truth: "frontend/vitest.config.ts enforces coverage thresholds (lines: 60, functions: 50, branches: 50, statements: 60)"
    addressed_in: "Phase 1 Plan 01-09"
    evidence: "User explicitly chose Option C at plan 01-04 checkpoint: SAFE-03 deferred to plan 01-09 because frontend baseline (0.43% lines) is far below D-06 targets. D-06 literal values are staged as commented-out block in vitest.config.ts."
human_verification:
  - test: "Verify Dependabot is active in GitHub repository Insights tab"
    expected: "Navigate to GitHub repository → Insights → Dependency graph → Dependabot. Three ecosystems (pip, npm, github-actions) should show as active with 'Next check' showing the upcoming Monday."
    why_human: "Dependabot activation is a GitHub-side service action triggered by .github/dependabot.yml presence — cannot be verified programmatically from the local codebase."
  - test: "Record Google OAuth cassettes and confirm OAuth tests move from SKIPPED to PASSED"
    expected: "After running `cd backend && pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_signin.py` and `tests/auth/test_characterization_oauth_link.py` (with Google sandbox creds), commit the cassette YAMLs. Then run `pytest -n auto tests/auth/test_characterization_oauth_signin.py tests/auth/test_characterization_oauth_link.py -v` and confirm both report PASSED, not SKIPPED."
    why_human: "Cassette recording requires a Google sandbox account and real OAuth credentials. The skipif guards make the tests CI-green while cassettes are absent, but the guardrail is not functional until cassettes exist."
---

# Phase 01: Safety Nets & CI Hardening Verification Report

**Phase Goal:** Establish safety nets and CI hardening so Phase 2-5 refactoring work cannot silently regress. Land 10 SAFE-XX requirements (SAFE-01 through SAFE-10) covering coverage gates, migration repair + DROP guard, OpenAPI snapshot, auth/crawler characterization tests, naming conventions, and Dependabot.
**Verified:** 2026-04-22T10:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                          | Status              | Evidence                                                                                                     |
|----|------------------------------------------------------------------------------------------------|---------------------|--------------------------------------------------------------------------------------------------------------|
| 1  | Backend pytest.ini has `--cov-fail-under=<N>` at measured baseline                           | VERIFIED            | `--cov-fail-under=51` present in backend/pytest.ini between --cov-report=xml and parallel options comment    |
| 2  | Frontend CI runs `npm test -- --run --coverage` on every PR, placed before Build              | VERIFIED            | frontend-ci.yml step "Run tests" at index 7, Audit=6 Build=8. yaml parser confirms correct ordering          |
| 3  | Vitest coverage thresholds enforce 60/50/50/60 lines/functions/branches/statements             | DEFERRED            | Intentional: SAFE-03 deferred to plan 01-09 per user decision at checkpoint. Values staged as comments.      |
| 4  | Migration DROP guard (check_migrations.py) exits 0 on current tree and is wired into CI       | VERIFIED            | `python backend/scripts/check_migrations.py` exits 0, "OK (34 files scanned)". CI step between Scan and Run tests. |
| 5  | OpenAPI snapshot test is CI-green and catches schema drift                                     | VERIFIED            | `pytest tests/test_openapi_snapshot.py --no-cov` exits 0, 1 passed. 158 paths, 466 KB snapshot committed.    |
| 6  | All 7 auth happy-path flows have characterization tests (5 pass, 2 skip pending cassettes)    | VERIFIED            | 7 files exist in backend/tests/auth/. 5 non-VCR tests pass. 2 OAuth tests skip cleanly (cassettes absent).  |
| 7  | 5 crawler adapter characterization tests pin parse_product_page() output                      | VERIFIED            | All 5 tests pass (briantooleyracing, amsperformance, subispeed, texasspeed, cobbtuning). Real archived HTML. |
| 8  | Three broken drop_constraint(None) migrations are repaired via forward-only migration          | VERIFIED            | aa583927d86a exists with no-op upgrade + 3 named FK drops. 3 historic files have SAFE legacy annotations.   |
| 9  | SQLAlchemy Base.metadata.naming_convention has the 5 SQLAlchemy-recommended keys              | VERIFIED            | base_class.py contains NAMING_CONVENTION dict + MetaData(naming_convention=NAMING_CONVENTION). Keys: ck/fk/ix/pk/uq. |
| 10 | Dependabot v2 config covers pip/npm/github-actions with weekly Monday schedule, no ignore     | VERIFIED (partial)  | .github/dependabot.yml exists, YAML valid, 3 ecosystems, npm multi-dir, no ignore block. GitHub activation needs human check. |

**Score:** 9/10 truths verified (SAFE-03 deferred as intentional, Dependabot GitHub-side activation needs human confirmation)

### Deferred Items

Items not yet met but explicitly addressed in later milestone phases.

| # | Item                                                        | Addressed In      | Evidence                                                                                                  |
|---|-------------------------------------------------------------|-------------------|-----------------------------------------------------------------------------------------------------------|
| 1 | Vitest coverage threshold enforcement (SAFE-03)             | Phase 1 Plan 01-09 | User chose Option C at plan 01-04 checkpoint. D-06 values (lines:60, functions:50, branches:50, statements:60) staged as commented literals in frontend/vitest.config.ts. STATE.md documents deferral. |

### Required Artifacts

| Artifact                                                                 | Expected                                          | Status    | Details                                                                               |
|--------------------------------------------------------------------------|---------------------------------------------------|-----------|---------------------------------------------------------------------------------------|
| `backend/app/db/base_class.py`                                           | MetaData with 5-key naming_convention             | VERIFIED  | Contains NAMING_CONVENTION dict + declarative_base(metadata=metadata)                |
| `backend/tests/test_metadata_naming_convention.py`                       | 2 tests pinning convention keys and templates     | VERIFIED  | 2 test functions exist; both pass                                                     |
| `backend/alembic/versions/aa583927d86a_repair_drop_constraint_none_refs.py` | Forward-only repair migration                  | VERIFIED  | 4 SAFE annotations; upgrade()=pass; downgrade()=3 named FK drops                     |
| `backend/scripts/check_migrations.py`                                    | SAFE-04 DROP guard, CWD-independent, exit 0/1/2  | VERIFIED  | Exists, executable, DESTRUCTIVE_OP_RE + SAFE_ANNOTATION_RE + INLINE_SAFE_RE defined  |
| `backend/tests/test_check_migrations.py`                                 | 12 unit tests covering PASS/FAIL/ReDoS/docstring  | VERIFIED  | 12 test functions confirmed; test_fail_safe_in_docstring and test_redos present       |
| `.github/workflows/backend-ci.yml`                                       | DROP guard step before Run tests with coverage    | VERIFIED  | Step "Check migrations for unannotated destructive operations" at index 8; tests at 9 |
| `backend/pytest.ini`                                                     | --cov-fail-under=51 in addopts                   | VERIFIED  | Line present between --cov-report=xml and parallel options comment                    |
| `.github/workflows/frontend-ci.yml`                                      | "Run tests" step with npm test -- --run --coverage | VERIFIED | Step at index 7 (Audit=6, Build=8). Step ordering correct.                           |
| `frontend/vitest.config.ts`                                              | thresholds block (D-06 values)                   | DEFERRED  | Commented-out D-06 values present with deferral note pointing to plan 01-09           |
| `backend/tests/test_openapi_snapshot.py`                                 | Function-scope app import, string equality assert  | VERIFIED  | `from app.main import app` at indented line 39 (inside test function body)            |
| `backend/tests/fixtures/openapi_snapshot.json`                           | 158-path formatted JSON snapshot                  | VERIFIED  | 466,651 bytes, 158 paths, top-level keys: components/info/openapi/paths (sorted)      |
| `backend/tests/fixtures/.gitkeep`                                        | Directory marker                                  | VERIFIED  | File exists                                                                           |
| `backend/requirements.txt`                                               | pytest-recording==0.13.4 in Testing block        | VERIFIED  | Exact line present between pytest-cov and httpx                                       |
| `backend/tests/conftest.py`                                              | vcr_config fixture with 4 scrub categories        | VERIFIED  | def vcr_config with filter_headers, filter_post_data_parameters, filter_query_parameters, record_mode="none" |
| `backend/tests/auth/__init__.py`                                         | Empty package marker                              | VERIFIED  | File exists (0 bytes)                                                                 |
| `backend/tests/cassettes/auth/.gitkeep`                                  | Cassette directory marker                         | VERIFIED  | File exists                                                                           |
| `backend/tests/auth/test_characterization_signup_verify.py`              | Flow 1 test, min 40 lines                         | VERIFIED  | Exists; email_verified is True assertion present; no NotImplementedError stub         |
| `backend/tests/auth/test_characterization_login.py`                      | Flow 2 test, min 40 lines                         | VERIFIED  | Exists; passes                                                                        |
| `backend/tests/auth/test_characterization_2fa_totp.py`                   | Flow 3 test, min 50 lines                         | VERIFIED  | Exists; passes                                                                        |
| `backend/tests/auth/test_characterization_webauthn.py`                   | Flow 4 test with 4 @patch at auth boundary        | VERIFIED  | 2 occurrences each of verify_registration_response and generate_registration_options patches |
| `backend/tests/auth/test_characterization_oauth_signin.py`               | Flow 5 test, @pytest.mark.vcr, skipif guard       | VERIFIED  | @pytest.mark.vcr present; skipif guard present; skips cleanly without cassette        |
| `backend/tests/auth/test_characterization_oauth_link.py`                 | Flow 6 test, @pytest.mark.vcr, skipif guard       | VERIFIED  | @pytest.mark.vcr present; skipif guard present; skips cleanly without cassette        |
| `backend/tests/auth/test_characterization_password_reset.py`             | Flow 7 test, min 50 lines                         | VERIFIED  | Exists; passes                                                                        |
| `backend/tests/test_cassette_secret_audit.py`                            | BANNED_PATTERNS, parametrized, REDACTED check     | VERIFIED  | BANNED_PATTERNS present (5 occurrences); 1 @pytest.mark.parametrize; 12 REDACTED refs |
| `backend/tests/crawlers/fixtures/briantooleyracing/product.html`         | Real archived HTML >5 KB                          | VERIFIED  | 464 KB                                                                                |
| `backend/tests/crawlers/fixtures/briantooleyracing/expected.json`        | Deterministic parse output JSON                   | VERIFIED  | Exists with non-empty name and product_url                                            |
| `backend/tests/crawlers/fixtures/amsperformance/product.html`            | Real archived HTML >5 KB                          | VERIFIED  | 349 KB                                                                                |
| `backend/tests/crawlers/fixtures/amsperformance/expected.json`           | Deterministic parse output JSON                   | VERIFIED  | Exists                                                                                |
| `backend/tests/crawlers/fixtures/subispeed/product.html`                 | Real archived HTML >5 KB                          | VERIFIED  | 2.5 MB                                                                                |
| `backend/tests/crawlers/fixtures/subispeed/expected.json`                | Deterministic parse output JSON                   | VERIFIED  | Exists                                                                                |
| `backend/tests/crawlers/fixtures/texasspeed/product.html`                | Real archived HTML >5 KB                          | VERIFIED  | 924 KB                                                                                |
| `backend/tests/crawlers/fixtures/texasspeed/expected.json`               | Deterministic parse output JSON                   | VERIFIED  | Exists                                                                                |
| `backend/tests/crawlers/fixtures/cobbtuning/product.html`                | Real archived HTML >5 KB                          | VERIFIED  | 241 KB                                                                                |
| `backend/tests/crawlers/fixtures/cobbtuning/expected.json`               | Deterministic parse output JSON                   | VERIFIED  | Exists (price_cents: null — correct, Cobb hydrates price client-side)                 |
| `backend/tests/crawlers/test_characterization_briantooleyracing.py`      | parse_product_page characterization test          | VERIFIED  | Exists; test_parse_product_page_matches_expected passes                               |
| `backend/tests/crawlers/test_characterization_amsperformance.py`         | parse_product_page characterization test          | VERIFIED  | Exists; passes                                                                        |
| `backend/tests/crawlers/test_characterization_subispeed.py`              | parse_product_page characterization test          | VERIFIED  | Exists; passes                                                                        |
| `backend/tests/crawlers/test_characterization_texasspeed.py`             | parse_product_page characterization test          | VERIFIED  | Exists; passes                                                                        |
| `backend/tests/crawlers/test_characterization_cobbtuning.py`             | parse_product_page characterization test          | VERIFIED  | Exists; passes                                                                        |
| `.github/dependabot.yml`                                                 | 3 ecosystems, weekly Monday, no ignore block      | VERIFIED  | version:2; pip+npm+github-actions; npm uses directories:; no ignore: keyword; all Monday |

### Key Link Verification

| From                                              | To                                                       | Via                                              | Status   | Details                                                                          |
|---------------------------------------------------|----------------------------------------------------------|--------------------------------------------------|----------|----------------------------------------------------------------------------------|
| backend/pytest.ini --cov-fail-under               | backend-ci.yml "Run tests with coverage"                 | pytest reads addopts at both local and CI runtime | WIRED    | No extra CI flags needed; addopts applies automatically                          |
| .github/workflows/frontend-ci.yml "Run tests"    | frontend/vitest.config.ts                                | npm test --run --coverage reads vitest config    | WIRED    | CI step confirmed; thresholds commented (deferred to 01-09)                     |
| backend-ci.yml "Check migrations" step            | backend/scripts/check_migrations.py                      | `python backend/scripts/check_migrations.py`     | WIRED    | Step confirmed at correct position; script exits 0 on current tree              |
| backend/scripts/check_migrations.py              | backend/alembic/versions/*.py                             | MIGRATIONS_DIR.glob("*.py")                      | WIRED    | 34 files scanned, all annotated                                                  |
| backend/tests/test_openapi_snapshot.py           | backend/tests/fixtures/openapi_snapshot.json             | Path(__file__).parent / "fixtures" / "openapi_snapshot.json" | WIRED | String equality comparison; test passes |
| backend/tests/test_openapi_snapshot.py           | backend/app/main.py app.openapi()                        | function-scope `from app.main import app`        | WIRED    | Import is at line 39, indented (inside test function body per Pitfall 8)        |
| backend/tests/auth/test_characterization_oauth_signin.py | cassettes (pending)                               | @pytest.mark.vcr + skipif guard                  | PARTIAL  | Guard correctly skips without cassettes; wiring is structural but cassettes absent |
| backend/tests/conftest.py vcr_config             | All @pytest.mark.vcr tests                               | pytest-recording fixture injection               | WIRED    | vcr_config fixture present; filter_headers + record_mode="none" configured      |
| backend/alembic/env.py                            | backend/app/db/base_class.py Base.metadata               | target_metadata = Base.metadata                  | WIRED    | env.py unchanged; naming_convention flows through automatically                  |
| .github/dependabot.yml                           | GitHub Dependabot service                                 | committed to .github/; auto-activated on push    | PARTIAL  | File committed correctly; GitHub activation requires human confirmation          |

### Data-Flow Trace (Level 4)

Not applicable — this phase delivers CI scripts, config files, and characterization tests (no dynamic data-rendering components). All artifacts are either pure Python analysis scripts, config files, or tests that read committed fixture files.

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                                  | Result                           | Status  |
|-------------------------------------------------------|------------------------------------------------------------------------------------------|----------------------------------|---------|
| DROP guard exits 0 on current migration tree          | `python backend/scripts/check_migrations.py`                                            | "OK (34 files scanned)", exit 0  | PASS    |
| Naming convention keys available on Base              | Python: `sorted(Base.metadata.naming_convention.keys())`                                | `['ck', 'fk', 'ix', 'pk', 'uq']` | PASS   |
| Naming convention + DROP guard unit tests pass        | `pytest tests/test_metadata_naming_convention.py tests/test_check_migrations.py -q`    | 14 passed in 0.04s               | PASS    |
| OpenAPI snapshot test passes                          | `pytest tests/test_openapi_snapshot.py --no-cov -q`                                    | 1 passed in 0.34s                | PASS    |
| 5 non-VCR auth characterization tests pass           | `pytest tests/auth/test_characterization_signup_verify.py tests/auth/test_characterization_login.py tests/auth/test_characterization_2fa_totp.py tests/auth/test_characterization_password_reset.py tests/auth/test_characterization_webauthn.py --no-cov -q` | 5 passed in 2.71s | PASS |
| 2 OAuth tests skip cleanly without cassettes          | `pytest tests/auth/test_characterization_oauth_signin.py tests/auth/test_characterization_oauth_link.py --no-cov -q` | 2 skipped in 0.01s | PASS |
| 5 crawler characterization tests pass                 | `pytest tests/crawlers/test_characterization_*.py --no-cov -q`                         | 5 passed in 1.30s                | PASS    |
| Cassette secret audit passes (no cassettes yet)       | `pytest tests/test_cassette_secret_audit.py --no-cov -q`                               | 2 passed, 2 skipped in 0.02s    | PASS    |
| Dependabot YAML is structurally correct               | Python yaml.safe_load assertions on .github/dependabot.yml                              | VERSION:2, 3 ecosystems, no ignore, all Monday | PASS |
| Frontend CI step ordering correct                     | Python yaml parser on frontend-ci.yml                                                    | Audit=6 Run tests=7 Build=8     | PASS    |
| Backend CI DROP guard step ordering correct           | Python yaml parser on backend-ci.yml                                                     | Scan=7 Check migrations=8 Run tests=9 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                      | Status     | Evidence                                                                    |
|-------------|-------------|------------------------------------------------------------------|------------|-----------------------------------------------------------------------------|
| SAFE-01     | 01-04       | Backend pytest.ini enforces --cov-fail-under at measured baseline | SATISFIED  | --cov-fail-under=51 in addopts; measured at 51% (floor of 3 runs)          |
| SAFE-02     | 01-04       | frontend-ci.yml runs npm test -- --run on every PR               | SATISFIED  | "Run tests" step with npm test -- --run --coverage; correct position        |
| SAFE-03     | 01-04       | Vitest config enforces lines:60 coverage threshold               | DEFERRED   | Staged as commented literals; deferred to plan 01-09 (user decision)       |
| SAFE-04     | 01-03       | CI step fails any migration with unannotated drop_* op           | SATISFIED  | check_migrations.py + CI step + 12 unit tests; exits 0 on current tree     |
| SAFE-05     | 01-05       | OpenAPI snapshot test catches schema drift                       | SATISFIED  | test_openapi_snapshot.py passes; 466 KB snapshot with 158 paths committed  |
| SAFE-06     | 01-06       | Auth characterization tests cover 7 happy-path flows             | SATISFIED  | 7 test files; 5 pass; 2 OAuth skip with cassette guard (intentional design) |
| SAFE-07     | 01-07       | Crawler adapter VCR-style tests cover 5 representative adapters  | SATISFIED  | 5 tests pass against real archived HTML (3×tier0 + 2×tier1)                |
| SAFE-08     | 01-02       | Three broken drop_constraint(None) migrations repaired           | SATISFIED  | aa583927d86a forward-only repair; 3 historic files have legacy SAFE annotations |
| SAFE-09     | 01-01       | SQLAlchemy MetaData uses explicit naming_convention              | SATISFIED  | base_class.py has 5-key NAMING_CONVENTION; 2 unit tests pin keys + templates |
| SAFE-10     | 01-08       | Dependabot configured for weekly dependency PRs                  | SATISFIED (local) | .github/dependabot.yml committed with correct structure; GitHub activation pending human check |

Note: REQUIREMENTS.md shows SAFE-05, SAFE-06, SAFE-09 as unchecked `[ ]` — this is documentation staleness. All three are implemented and verified in the codebase.

### Anti-Patterns Found

| File                                        | Line | Pattern                                    | Severity | Impact                                                                                                     |
|---------------------------------------------|------|--------------------------------------------|----------|------------------------------------------------------------------------------------------------------------|
| `backend/pytest.ini`                        | 2    | `testpaths = app/tests` (dir does not exist) | Warning  | WR-01: If backend/app/tests/ is ever created, pytest silently narrows collection to that directory, dropping 2100+ real tests and making CI look green with near-zero coverage. |
| `backend/tests/auth/test_characterization_oauth_signin.py` | 73-75 | `id_token_from_cassette`, `email_from_cassette` are `"<..._FROM_CASSETTE>"` placeholders | Warning | Intentional placeholders documented in SUMMARY; skipif guard prevents them from causing failures. Will be replaced when cassettes recorded. |
| `backend/tests/auth/test_characterization_oauth_link.py` | 66-68 | Same cassette placeholder pattern | Warning | Same as above — intentional, documented. |

No blockers found. The stale `testpaths` (WR-01 from code review) is the highest-impact warning but is not a blocker for phase goal achievement — pytest silently falls back to CWD collection and the full 2154-test suite currently runs.

The OAuth placeholder values are intentional and protected by skipif guards — they do not represent implementation stubs.

### Human Verification Required

**1. Dependabot GitHub-Side Activation**

**Test:** Navigate to GitHub repository → Insights → Dependency graph → Dependabot tab.
**Expected:** Three ecosystems should appear as active (pip, npm, github-actions) with "Next check" showing the upcoming Monday. First PR batch should arrive the Monday after merge.
**Why human:** Dependabot activation is a GitHub-service-side effect of committing `.github/dependabot.yml`. The file structure and YAML validity are confirmed programmatically, but the actual GitHub service pickup cannot be observed from the local repo.

**2. Record Google OAuth Cassettes and Confirm Tests Move from SKIPPED to PASSED**

**Test:** With a Google sandbox account and GOOGLE_CLIENT_ID configured, run:
```bash
cd backend
rm -rf tests/auth/cassettes/test_characterization_oauth_signin
pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_signin.py::test_google_oauth_signin
rm -rf tests/auth/cassettes/test_characterization_oauth_link
pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_link.py::test_google_oauth_link_existing_user
git add tests/auth/cassettes/
git commit -m "test(01-06): add Google OAuth VCR cassettes for flows 5+6"
pytest -n auto tests/auth/test_characterization_oauth_signin.py tests/auth/test_characterization_oauth_link.py -v
```
**Expected:** After cassette commit, both tests report PASSED (not SKIPPED). The `id_token_from_cassette`, `nonce_from_cassette`, and `email_from_cassette` placeholders must be replaced with values from the recorded cassette before committing.
**Why human:** Cassette recording requires a real Google OAuth sandbox account with valid credentials. A SKIPPED result after cassette YAML files are present would indicate the `_CASSETTE` path formula does not match pytest-recording's actual default layout — fix the path computation in each file so `_CASSETTE.exists()` returns True.

### Gaps Summary

No blocking gaps. The phase goal is substantially achieved: all 10 SAFE-XX requirements are either implemented and verified in the codebase (SAFE-01, SAFE-02, SAFE-04 through SAFE-10) or intentionally deferred with tracking (SAFE-03 to plan 01-09).

The human verification items are confirmations of service-side activation (Dependabot) and a post-merge manual step (OAuth cassette recording) that were documented as required from the start. Neither prevents the core safety net function from operating.

The REQUIREMENTS.md `[ ]` checkbox state for SAFE-05, SAFE-06, and SAFE-09 is a documentation staleness issue, not a code gap — all three are implemented and tests pass.

The stale `testpaths = app/tests` in pytest.ini (WR-01 from code review) is a latent correctness hazard but is not currently causing any test collection issues. The full 2154-test suite runs normally. This should be fixed in a follow-up commit (correcting to `testpaths = tests`).

---

_Verified: 2026-04-22T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
