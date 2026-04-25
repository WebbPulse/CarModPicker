---
estimated_steps: 17
estimated_files: 1
skills_used: []
---

# T01: Add `app/crawlers/compliance_audit.py` script-as-test that prints `<n>/<n> compliant` + per-tier breakdown and exits non-zero on miss

Write the audit script first (TDD-style) so the slice has an objective stopping condition: before T02 it fails with 108 non-compliant adapters, after T02 it passes 108/108. The script is the slice's primary demo gate — `python -m app.crawlers.compliance_audit` from `backend/` must be a one-liner anyone can run.

**Module shape:** put `audit() -> int` (returns exit code) and a small `_classify_tier(cls) -> str` helper at module scope so tests in T03 can import them directly without subprocess overhead. The `__main__` block calls `sys.exit(audit())`. `audit()` reads `ADAPTER_REGISTRY` from `app.crawlers.adapters` (importing it triggers the discovery walk), buckets each registered class by `cls.FETCHER_TIER` (`http` → T0, `tls` → T1, `browser` → T2), and for each adapter checks that `cls.category_targets` is a non-empty list/tuple of strings.

**Stdout contract** (consumed by S04 — keep it stable):
```
M002/S03 adapter compliance audit
  T0 (http):    <n0>/<total0> compliant
  T1 (tls):     <n1>/<total1> compliant
  T2 (browser): <n2>/<total2> compliant
  Total:        <n>/<total> compliant
```
When all compliant, append `OK — every adapter declares at least one category_targets entry` and exit 0. When non-compliant, prepend a `Non-compliant adapters:` block listing each offender as `  - <adapter_slug> [<tier>]: declares no category_targets` and exit 1.

**Implementation notes:**
- Do NOT re-validate that each declared slug resolves via `default_registry` — `RetailerCrawlerAdapter.__init_subclass__` already does that at import time; if a bad slug shipped, `ADAPTER_REGISTRY` would be empty/the import would have raised. The audit's job is the binary compliance count.
- Use `getattr(cls, 'category_targets', [])` defensively, then check `isinstance(value, (list, tuple))` and `len(value) >= 1` — exactly the same check `__init_subclass__` will accept.
- Print to stdout (not stderr) so the gate command can pipe-capture cleanly.
- Hardcode the column widths (e.g. `T0 (http):    `) for stable grep-ability.

**Why TDD-shape this task first:** the script becomes the verify command for T02 — running it after the retrofit must print `108/108 compliant`. Writing T02 first would leave us without an objective signal for whether the retrofit is complete.

## Inputs

- ``backend/app/crawlers/adapters/__init__.py` — provides `ADAPTER_REGISTRY` (discovery walk runs at import time)`
- ``backend/app/crawlers/adapters/base.py` — `RetailerCrawlerAdapter.category_targets` ClassVar + `FETCHER_TIER` ClassVar + `__init_subclass__` validation gate`
- ``backend/app/crawlers/specs/__init__.py` — `default_registry` (referenced for context; not directly called)`

## Expected Output

- ``backend/app/crawlers/compliance_audit.py` — runnable module with `audit() -> int` + `_classify_tier(cls) -> str` + `__main__` block; exits 1 today (no adapter declares targets), prints per-tier breakdown to stdout.`

## Verification

cd backend && python -m app.crawlers.compliance_audit; test $? -eq 1 && python -m app.crawlers.compliance_audit | grep -q 'Non-compliant adapters:'
