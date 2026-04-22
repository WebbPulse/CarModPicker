---
phase: 05-structural-router-splits
plan: 02
type: execute
wave: 2
depends_on:
  - 05-01-admin-split
files_modified:
  - backend/requirements.txt
  - backend/app/core/config.py
  - backend/app/api/dependencies/auth.py
  - backend/app/api/endpoints/auth.py
  - backend/tests/test_pyjwt_migration.py
  - backend/tests/test_jwt_algorithm_regression.py
autonomous: true
requirements:
  - AUTH-04
user_setup: []

must_haves:
  truths:
    - "PyJWT==2.12.1 is installed and imported via `import jwt` throughout backend/app/"
    - "Zero `from jose import` statements remain in backend/app/"
    - "Zero `except JWTError` statements remain in backend/app/ (all 7 sites use `except InvalidTokenError`)"
    - "Every `jwt.decode(...)` call in backend/app/ specifies `algorithms=[...]` (CWE-327 hardening)"
    - "`settings.JWT_ALGORITHM` exists as a config field with default `\"HS256\"`"
    - "`ALGORITHM` in backend/app/api/dependencies/auth.py reads from `settings.JWT_ALGORITHM`"
    - "Test `test_pyjwt_migration.py` proves a jose-issued HS256 token decodes identically under PyJWT"
    - "Test `test_jwt_algorithm_regression.py` fails on any future bare `jwt.decode` without `algorithms=[...]`"
    - "Phase 1 auth characterization tests stay green (in-flight tokens work post-swap)"
  artifacts:
    - path: "backend/app/core/config.py"
      provides: "JWT_ALGORITHM setting (default HS256)"
      contains: "JWT_ALGORITHM"
    - path: "backend/app/api/dependencies/auth.py"
      provides: "PyJWT imports + InvalidTokenError + ALGORITHM from settings"
      contains: "from jwt import InvalidTokenError"
    - path: "backend/app/api/endpoints/auth.py"
      provides: "Still-monolithic auth.py with PyJWT imports (split lands in Plan 04)"
      contains: "from jwt import InvalidTokenError"
    - path: "backend/tests/test_pyjwt_migration.py"
      provides: "jose/PyJWT parity proof for HS256 tokens"
    - path: "backend/tests/test_jwt_algorithm_regression.py"
      provides: "Grep guard for bare jwt.decode without algorithms=[] (matches Phase 4 test_session_query_regression.py shape)"
    - path: "backend/requirements.txt"
      provides: "PyJWT==2.12.1 added; python-jose kept for parity test (Risk 6)"
      contains: "PyJWT==2.12.1"
  key_links:
    - from: "backend/app/api/dependencies/auth.py"
      to: "backend/app/core/config.py"
      via: "ALGORITHM = settings.JWT_ALGORITHM"
      pattern: "ALGORITHM\\s*=\\s*settings\\.JWT_ALGORITHM"
    - from: "backend/tests/test_jwt_algorithm_regression.py"
      to: "backend/app/**/*.py"
      via: "Path(app).rglob('*.py') + regex for jwt.decode without algorithms="
      pattern: "jwt\\.decode\\("
---

<objective>
Swap `python-jose[cryptography]==3.5.0` for `PyJWT==2.12.1` in a narrow, focused PR between the admin split (Plan 01) and the auth split (Plan 04). Hoist the HS256 algorithm literal to `settings.JWT_ALGORITHM`, rewrite 7 `JWTError` exception sites to `InvalidTokenError`, add a byte-identity parity test for in-flight tokens, and add a grep regression guard that fails CI on any future bare `jwt.decode` call.

Purpose: Close AUTH-04. Harden against CWE-327 "alg: none" class attacks via D-04's regression grep. Land the library swap before the auth split so the split happens on the modernized library from day one (per D-01 / D-41).

Output: Single PR with requirements.txt swap, config field, 2 import rewrites (dependencies/auth.py + endpoints/auth.py), 7 exception rewrites, ALGORITHM hoist, 2 new test files. Phase 1 auth characterization tests stay green.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/05-structural-router-splits/05-CONTEXT.md
@.planning/phases/05-structural-router-splits/05-RESEARCH.md
@.planning/phases/05-structural-router-splits/05-PATTERNS.md
@.planning/phases/05-structural-router-splits/05-VALIDATION.md
@CLAUDE.md

# Source files being modified
@backend/app/api/dependencies/auth.py
@backend/app/api/endpoints/auth.py
@backend/app/core/config.py
@backend/requirements.txt

# Shape reference for grep test
@backend/tests/test_session_query_regression.py

# Shape reference for parity test
@backend/tests/test_pydantic_v1_regression.py

<interfaces>
<!-- Current (pre-swap) JWT call sites verified via grep in RESEARCH.md Finding 1 -->

From backend/app/api/dependencies/auth.py (VERIFIED — line-exact):
```
Line 7:   from jose import JWTError, jwt            # REPLACE
Line 17:  ALGORITHM = "HS256"                        # REWRITE to settings.JWT_ALGORITHM
Line 73:  jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)   # unchanged syntax
Line 95:  jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])    # unchanged syntax
Line 100: except JWTError:                           # REPLACE → except InvalidTokenError
Line 127: jwt.decode(..., algorithms=[ALGORITHM])    # unchanged syntax
Line 132: except JWTError:                           # REPLACE → except InvalidTokenError
Line 155: jwt.decode(..., algorithms=[ALGORITHM])    # unchanged syntax
Line 160: except JWTError:                           # REPLACE → except InvalidTokenError
```

From backend/app/api/endpoints/auth.py (VERIFIED — line-exact):
```
Line 23:  from jose import JWTError, jwt            # REPLACE
Line 227: jwt.decode(...)                            # must have algorithms=[ALGORITHM] — verify
Line 261: except JWTError:                           # REPLACE → except InvalidTokenError
Line 311: jwt.decode(...)                            # must have algorithms=[ALGORITHM] — verify
Line 332: except JWTError:                           # REPLACE → except InvalidTokenError
Line 514: jwt.decode(...)                            # must have algorithms=[ALGORITHM] — verify
Line 515: except JWTError:                           # REPLACE → except InvalidTokenError
Line 910: jwt.decode(...)                            # must have algorithms=[ALGORITHM] — verify
Line 911: except JWTError as e:                      # REPLACE → except InvalidTokenError as e
```

Total: 2 import-line rewrites + 7 exception-handler rewrites + 1 ALGORITHM hoist + requirements.txt swap.

From backend/app/core/config.py (VERIFIED — existing field convention at line 29/33):
```python
# Current settings reference pattern:
SECRET_KEY: str = Field(default="change-me-in-production", description="...")
ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="...")
# NEW field to add (after ACCESS_TOKEN_EXPIRE_MINUTES_MAX at ~line 36):
JWT_ALGORITHM: str = Field(default="HS256", description="Algorithm used to sign + verify JWTs. Must match on encode and decode.")
```

From backend/requirements.txt (VERIFIED — lines 24-28):
```
# Note: python-jose depends on ecdsa (CVE-2024-23342), but this is not exploitable
# in this codebase as we use HS256 (HMAC) algorithm, not ECDSA-based algorithms.
# The ecdsa maintainers have indicated no plans to fix this vulnerability.
python-jose[cryptography]==3.5.0
```
Target state per Risk 6 (keep python-jose through Phase 5 for parity test):
```
# PyJWT — primary JWT library (AUTH-04, Phase 5 D-06).
PyJWT==2.12.1

# python-jose — KEPT through Phase 5 only for test_pyjwt_migration.py parity assertion.
# Scheduled for removal in Phase 6 dependency cleanup.
# Note: python-jose depends on ecdsa (CVE-2024-23342), not exploitable in HS256-only usage.
python-jose[cryptography]==3.5.0
```

PyJWT API reference (Context7 /jpadilla/pyjwt, verified in RESEARCH.md Finding 1):
```python
import jwt
from jwt import InvalidTokenError   # re-exported from jwt.exceptions (both work)

# Encode — identical signature to jose
jwt.encode(payload_dict, key, algorithm="HS256")  # returns str (PyJWT 2.x)

# Decode — identical signature to jose
jwt.decode(token_str, key, algorithms=["HS256"])  # returns dict

# InvalidTokenError is the broad base of DecodeError, ExpiredSignatureError,
# InvalidSignatureError, ImmatureSignatureError, InvalidAudienceError,
# InvalidIssuerError, InvalidAlgorithmError, MissingRequiredClaimError, InvalidKeyError.
# It covers everything jose.JWTError covered.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add PyJWT to requirements + create JWT_ALGORITHM config field + create parity + grep-guard test files</name>
  <files>
    backend/requirements.txt,
    backend/app/core/config.py,
    backend/tests/test_pyjwt_migration.py,
    backend/tests/test_jwt_algorithm_regression.py
  </files>
  <read_first>
    - backend/requirements.txt (all 28+ lines — see exact current state in `<interfaces>`)
    - backend/app/core/config.py (to find the existing `ACCESS_TOKEN_EXPIRE_MINUTES` field and match its Pydantic Field style)
    - backend/tests/test_session_query_regression.py (EXACT shape to mirror for test_jwt_algorithm_regression.py)
    - backend/tests/test_pydantic_v1_regression.py (role-match reference for test_pyjwt_migration.py)
    - .planning/phases/05-structural-router-splits/05-PATTERNS.md (Sections 14, 15, 18 — test templates + config.py field pattern)
  </read_first>
  <behavior>
    - Test `test_pyjwt_migration.py::test_pyjwt_decodes_jose_hs256_token` PASSES (jose-encoded HS256 token decodes via PyJWT — bit-identical).
    - Test `test_pyjwt_migration.py::test_pyjwt_and_jose_produce_identical_hs256_tokens` PASSES (both libraries produce byte-identical tokens for same payload + key + algorithm="HS256").
    - Test `test_jwt_algorithm_regression.py::test_every_jwt_decode_specifies_algorithms` PASSES before Task 2 migration (current code already has `algorithms=[ALGORITHM]` on every decode per Finding 1).
    - `python -c "from app.core.config import settings; print(settings.JWT_ALGORITHM)"` outputs `HS256`.
    - `pip install -r backend/requirements.txt` succeeds with both PyJWT 2.12.1 and python-jose 3.5.0 installed (Risk 6 — keep both through Phase 5).
  </behavior>
  <action>
**Step A — Update `backend/requirements.txt`** per Risk 6 (keep python-jose through Phase 5).

Replace the existing `python-jose[cryptography]==3.5.0` block with the block shown in the `<interfaces>` "Target state per Risk 6" section. In particular:
1. Add a new line `PyJWT==2.12.1` with a preceding comment `# PyJWT — primary JWT library (AUTH-04, Phase 5 D-06).`
2. Keep the existing `python-jose[cryptography]==3.5.0` line + update its comment to indicate it's transitional (see `<interfaces>` Target state).

After the edit, install the new dependency:
```bash
cd backend
pip install PyJWT==2.12.1
```

**Step B — Add `JWT_ALGORITHM` field to `backend/app/core/config.py`** per D-03 + D-07.

Read config.py to find the existing `ACCESS_TOKEN_EXPIRE_MINUTES_MAX` field (~line 36 per `<interfaces>`). Insert the new field directly AFTER it:
```python
    # JWT algorithm — PyJWT swap (AUTH-04 D-03). HS256 preserved per D-46.
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used to sign + verify JWTs. Must match on encode and decode.",
    )
```

Match the `Field(default=..., description=...)` pattern used by `SECRET_KEY` and `GOOGLE_CLIENT_ID` in the same file (note: some fields such as `ACCESS_TOKEN_EXPIRE_MINUTES` use a plain annotation like `ACCESS_TOKEN_EXPIRE_MINUTES: int = 60` — do NOT mimic that shorter form; use the `Field(...)` wrapper for JWT_ALGORITHM because the `description=` metadata documents the CWE-327 hardening intent). Do NOT reorganize the file.

**Step C — Create `backend/tests/test_pyjwt_migration.py`** per D-05. Verbatim from PATTERNS.md §14:
```python
"""AUTH-04 D-05: HS256 token parity between python-jose (old) and PyJWT (new).

Proves a token issued by the old library decodes identically under the new.
HS256 is deterministic HMAC — byte-compatible across libraries. This test
is the reviewer-visible safety check for the PyJWT swap PR.

Lifetime discretion: keep post-migration as a safeguard against future
library-swap regressions, OR delete alongside python-jose dependency in
Phase 6 cleanup. See CONTEXT.md "Claude's Discretion".
"""

from __future__ import annotations

import jwt as pyjwt
from jose import jwt as jose_jwt


def test_pyjwt_decodes_jose_hs256_token() -> None:
    """Round-trip: jose encode -> PyJWT decode -> payload match."""
    payload = {"sub": "user@example.com", "exp": 9999999999}
    secret = "test-secret-for-parity-check-not-for-production"

    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")
    decoded = pyjwt.decode(jose_token, secret, algorithms=["HS256"])

    assert decoded == payload


def test_pyjwt_and_jose_produce_identical_hs256_tokens() -> None:
    """Byte-identity assertion — both libraries produce the same string for HS256."""
    payload = {"sub": "bob", "exp": 9999999999}
    secret = "test-secret-deterministic"

    pyjwt_token = pyjwt.encode(payload, secret, algorithm="HS256")
    jose_token = jose_jwt.encode(payload, secret, algorithm="HS256")

    assert pyjwt_token == jose_token
```

**Step D — Create `backend/tests/test_jwt_algorithm_regression.py`** per D-04. Verbatim from PATTERNS.md §15:
```python
"""AUTH-04 D-04 regression: every jwt.decode() call MUST specify algorithms=[].

Scoped to backend/app/ per Phase 3/4 precedent (test_session_query_regression.py).
Guards against the CWE-327 / "alg: none" vulnerability class — if a future PR
adds a bare jwt.decode(token, key) call, this test fails at CI.

Companion tests: test_session_query_regression.py, test_pydantic_v1_regression.py,
test_logger_migration_regression.py.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

_DECODE_PATTERN = re.compile(r"\bjwt\.decode\(")
_ALG_PATTERN = re.compile(r"algorithms\s*=\s*\[")


def test_every_jwt_decode_specifies_algorithms() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in APP_DIR.rglob("*.py"):
        lines = pyfile.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _DECODE_PATTERN.search(line):
                # Check same line + next 2 lines (multi-line statements)
                window = "\n".join(lines[lineno - 1:lineno + 2])
                if not _ALG_PATTERN.search(window):
                    offenders.append((str(pyfile.relative_to(APP_DIR)), lineno, line.strip()))
    assert not offenders, (
        "jwt.decode() calls without algorithms=[...] detected (CWE-327 risk):\n"
        + "\n".join(f"  {f}:{ln} -> {code}" for f, ln, code in offenders)
    )
```

After creating the files, run them to verify they pass BEFORE the swap (proving baseline is green):
```bash
cd backend
pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x
```

If `test_pyjwt_migration.py` fails — halt and report. If `test_jwt_algorithm_regression.py` fails — there is already a bare `jwt.decode` somewhere; report it as a pre-existing bug (unexpected per Finding 1 which verified all decode calls have `algorithms=[ALGORITHM]`).
  </action>
  <verify>
    <automated>cd backend && grep -q "^PyJWT==2.12.1$" requirements.txt</automated>
    <automated>cd backend && grep -q "^python-jose\[cryptography\]==3.5.0$" requirements.txt</automated>
    <automated>cd backend && python -c "import jwt; from jwt import InvalidTokenError; print('PyJWT', jwt.__version__); assert jwt.__version__ == '2.12.1'"</automated>
    <automated>cd backend && python -c "from app.core.config import settings; print('JWT_ALGORITHM=', settings.JWT_ALGORITHM); assert settings.JWT_ALGORITHM == 'HS256'"</automated>
    <automated>test -f backend/tests/test_pyjwt_migration.py && test -f backend/tests/test_jwt_algorithm_regression.py</automated>
    <automated>cd backend && pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -q "^PyJWT==2.12.1$" backend/requirements.txt` exits 0
    - `grep -q "^python-jose\[cryptography\]==3.5.0$" backend/requirements.txt` exits 0 (kept per Risk 6)
    - `cd backend && python -c "import jwt; assert jwt.__version__ == '2.12.1'"` exits 0
    - `cd backend && python -c "from jwt import InvalidTokenError; print(InvalidTokenError)"` exits 0
    - `cd backend && python -c "from app.core.config import settings; assert settings.JWT_ALGORITHM == 'HS256'"` exits 0
    - `test -f backend/tests/test_pyjwt_migration.py` exits 0
    - `test -f backend/tests/test_jwt_algorithm_regression.py` exits 0
    - `cd backend && pytest -n auto tests/test_pyjwt_migration.py -x` exits 0 (2 tests pass — parity + byte-identity)
    - `cd backend && pytest -n auto tests/test_jwt_algorithm_regression.py -x` exits 0 (baseline passes BEFORE code migration per Finding 1)
  </acceptance_criteria>
  <done>PyJWT installed alongside python-jose, JWT_ALGORITHM config field exists with default HS256, parity + regression-grep tests created and green against pre-migration code.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Swap jose → PyJWT imports in dependencies/auth.py + endpoints/auth.py + rewrite 7 exception sites + hoist ALGORITHM</name>
  <files>
    backend/app/api/dependencies/auth.py,
    backend/app/api/endpoints/auth.py
  </files>
  <read_first>
    - backend/app/api/dependencies/auth.py (ALL lines — identify lines 7, 17, 95, 100, 127, 132, 155, 160 — exact sites per `<interfaces>`)
    - backend/app/api/endpoints/auth.py (lines 23, 227, 261, 311, 332, 514, 515, 910, 911 — exact sites per `<interfaces>`)
    - .planning/phases/05-structural-router-splits/05-CONTEXT.md §D-02, D-03, D-07 (exception + algorithm literal conventions)
    - .planning/phases/05-structural-router-splits/05-RESEARCH.md Finding 1 (exception hierarchy + migration sites)
  </read_first>
  <behavior>
    - `grep -rn "from jose" backend/app/` returns exit code 1 (zero matches).
    - `grep -rn "except JWTError" backend/app/` returns exit code 1 (zero matches).
    - `grep -rn "JWTError" backend/app/` returns exit code 1 (zero matches anywhere — import + raise + except removed).
    - `grep -n "^ALGORITHM = settings.JWT_ALGORITHM$" backend/app/api/dependencies/auth.py` returns exactly one match.
    - `pytest -n auto backend/tests/test_jwt_algorithm_regression.py -x` passes (still green — all decode calls still have `algorithms=[ALGORITHM]`).
    - `pytest -n auto backend/tests/test_pyjwt_migration.py -x` passes (parity unchanged).
    - Phase 1 auth characterization suite passes (in-flight tokens decode under PyJWT — AUTH-04 hardening verified end-to-end).
    - `from app.main import app` succeeds without ImportError.
  </behavior>
  <action>
**Step A — Modify `backend/app/api/dependencies/auth.py`:**

Make these EXACT line-level edits (all sites verified via RESEARCH.md Finding 1):

1. Line 7 — REPLACE:
   ```python
   from jose import JWTError, jwt
   ```
   WITH:
   ```python
   import jwt
   from jwt import InvalidTokenError
   ```

2. Line 17 — REPLACE:
   ```python
   ALGORITHM = "HS256"
   ```
   WITH:
   ```python
   ALGORITHM = settings.JWT_ALGORITHM
   ```
   (This makes ALGORITHM a module-level reference to the settings field per D-07 — sibling code imports `ALGORITHM` unchanged.)

3. Lines 100, 132, 160 — For EACH occurrence, REPLACE:
   ```python
   except JWTError:
   ```
   WITH:
   ```python
   except InvalidTokenError:
   ```

Verify the encode/decode call-sites (lines 73, 95, 127, 155) still work verbatim — PyJWT's `jwt.encode(payload, key, algorithm=ALGORITHM)` and `jwt.decode(token, key, algorithms=[ALGORITHM])` signatures are identical to jose's. NO changes needed on those lines. Leave them untouched.

**Step B — Modify `backend/app/api/endpoints/auth.py`:**

At Plan 02 time, `endpoints/auth.py` is still monolithic (the auth split lands in Plan 04 after API_CONTRACT lands). Make these EXACT line-level edits:

1. Line 23 — REPLACE:
   ```python
   from jose import JWTError, jwt
   ```
   WITH:
   ```python
   import jwt
   from jwt import InvalidTokenError
   ```

2. Lines 261, 332, 515, 911 — For EACH occurrence, REPLACE:
   - `except JWTError:` → `except InvalidTokenError:`
   - `except JWTError as e:` → `except InvalidTokenError as e:`

Leave all `jwt.decode(...)` and `jwt.encode(...)` call lines (227, 311, 514, 910) UNTOUCHED — they already have `algorithms=[ALGORITHM]` per Finding 1's grep audit. If any decode call lacks `algorithms=[ALGORITHM]`, ADD it before exit (the `test_jwt_algorithm_regression.py` would fail otherwise and catch the miss).

**Step C — Final audit greps** (these MUST return exit code 1 after the migration):
```bash
cd backend
grep -rn "from jose" app/ && exit 1 || echo "jose imports clean"
grep -rn "JWTError" app/ && exit 1 || echo "JWTError refs clean"
grep -rn "except JWTError" app/ && exit 1 || echo "except JWTError clean"
```

**Step D — Run full validation:**
```bash
cd backend
pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x

# Phase 1 auth characterization — 7 happy-path flows MUST stay green per D-43
pytest -n auto -k "auth and characterization" -x

# Sanity: full app imports cleanly
python -c "from app.main import app; print('app routes:', len(app.routes))"
```

If any Phase 1 characterization test fails, halt and investigate Risk 1 (in-flight JWT invalidation). Most likely mitigation: add `leeway=10` to the `jwt.decode` calls in dependencies/auth.py if clock-skew-strict `iat` rejection is the culprit (PyJWT 2.x is stricter than jose on `iat` validation per Risk 1).
  </action>
  <verify>
    <automated>cd backend && grep -rn "from jose" app/ ; test $? -eq 1</automated>
    <automated>cd backend && grep -rn "JWTError" app/ ; test $? -eq 1</automated>
    <automated>cd backend && grep -rn "except JWTError" app/ ; test $? -eq 1</automated>
    <automated>cd backend && grep -q "^ALGORITHM = settings.JWT_ALGORITHM$" app/api/dependencies/auth.py</automated>
    <automated>cd backend && grep -c "^from jwt import InvalidTokenError$" app/api/dependencies/auth.py app/api/endpoints/auth.py | awk -F: '$2!=1 {exit 1}'</automated>
    <automated>cd backend && grep -c "except InvalidTokenError" app/api/dependencies/auth.py ; test "$(grep -c 'except InvalidTokenError' app/api/dependencies/auth.py)" -eq 3</automated>
    <automated>cd backend && grep -c "except InvalidTokenError" app/api/endpoints/auth.py ; test "$(grep -c 'except InvalidTokenError' app/api/endpoints/auth.py)" -eq 4</automated>
    <automated>cd backend && pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x</automated>
    <automated>cd backend && pytest -n auto -k "auth and characterization" -x 2>&1 | tail -30</automated>
    <automated>cd backend && python -c "from app.main import app; print('ok', len(app.routes))"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "from jose" backend/app/` returns exit code 1 (no matches)
    - `grep -rn "JWTError" backend/app/` returns exit code 1 (no matches anywhere — neither import nor except nor raise)
    - `grep -rn "except JWTError" backend/app/` returns exit code 1 (no matches)
    - `grep -q "^ALGORITHM = settings.JWT_ALGORITHM$" backend/app/api/dependencies/auth.py` exits 0
    - `grep -c "^from jwt import InvalidTokenError$" backend/app/api/dependencies/auth.py` outputs `1`
    - `grep -c "^from jwt import InvalidTokenError$" backend/app/api/endpoints/auth.py` outputs `1`
    - `grep -c "except InvalidTokenError" backend/app/api/dependencies/auth.py` outputs `3` (matches the 3 sites per Finding 1)
    - `grep -c "except InvalidTokenError" backend/app/api/endpoints/auth.py` outputs `4` (matches the 4 sites per Finding 1)
    - `cd backend && pytest -n auto tests/test_pyjwt_migration.py -x` exits 0
    - `cd backend && pytest -n auto tests/test_jwt_algorithm_regression.py -x` exits 0 (every decode call still specifies algorithms)
    - `cd backend && pytest -n auto -k "auth and characterization" -x` exits 0 (Phase 1 D-43 guardrail — in-flight tokens work)
    - `cd backend && python -c "from app.main import app"` exits 0 (no import errors)
  </acceptance_criteria>
  <done>Library swapped in-place across 2 files, 7 exception sites rewritten, ALGORITHM hoisted to settings, Phase 1 auth characterization tests stay green, zero `from jose`/`JWTError` references remain in backend/app/.</done>
</task>

</tasks>

<deferred>
## Deferred / documented-only

- **Removing `python-jose` dependency from requirements.txt:** Per Risk 6, python-jose STAYS through Phase 5 to support the parity test import. Removal scheduled for Phase 6 dependency cleanup (per Deferred Ideas list in CONTEXT.md).
- **Deleting `test_pyjwt_migration.py` post-migration:** Claude's Discretion in CONTEXT.md — keep for future library-swap safeguard; revisit in Phase 6.
- **ALGORITHM rotation / RS256 migration:** D-46 preserves HS256. No algorithmic change.
</deferred>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Unauthenticated HTTP → FastAPI token endpoints | `/api/auth/token` issues JWTs; attacker cannot forge without SECRET_KEY |
| Authenticated request → `get_current_user` JWT decode | Bearer token in `Authorization` header; decoded via `jwt.decode` |
| In-flight tokens (issued by jose, decoded by PyJWT) | Single-deploy transition boundary during the swap PR |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-02-01 | Spoofing | Any `jwt.decode(...)` call missing `algorithms=[...]` (CWE-327 / "alg: none" class) | mitigate | Task 1 creates `backend/tests/test_jwt_algorithm_regression.py` (D-04) that fails CI if any `jwt.decode(` in `backend/app/` lacks `algorithms=[` within 3 lines. The regex-based grep test runs on every PR forever. Task 2 maintains the existing `algorithms=[ALGORITHM]` on all 9 decode call sites (verified in Finding 1). |
| T-05-02-02 | Tampering | In-flight tokens (jose-issued) rejected by PyJWT post-deploy → mass user logout | mitigate | Task 1 creates `test_pyjwt_migration.py` (D-05) proving HS256 tokens are byte-identical between jose and PyJWT. Test runs pre-merge. Phase 1 auth characterization suite (D-43) is the end-to-end regression guard — must stay green. If PyJWT's stricter `iat`/`exp` validation becomes an issue (Risk 1), add `leeway=10` to decode calls. |
| T-05-02-03 | Tampering | Algorithm confusion attack via RS256 public key as HMAC secret | accept | HS256-only codebase per D-46; no RSA keys in circulation; no confusion-attack surface. Documented in RESEARCH.md Security Domain. |
| T-05-02-04 | Information Disclosure | `InvalidTokenError` exception message leaks token internals in Sentry | mitigate | PyJWT's `InvalidTokenError` messages are opaque ("Signature verification failed", "Token expired", etc.) — no payload leak. Existing `except InvalidTokenError:` sites re-raise as HTTP 401 without echoing the exception to the client response body. |
| T-05-02-05 | Repudiation | Deleting `python-jose` dep in same PR as adding parity test → ModuleNotFoundError at collection time | mitigate | Risk 6 explicit mitigation: Task 1 KEEPS `python-jose[cryptography]==3.5.0` in requirements.txt. Parity test imports jose successfully. Removal deferred to Phase 6. |
</threat_model>

<verification>
```bash
cd backend
pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x
pytest -n auto -k "auth and characterization" -x  # Phase 1 D-43
pytest -n auto tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x

# Grep audits (MUST return exit 1)
grep -rn "from jose" app/ ; test $? -eq 1
grep -rn "JWTError" app/ ; test $? -eq 1
```
</verification>

<success_criteria>
1. PyJWT 2.12.1 installed; python-jose 3.5.0 kept through Phase 5 per Risk 6.
2. Zero `from jose` or `JWTError` references in `backend/app/`.
3. `settings.JWT_ALGORITHM` exists, default HS256; `ALGORITHM` in dependencies/auth.py reads from it.
4. All 7 `except JWTError` sites rewritten to `except InvalidTokenError` (3 in dependencies/auth.py + 4 in endpoints/auth.py).
5. `test_pyjwt_migration.py` passes (parity + byte-identity).
6. `test_jwt_algorithm_regression.py` passes (zero bare `jwt.decode` in backend/app/).
7. Phase 1 auth characterization tests stay green (in-flight tokens decode under PyJWT).
</success_criteria>

<output>
After completion, create `.planning/phases/05-structural-router-splits/05-02-SUMMARY.md` with:
- Sites migrated: 2 imports + 7 exceptions + 1 ALGORITHM hoist + 1 settings field + 2 new tests
- Parity test result (byte-identical confirmed, satisfies Assumption A2)
- Risk 1 watch items (spike in 401 responses post-deploy — monitor via Sentry)
- Python-jose retention rationale (Risk 6)
- Note that auth.py is still monolithic (split lands in Plan 04)
</output>
