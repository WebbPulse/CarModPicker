---
phase: 06-frontend-cleanup-final-ci-gates
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/eslint.config.js
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/06-LINT-BASELINE.txt
  - frontend/src/test/no-legacy-gradient.test.ts
  - frontend/src/test/no-process-env.test.ts
  - frontend/src/test/extension-content-type.test.ts
  - frontend/src/App.tsx
  - frontend/src/components/common/Button.tsx
  - frontend/src/components/common/Card.tsx
  - frontend/src/components/common/ChromeExtensionPromo.tsx
  - frontend/src/components/common/DangerousActionDialog.tsx
  - frontend/src/components/common/DeleteConfirmationDialog.tsx
  - frontend/src/components/common/Dialog.tsx
  - frontend/src/components/common/SubscriptionPromo.tsx
  - frontend/src/components/layout/globalFooter/Footer.tsx
  - frontend/src/components/layout/globalHeader/Header.tsx
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/About.tsx
  - frontend/src/pages/Checkout.tsx
  - frontend/src/pages/Pricing.tsx
  - frontend/src/pages/Support.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/admin/PartsCuration.tsx
  - .github/workflows/frontend-ci.yml
  - backend/tests/test_bandit_high_gate.py
  - backend/.bandit
  - terraform/s3.tf
autonomous: true
requirements:
  - FE-01
  - FE-02
  - FE-05
  - FE-06
  - QUAL-04
  - QUAL-08
requirements_addressed:
  - FE-01
  - FE-02
  - FE-05
  - FE-06
  - QUAL-04
  - QUAL-08
must_haves:
  truths:
    - "ESLint config rejects no-explicit-any and no-unsafe-* as errors"
    - "A lint baseline file is committed so FE-01 fix scope is visible before Plan 06-02 begins"
    - "No file in frontend/src/**/*.{ts,tsx} contains bg-gradient-to- substring"
    - "No file in frontend/src/**/*.{ts,tsx} contains process.env outside allowlisted paths"
    - "Every chrome-extension POST fetch() call sets Content-Type application/json OR uses a FormData body"
    - "npx madge --circular --extensions ts,tsx src/ runs successfully in frontend CI"
    - "pytest subprocess invocation of bandit against synthetic B602 HIGH fixture exits non-zero"
    - "terraform/s3.tf declares aws_s3_bucket_lifecycle_configuration.crawl_data with DEEP_ARCHIVE at 90 days"
  artifacts:
    - path: "frontend/eslint.config.js"
      provides: "strict typing rule flip and test-file override removal"
      contains: "no-explicit-any"
    - path: "frontend/06-LINT-BASELINE.txt"
      provides: "committed lint audit baseline per D-02"
    - path: "frontend/src/test/no-legacy-gradient.test.ts"
      provides: "FE-05 regression guard"
    - path: "frontend/src/test/no-process-env.test.ts"
      provides: "FE-02 regression guard"
    - path: "frontend/src/test/extension-content-type.test.ts"
      provides: "QUAL-06 Content-Type grep guard"
    - path: "backend/tests/test_bandit_high_gate.py"
      provides: "QUAL-04 regression test"
    - path: "terraform/s3.tf"
      provides: "aws_s3_bucket_lifecycle_configuration.crawl_data resource"
    - path: ".github/workflows/frontend-ci.yml"
      provides: "madge CI step"
    - path: "frontend/package.json"
      provides: "madge devDependency"
  key_links:
    - from: ".github/workflows/frontend-ci.yml"
      to: "madge CLI"
      via: "npx madge --circular --extensions ts,tsx src/"
      pattern: "madge --circular"
    - from: "frontend/src/test/no-legacy-gradient.test.ts"
      to: "frontend/src/**/*.{ts,tsx}"
      via: "globSync filesystem scan"
      pattern: "bg-gradient-to-"
    - from: "backend/tests/test_bandit_high_gate.py"
      to: "bandit CLI"
      via: "subprocess.run with -ll flag"
      pattern: "Severity: High"
    - from: "terraform/s3.tf"
      to: "aws_s3_bucket.crawl_data"
      via: "bucket = aws_s3_bucket.crawl_data.id"
      pattern: "DEEP_ARCHIVE"
---

<objective>
Wave 1 lands all parallel-safe infrastructure that unblocks later waves: ESLint rule flip plus lint baseline capture (FE-01 scope visibility), three vitest grep-guards (FE-02/FE-05/QUAL-06), Tailwind v3 to v4 gradient codemod across all 44+ sites (FE-05), madge devDependency plus CI step (FE-06), bandit HIGH regression test (QUAL-04), and the Terraform Glacier lifecycle rule (QUAL-08).

Purpose: Every Wave 1 task is independent of the others (disjoint file sets or append-only edits). Landing them together gives Wave 2 a green CI surface to build on.
Output: Baseline artifact file, 4 new test files, 1 new Terraform resource, 1 new CI step, 1 new devDependency, all gradient class names renamed.

**Scope rationale (WARNING #B):** This plan has 4 tasks covering 7 requirement surfaces (FE-01 config, FE-02 guard, FE-05 codemod, FE-06 madge, QUAL-04 bandit, QUAL-06 ext-type, QUAL-08 Terraform). Per D-02's chunked-commit model, each task commits independently — reviewer can bisect at task granularity. Tasks 1-3 are all frontend-CI-infra (touch frontend/ + .github/); Task 4 is backend+Terraform (touch backend/ + terraform/). Splitting Task 4 into separate QUAL-04-only + QUAL-08-only tasks was considered but rejected because (a) both are Wave 1 parallel-safe low-risk commits, (b) they share the "final CI gates" theme in the phase goal, and (c) splitting would add a 5th task with negligible quality benefit. Keeping as 4 tasks is per-D-02 intentional.
</objective>

<execution_context>
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/workflows/execute-plan.md
@/home/tyler-webb/Documents/Github/CarModPicker/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/06-frontend-cleanup-final-ci-gates/06-CONTEXT.md
@.planning/phases/06-frontend-cleanup-final-ci-gates/06-RESEARCH.md
@.planning/phases/06-frontend-cleanup-final-ci-gates/06-PATTERNS.md
@.planning/phases/06-frontend-cleanup-final-ci-gates/06-VALIDATION.md
@frontend/eslint.config.js
@frontend/src/App.tsx
@backend/tests/test_pydantic_v1_regression.py
@backend/tests/test_check_migrations.py
@terraform/s3.tf
@.github/workflows/frontend-ci.yml

<interfaces>
Existing grep-guard analog (backend) at backend/tests/test_pydantic_v1_regression.py lines 49-74: iterates all .py files, checks each line against regex list, collects (file, lineno, label) offenders into a list, asserts the list is empty.

Existing vitest scaffolding at frontend/src/test/setup.ts (jsdom config). Vitest 3.2.4 with @testing-library/react 16.1.0 per VALIDATION.md.

Existing subprocess pytest analog at backend/tests/test_check_migrations.py (imports, subprocess.run with capture_output, exit code assertion). tmp_path fixture is xdist-per-worker-safe.

Sentry/existing ErrorBoundary at frontend/src/components/common/ErrorBoundary.tsx (reference only for dark theme Tailwind class conventions).

Current frontend-ci.yml step order (line numbers) from head -65 output:
  L16 Set up Node.js
  L23 Install dependencies
  L28 Check code formatting
  L33 Run linting
  L38 Run type checking
  L43 Audit dependencies
  L48 Run tests
  L53 Build application
Insert Check circular imports step between L48 and L53.

Current terraform/s3.tf contains at line 20: resource "aws_s3_bucket" "crawl_data" and at line 24: resource "aws_s3_bucket_public_access_block" "crawl_data". Append the lifecycle rule immediately after the public_access_block resource (around line 31).

Current frontend/eslint.config.js line 29 starts the main app block `files: ['src/**/*.ts', 'src/**/*.tsx']`. Lines 63-80 contain the test-file override with no-unsafe-* set to off.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Flip ESLint strict rules and capture lint baseline (FE-01 per D-01 D-02 D-05)</name>
  <read_first>
    - frontend/eslint.config.js (full file, 81 lines)
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-RESEARCH.md search for "Example 7" (Fresh ESLint Config)
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-PATTERNS.md Wave 0 section for frontend/eslint.config.js
  </read_first>
  <behavior>
    - After edit: `cd frontend && npm run lint` MAY exit non-zero (baseline captures all violations). That is expected for THIS task; Plan 06-02 fixes them.
    - `@typescript-eslint/no-explicit-any: 'error'` is present in the main app rules block
    - All 5 no-unsafe rules (`no-unsafe-assignment/-call/-return/-member-access/-argument`) are `'error'` in main app rules block
    - The test-file override block (lines 63-80) that turned off no-unsafe rules is DELETED entirely
    - `frontend/06-LINT-BASELINE.txt` exists and contains the captured lint output from `npm run lint`
  </behavior>
  <action>
Edit `frontend/eslint.config.js`:

STEP 1 — In the main application block (the object with `files: ['src/**/*.ts', 'src/**/*.tsx']`, currently starting at line 29), APPEND these rules to the `rules:` object (keep all existing react-refresh/react-hooks/react-x/react-dom rules):

```js
'@typescript-eslint/no-explicit-any': 'error',
'@typescript-eslint/no-unsafe-assignment': 'error',
'@typescript-eslint/no-unsafe-call': 'error',
'@typescript-eslint/no-unsafe-return': 'error',
'@typescript-eslint/no-unsafe-member-access': 'error',
'@typescript-eslint/no-unsafe-argument': 'error',
```

STEP 2 — DELETE the entire test-file override block (currently lines 63-80 — the object with `files: ['src/test/**/*.ts', 'src/test/**/*.tsx']` that sets no-unsafe-* to 'off'). After deletion, `src/test/**` falls through to the main `src/**/*.ts, src/**/*.tsx` block per D-05.

STEP 3 — Capture the lint baseline (per D-02):

```bash
cd frontend
npm run lint 2>&1 | tee 06-LINT-BASELINE.txt || true   # "|| true" so commit still runs when lint exits non-zero
```

Do NOT fix the lint violations in this task — that is Plan 06-02's responsibility. This task only flips the rules and captures scope.

Rationale per D-01: the scout found only 1 explicit `any` in source (`frontend/src/utils/lazyWithReload.ts:23`), but no-unsafe-* will likely surface more violations once test files also run strict rules (D-05). The baseline file makes that scope visible before Plan 06-02 chunks the fixes.
  </action>
  <verify>
    <automated>grep -q "no-explicit-any': 'error'" frontend/eslint.config.js &amp;&amp; grep -q "no-unsafe-assignment': 'error'" frontend/eslint.config.js &amp;&amp; ! grep -q "no-unsafe-assignment': 'off'" frontend/eslint.config.js &amp;&amp; test -s frontend/06-LINT-BASELINE.txt</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "no-unsafe-" frontend/eslint.config.js` returns at least 5
    - `grep -c "': 'off'" frontend/eslint.config.js` returns 0 (no unsafe-* overrides remain)
    - `test -s frontend/06-LINT-BASELINE.txt` exits 0 (file exists and is non-empty)
  </acceptance_criteria>
  <done>ESLint strict rules flipped to error; test-file override block deleted; `frontend/06-LINT-BASELINE.txt` committed as scope-visibility artifact.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create 3 vitest grep-guards, install madge, add CI step (FE-02 + FE-05 prereq + FE-06 + QUAL-06)</name>
  <read_first>
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-PATTERNS.md Wave 0 sections for no-legacy-gradient, no-process-env, extension-content-type
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-RESEARCH.md Pattern 4 (CI Grep Guard), Example 6 (madge CI step), Pitfall 3 (madge and tsconfig paths)
    - frontend/src/test/setup.ts (existing vitest scaffolding)
    - .github/workflows/frontend-ci.yml (6-space indent required for `- name:`)
    - backend/tests/test_pydantic_v1_regression.py (canonical grep-guard shape)
  </read_first>
  <behavior>
    - `frontend/src/test/no-legacy-gradient.test.ts`: runs via vitest; currently FAILS because 44+ `bg-gradient-to-` sites exist; after Task 3 it PASSES
    - `frontend/src/test/no-process-env.test.ts`: runs via vitest and PASSES on current source (allowlist covers src/lib/sentry.ts docstring)
    - `frontend/src/test/extension-content-type.test.ts`: runs via vitest and PASSES on current source (apiRequest helper at chrome-extension/src/background.ts:81-96 already sets Content-Type)
    - `frontend/package.json` has `"madge": "^8.0.0"` in devDependencies
    - `frontend/package-lock.json` updated by `npm install`
    - `.github/workflows/frontend-ci.yml` has a Check circular imports step between Run tests (L48-51) and Build application (L53-56)
    - `cd frontend && npx madge --circular --extensions ts,tsx src/` exits 0 (no circular imports currently)
  </behavior>
  <action>
PART A — Create `frontend/src/test/no-legacy-gradient.test.ts`:

```typescript
import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('FE-05: no bg-gradient-to-* class names in source (Tailwind v3 legacy)', () => {
  it('no file contains bg-gradient-to-', () => {
    const srcDir = resolve(__dirname, '..', '..');
    const files = globSync('src/**/*.{ts,tsx}', { cwd: srcDir, absolute: true });
    const allowlist = new Set([
      resolve(__dirname, 'no-legacy-gradient.test.ts'),
    ]);
    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (/bg-gradient-to-/.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
```

PART B — Create `frontend/src/test/no-process-env.test.ts`:

```typescript
import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('FE-02: no process.env in frontend browser source (use import.meta.env.VITE_*)', () => {
  it('no non-allowlisted src file contains process.env', () => {
    const srcDir = resolve(__dirname, '..', '..');
    const files = globSync('src/**/*.{ts,tsx}', { cwd: srcDir, absolute: true });
    const allowlist = new Set([
      resolve(srcDir, 'src/lib/sentry.ts'),            // docstring-only mention of process.env.CI
      resolve(__dirname, 'no-process-env.test.ts'),    // this guard itself
    ]);
    const violations: Array<{ file: string; line: number; match: string }> = [];
    for (const file of files) {
      if (allowlist.has(file)) continue;
      const lines = readFileSync(file, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (/\bprocess\.env\b/.test(line)) {
          violations.push({ file, line: i + 1, match: line.trim() });
        }
      });
    }
    expect(violations).toEqual([]);
  });
});
```

PART C — Create `frontend/src/test/extension-content-type.test.ts`:

```typescript
import { readFileSync } from 'fs';
import { globSync } from 'glob';
import { describe, expect, it } from 'vitest';
import { resolve } from 'path';

describe('QUAL-06: Chrome extension POST Content-Type compliance (FastAPI 0.132+ strict)', () => {
  it('every fetch POST sets application/json Content-Type or uses FormData', () => {
    const extDir = resolve(__dirname, '..', '..', '..', 'chrome-extension');
    const files = globSync('src/**/*.ts', { cwd: extDir, absolute: true });
    const postRegex = /fetch\([^)]+\{[^}]*method:\s*["']POST["'][^}]*\}/gs;
    const violations: string[] = [];
    for (const file of files) {
      const src = readFileSync(file, 'utf8');
      const matches = src.match(postRegex) ?? [];
      for (const match of matches) {
        const hasJsonHeader = /["']Content-Type["']\s*:\s*["']application\/json["']/.test(match);
        const hasFormData = /body:\s*(formData|\w*FormData)/i.test(match);
        if (!hasJsonHeader && !hasFormData) {
          violations.push(`${file}: ${match.slice(0, 140)}`);
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
```

PART D — Add madge to `frontend/package.json`. Under `devDependencies` (preserving alphabetical ordering), add:

```json
"madge": "^8.0.0"
```

Then:
```bash
cd frontend && npm install
```

(This regenerates `package-lock.json`.)

PART E — Insert Check circular imports step into `.github/workflows/frontend-ci.yml` between the existing Run tests step (ending ~L51) and Build application (starting ~L53). Use EXACT 6-space indentation matching sibling steps:

```yaml
      - name: Check circular imports
        run: |
          cd frontend
          npx madge --circular --extensions ts,tsx src/
```

PART F — Verify locally:

```bash
cd frontend
npm test -- --run src/test/no-process-env.test.ts         # expect PASS
npm test -- --run src/test/extension-content-type.test.ts # expect PASS
npm test -- --run src/test/no-legacy-gradient.test.ts     # expect FAIL; Task 3 makes it pass
npx madge --circular --extensions ts,tsx src/             # expect exit 0
```

The `no-legacy-gradient` failure is expected in THIS task — Task 3 runs the codemod that makes it pass.
  </action>
  <verify>
    <automated>cd frontend &amp;&amp; npm test -- --run src/test/no-process-env.test.ts src/test/extension-content-type.test.ts &amp;&amp; npx madge --circular --extensions ts,tsx src/ &amp;&amp; grep -q '"madge":' package.json &amp;&amp; grep -q "Check circular imports" ../.github/workflows/frontend-ci.yml</automated>
  </verify>
  <acceptance_criteria>
    - `test -f frontend/src/test/no-legacy-gradient.test.ts` exits 0
    - `test -f frontend/src/test/no-process-env.test.ts` exits 0
    - `test -f frontend/src/test/extension-content-type.test.ts` exits 0
    - `grep -q '"madge":' frontend/package.json` succeeds
    - `grep -c "Check circular imports" .github/workflows/frontend-ci.yml` returns 1
    - `grep -c "npx madge --circular --extensions ts,tsx src/" .github/workflows/frontend-ci.yml` returns 1
    - `cd frontend && npm test -- --run src/test/no-process-env.test.ts` exits 0
    - `cd frontend && npm test -- --run src/test/extension-content-type.test.ts` exits 0
    - `cd frontend && npx madge --circular --extensions ts,tsx src/` exits 0
  </acceptance_criteria>
  <done>Three vitest grep-guards created; madge installed as `^8.0.0` devDependency; Check circular imports CI step inserted between Run tests and Build application.</done>
</task>

<task type="auto">
  <name>Task 3: Tailwind v3→v4 gradient codemod across 44+ sites (FE-05 D-15)</name>
  <read_first>
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-RESEARCH.md Pitfall 2 rename table (all 8 directional variants)
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-PATTERNS.md Wave 1 Frontend Tailwind gradient rename section
    - Output of: grep -rn "bg-gradient-to-" frontend/src/ --include="*.ts" --include="*.tsx"
  </read_first>
  <behavior>
    - Zero occurrences of `bg-gradient-to-` remain in `frontend/src/**/*.{ts,tsx}`
    - Every renamed site uses `bg-linear-to-<suffix>` with the SAME direction suffix (t, tr, r, br, b, bl, l, tl) as the original
    - `from-*`, `via-*`, `to-*` color stops remain UNCHANGED
    - The grep-guard `no-legacy-gradient.test.ts` now passes
    - `npm run type-check` still green (Tailwind v4 accepts the new class names — verified in RESEARCH §Pitfall 2)
  </behavior>
  <action>
The rename is a literal string substitution with unambiguous prefix-only target (per Pitfall 2 rename table):

| Find | Replace |
|---|---|
| `bg-gradient-to-t`, `bg-gradient-to-tr`, `bg-gradient-to-r`, `bg-gradient-to-br`, `bg-gradient-to-b`, `bg-gradient-to-bl`, `bg-gradient-to-l`, `bg-gradient-to-tl` | prefix `bg-gradient-to-` → `bg-linear-to-` (direction suffix untouched) |

Single codemod command (replaces the exact substring `bg-gradient-to-` with `bg-linear-to-` everywhere):

```bash
cd frontend
grep -rln "bg-gradient-to-" src/ --include="*.ts" --include="*.tsx" | \
  xargs sed -i 's/bg-gradient-to-/bg-linear-to-/g'
```

Affected files (verified present via grep at planning time):
- frontend/src/App.tsx (4 sites: L133, L149, L151, L155)
- frontend/src/components/common/Button.tsx
- frontend/src/components/common/Card.tsx
- frontend/src/components/common/ChromeExtensionPromo.tsx
- frontend/src/components/common/DangerousActionDialog.tsx
- frontend/src/components/common/DeleteConfirmationDialog.tsx
- frontend/src/components/common/Dialog.tsx
- frontend/src/components/common/SubscriptionPromo.tsx
- frontend/src/components/layout/globalFooter/Footer.tsx
- frontend/src/components/layout/globalHeader/Header.tsx
- frontend/src/pages/Home.tsx
- frontend/src/pages/About.tsx
- frontend/src/pages/Checkout.tsx
- frontend/src/pages/Pricing.tsx
- frontend/src/pages/Support.tsx
- frontend/src/pages/authentication/ExtensionAuth.tsx
- frontend/src/pages/authentication/Login.tsx
- frontend/src/pages/authentication/Register.tsx
- frontend/src/pages/admin/SystemAdmin.tsx
- frontend/src/pages/admin/PartsCuration.tsx

Post-codemod validation:

```bash
cd frontend
grep -rn "bg-gradient-to-" src/ --include="*.ts" --include="*.tsx"   # must return zero lines
npm test -- --run src/test/no-legacy-gradient.test.ts               # must PASS
npm run type-check                                                   # must exit 0
```

DO NOT modify CSS files. DO NOT rename `from-*`/`via-*`/`to-*` color stops. DO NOT touch non-`.ts`/`.tsx` files.
  </action>
  <verify>
    <automated>! grep -rn "bg-gradient-to-" frontend/src/ --include="*.ts" --include="*.tsx" &amp;&amp; cd frontend &amp;&amp; npm test -- --run src/test/no-legacy-gradient.test.ts &amp;&amp; npm run type-check</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "bg-gradient-to-" frontend/src/ --include="*.ts" --include="*.tsx" | wc -l` returns 0
    - `grep -rcn "bg-linear-to-" frontend/src/ --include="*.ts" --include="*.tsx" | awk -F: '{s+=$2} END {print s}'` returns at least 44
    - `cd frontend && npm test -- --run src/test/no-legacy-gradient.test.ts` exits 0
    - `cd frontend && npm run type-check` exits 0
  </acceptance_criteria>
  <done>All bg-gradient-to-* usages replaced with bg-linear-to-*; FE-05 grep-guard passes; type-check green.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: QUAL-04 bandit HIGH regression test + QUAL-08 Terraform Glacier lifecycle rule (D-18 path A + D-19)</name>
  <read_first>
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-RESEARCH.md Example 4 (bandit fixture), Example 5 (Terraform), Pitfall 4 (empty filter)
    - .planning/phases/06-frontend-cleanup-final-ci-gates/06-PATTERNS.md Wave 0 test_bandit_high_gate.py + Wave 1 terraform/s3.tf sections
    - backend/tests/test_check_migrations.py (subprocess fixture pattern; xdist-safe tmp_path usage)
    - terraform/s3.tf lines 20-31 (existing crawl_data resources)
    - backend/.bandit (existing file; add documenting comment at top)
  </read_first>
  <behavior>
    - `backend/tests/test_bandit_high_gate.py`: pytest test writes a synthetic `subprocess.call(user_input, shell=True)` fixture into `tmp_path`, invokes `python -m bandit -r <fixture> -ll`, asserts exit code != 0 AND stdout contains `Severity: High`. xdist-safe (tmp_path is per-worker).
    - `backend/.bandit`: a new comment block documents the QUAL-04 regression test and forbids weakening `-ll` without updating the test.
    - `terraform/s3.tf`: a new `resource "aws_s3_bucket_lifecycle_configuration" "crawl_data"` exists with empty `filter {}` and a single `transition { days = 90; storage_class = "DEEP_ARCHIVE" }`.
    - `terraform validate` passes; `terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data` (operator-side, per D-20) shows 1 resource to create.
  </behavior>
  <action>
PART A — Create `backend/tests/test_bandit_high_gate.py` verbatim from RESEARCH §Example 4:

```python
"""QUAL-04: bandit HIGH-severity regression test.

Pins the current CI invocation (`bandit -r app -ll`) from silently regressing
to a config that would pass HIGH findings through. Uses a synthetic B602 fixture.

D-18 path A applies: current `-ll` flag empirically exits 1 on HIGH (verified
2026-04-23 on bandit 1.9.4). This test guards that behavior; no CI flag change
was made.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def high_severity_fixture(tmp_path: Path) -> Path:
    """Synthetic file with a bandit B602 HIGH-severity finding."""
    src = tmp_path / "fixture.py"
    src.write_text(
        "import subprocess\n"
        "import os\n"
        "user_input = os.environ.get('CMD', '')\n"
        "subprocess.call(user_input, shell=True)  # B602 HIGH\n"
    )
    return src


def test_bandit_fails_on_high_severity(high_severity_fixture: Path) -> None:
    """`bandit -r <fixture> -ll` MUST exit non-zero on a HIGH-severity finding."""
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", str(high_severity_fixture), "-ll"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        f"bandit -ll unexpectedly exited 0 on HIGH fixture. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Severity: High" in result.stdout, (
        f"Expected 'Severity: High' in bandit output, got: {result.stdout!r}"
    )
```

PART B — Read `backend/.bandit`, then prepend this comment block (above any `[bandit]` section header — INI parsers tolerate leading comment lines):

```
# QUAL-04 / D-18 path A (Phase 6): the CI invocation `bandit -r app -ll`
# intentionally fails on MEDIUM and HIGH. backend/tests/test_bandit_high_gate.py
# pins this behavior against regression. Empirical verification 2026-04-23:
# `-ll` exits 1 on B602 HIGH fixture. Do NOT weaken this flag without also
# updating the regression test.
```

PART C — Append Terraform lifecycle rule to `terraform/s3.tf`. Insert AFTER the existing `aws_s3_bucket_public_access_block "crawl_data"` resource (ends around line 31), BEFORE any following resource/comment:

```hcl
# QUAL-08 (Phase 6): transition crawl-data HTML snapshots to Glacier Deep Archive
# after 90 days. D-19 restricts this rule to crawl-data ONLY; user-images stays
# hot (latency-sensitive serve path).
# NOTE: empty `filter {}` = apply to all objects. Do NOT use `filter { prefix = "" }`
# per RESEARCH §Pitfall 4 (generates wrong AWS XML, transition fails to fire).
resource "aws_s3_bucket_lifecycle_configuration" "crawl_data" {
  bucket = aws_s3_bucket.crawl_data.id

  rule {
    id     = "archive-old-snapshots"
    status = "Enabled"

    filter {}

    transition {
      days          = 90
      storage_class = "DEEP_ARCHIVE"
    }
  }
}
```

PART D — Run backend test:

```bash
cd backend
pytest -n auto -x tests/test_bandit_high_gate.py
```

PART E — (Operator-side, per D-20) Run `terraform validate` and capture plan output into PR description:

```bash
cd terraform
terraform validate
terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data -no-color
```

`terraform apply` is NOT part of this task — operator-gated per VALIDATION.md Manual-Only Verifications.

Constraints: do NOT modify `aws_s3_bucket "crawl_data"` or `aws_s3_bucket_public_access_block "crawl_data"` declarations. Do NOT touch `aws_s3_bucket "user_images"` (explicitly excluded by D-19).
  </action>
  <verify>
    <automated>cd backend &amp;&amp; pytest -n auto -x tests/test_bandit_high_gate.py &amp;&amp; grep -q 'aws_s3_bucket_lifecycle_configuration" "crawl_data"' ../terraform/s3.tf &amp;&amp; grep -q 'storage_class = "DEEP_ARCHIVE"' ../terraform/s3.tf</automated>
  </verify>
  <acceptance_criteria>
    - `test -f backend/tests/test_bandit_high_gate.py` exits 0
    - `cd backend && pytest -n auto -x tests/test_bandit_high_gate.py` exits 0
    - `grep -q "QUAL-04" backend/.bandit` exits 0
    - `grep -q 'aws_s3_bucket_lifecycle_configuration" "crawl_data"' terraform/s3.tf` exits 0
    - `grep -q 'storage_class = "DEEP_ARCHIVE"' terraform/s3.tf` exits 0
    - `grep -q 'days          = 90' terraform/s3.tf` exits 0
    - `grep -c 'filter { prefix' terraform/s3.tf` returns 0 (Pitfall 4 avoided)
    - `grep -q 'aws_s3_bucket "user_images"' terraform/s3.tf` succeeds only via the EXISTING user_images declaration (no new lifecycle rule added for it — D-19)
  </acceptance_criteria>
  <done>test_bandit_high_gate.py added and green; .bandit documented; terraform/s3.tf has crawl_data lifecycle rule with DEEP_ARCHIVE @ 90d using empty filter block.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| CI → source tree | Wave 0 installs trust gates (bandit, eslint, madge). Any bypass/weakening of these gates is a supply-chain risk. |
| Chrome extension → FastAPI | QUAL-06 grep guard locks the Content-Type invariant ahead of PR-A's FastAPI 0.136 upgrade. |
| Terraform state → AWS S3 | QUAL-08 lifecycle rule changes object transition policy on `carmodpicker-production-crawl-data`. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-01 | Tampering | frontend/eslint.config.js | mitigate | Commit the strictened rules + baseline artifact together so rule-flip is atomic and auditable via git log. |
| T-06-02 | Elevation | bandit CI gate | mitigate | test_bandit_high_gate.py (subprocess on synthetic B602 HIGH fixture) asserts exit code != 0. Prevents silent weakening of `-ll` flag. |
| T-06-03 | Tampering | chrome-extension POST requests | mitigate | extension-content-type.test.ts grep-guard fails CI on any future `fetch(...POST...)` missing Content-Type or FormData body. Addresses FastAPI 0.132+ strict mode risk. |
| T-06-04 | Information Disclosure | carmodpicker-production-crawl-data S3 bucket | accept | Bucket is ALREADY private via existing aws_s3_bucket_public_access_block.crawl_data. Lifecycle transition to DEEP_ARCHIVE does not change ACL; per RESEARCH §Runtime State Inventory the object ACL is unchanged. Risk: objects-in-transition cost accounting (mitigate via AWS cost alert — not phase scope). |
| T-06-05 | Denial of Service | legacy bg-gradient-to-* class names | accept | Tailwind v4.1.7 compat theme renders both old and new class names to the same CSS (RESEARCH §Pitfall 2). Rename is cosmetic/preventive; rollback cost is trivial. |
| T-06-06 | Spoofing | process.env leak in browser source | mitigate | no-process-env.test.ts grep-guard prevents accidental Node-only env-var usage in browser code (would leak build-time secrets). |
</threat_model>

<verification>
Before merging Plan 06-01:
1. `cd frontend && npm test -- --run src/test/no-process-env.test.ts src/test/extension-content-type.test.ts src/test/no-legacy-gradient.test.ts` — all 3 green
2. `cd frontend && npx madge --circular --extensions ts,tsx src/` — exit 0
3. `cd frontend && npm run type-check` — exit 0
4. `cd backend && pytest -n auto -x tests/test_bandit_high_gate.py` — exit 0
5. `grep -rn "bg-gradient-to-" frontend/src/ --include="*.ts" --include="*.tsx"` — empty output
6. `test -s frontend/06-LINT-BASELINE.txt` — non-empty baseline committed
7. Operator: `terraform validate` green in `terraform/` workspace; `terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data` output pasted into PR description (per D-20)

CI job runs: frontend-ci.yml now includes Check circular imports step between Run tests and Build application.

## Notes on Merge Ordering (WARNING #A)

Plan 06-01 flips ESLint rules to `error` but does NOT fix existing violations; Plan 06-02 owns the fix sweep. To avoid a red-CI window on `main`:

- **REQUIRED:** Plan 06-01 and Plan 06-02 MUST co-merge — either as stacked PRs merged back-to-back, or as a single merge commit. OR Plan 06-02 must land on `main` before Plan 06-01's `eslint.config.js` change hits CI enforcement.
- If the two plans land in separate PRs with Plan 06-02 AFTER Plan 06-01 hits main, `main` will have a red `npm run lint` step between the two merges. Do NOT allow that window.
- The frontend-ci.yml workflow's `Run linting` step is the observable signal — it goes red at the moment Plan 06-01 merges and stays red until Plan 06-02's typing fixes land.

This is an intentional scope split (per D-01/D-02 chunked-commit model); the ordering constraint is a merge-time operational note, not a plan-content defect.
</verification>

<success_criteria>
- FE-01 config enablement committed (lint baseline captured for Plan 06-02 consumption)
- FE-02 guard passes on current source (zero violations)
- FE-05 gradient codemod complete + guard passes (zero `bg-gradient-to-` remain)
- FE-06 madge installed + CI step active + zero circular imports currently
- QUAL-04 regression test green; `.bandit` documented
- QUAL-08 Terraform resource added with empty `filter {}` + DEEP_ARCHIVE @ 90d on crawl_data bucket ONLY
- All acceptance_criteria on all 4 tasks pass
</success_criteria>

<output>
After completion, create `.planning/phases/06-frontend-cleanup-final-ci-gates/06-01-SUMMARY.md` per template.
</output>
