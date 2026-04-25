---
estimated_steps: 34
estimated_files: 4
skills_used: []
---

# T02: Retrofit `category_targets` ClassVar onto all 108 adapter modules (specialists get concrete slug + universal; everyone else gets `["universal"]`)

Apply the canonical mapping to every adapter file under `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/`. The retrofit is mechanical but must be auditable, so do it via a tracked one-shot helper script under `backend/scripts/m002_s03_apply_category_targets.py` that owns the mapping; run the script, then commit the script *and* the resulting adapter edits in this task. The helper stays in the repo as evidence (and so the mapping is reviewable in one place rather than spread across 108 diffs).

**Canonical category_targets mapping** (every entry must already be a registered slug — `coilover`, `brake`, `turbo`, or `universal`; nothing else exists in `default_registry` today):

*Brake specialists* (declare `["brake", "universal"]`):
- `girodisc` (tier0) — two-piece track rotor specialist
- `essexparts` (tier0) — AP Racing distributor (BBKs/pads/rotors/fluid)
- `wilwood` (tier0) — first-party brake manufacturer (calipers/rotors/pads/master cylinders)
- `stoptech` (tier0) — stub adapter, brake sub-brand

*Coilover specialists* (declare `["coilover", "universal"]`):
- `bcracing` (tier0) — first-party coilover manufacturer
- `tein` (tier0) — Japanese coilover/damper house brand
- `stanceusa` (tier0) — Stance Suspension USA, coilover-only catalog
- `kwsuspensions` (tier1) — premium coilover brand
- `fortuneauto` (tier1) — coilover series catalog

*Turbo specialists* (declare `["turbo", "universal"]`):
- `atpturbo` (tier0) — Garrett aftermarket distributor
- `fullrace` (tier0) — turbo manifold + drop-in turbo specialist

*Everyone else* (the remaining 97 adapters): declare `["universal"]`. This includes mixed-catalog resellers (ecstuning/jegs/summitracing/tirerack/americanmuscle), wheel houses (fifteen52/rotiform/titan7/hrewheels/apexwheels/forgeline), tuning houses (cobbtuning/ktuner/hondata/ecutek/openflashperformance/linkecu/aemelectronics/haltech), and platform-specific shops (a90shop/csfrace/iagperformance/etc.). Each gets a `category_targets` declaration so compliance audit passes — `universal` is the safe floor since the S02 bridge already routes any non-coilover/brake/turbo categorized payload there.

**Helper script contract** (`backend/scripts/m002_s03_apply_category_targets.py`):
1. Define `SPECIALIST_MAPPING: dict[str, list[str]]` with the brake/coilover/turbo sets above.
2. Walk `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/*.py` (excluding `__init__.py`, `base.py`, `generic.py`).
3. For each adapter file, read it, locate the `ADAPTER_NAME: ClassVar[str] = "<slug>"` line, and insert `category_targets: ClassVar[list[str]] = [...]` exactly *after* the `ADAPTER_NAME` line at the same indentation. Use the SPECIALIST_MAPPING value if present, otherwise `["universal"]`.
4. Idempotent: skip files that already declare `category_targets =` (regex match on the keyword) so re-running the helper is safe.
5. Print a one-line-per-adapter summary (`tier0_http/wilwood.py: category_targets = ['brake', 'universal']`) and a final count.

**Edit shape inside each adapter file** — the inserted line lives directly under `ADAPTER_NAME` so all class-level ClassVars cluster together (matches the existing convention where `FETCHER_TIER` / `HEALTH_PROBE_URL` / `IS_FALLBACK` sit near the top of the class body):

```python
    ADAPTER_NAME: ClassVar[str] = "wilwood"
    category_targets: ClassVar[list[str]] = ["brake", "universal"]
```

**Constraints / pitfalls:**
- Do NOT change adapter logic, imports, or any existing ClassVars. Only insert one new line per file.
- The `ClassVar[list[str]]` type annotation is required (matches the base class declaration) so pyright stays clean.
- Some adapter files declare ADAPTER_NAME with a comment on the same line — use a regex that anchors on the literal `ADAPTER_NAME: ClassVar[str] =` and inserts on the next physical line, preserving any inline comments.
- After running the helper, manually spot-check 5 representative diffs (one tier0 specialist, one tier0 catch-all, one tier1 specialist, one tier1 catch-all, one tier2 catch-all) to confirm the insertion landed inside the class body, not at module scope.
- Run `pyright` (or at minimum `python -c 'from app.crawlers.adapters import ADAPTER_REGISTRY; print(len(ADAPTER_REGISTRY))'`) afterward — `__init_subclass__` validates each declared slug at import, so a typo would surface as a TypeError during discovery.

## Inputs

- ``backend/app/crawlers/compliance_audit.py` — runnable audit script from T01 (initially fails 0/108; must report 108/108 after this task)`
- ``backend/app/crawlers/adapters/base.py` — `category_targets` ClassVar declaration + `__init_subclass__` validation gate; defines the contract this task must satisfy`
- ``backend/app/crawlers/specs/__init__.py` — `default_registry` registrations (`coilover`, `brake`, `turbo`, `universal`); every value the helper inserts must be one of these slugs`

## Expected Output

- ``backend/scripts/m002_s03_apply_category_targets.py` — committed one-shot helper that owns the SPECIALIST_MAPPING; idempotent re-runs are no-ops`
- ``backend/app/crawlers/adapters/tier0_http/girodisc.py` — `category_targets = ["brake", "universal"]` inserted after ADAPTER_NAME (representative specialist)`
- ``backend/app/crawlers/adapters/tier0_http/wilwood.py` — `category_targets = ["brake", "universal"]``
- ``backend/app/crawlers/adapters/tier0_http/bcracing.py` — `category_targets = ["coilover", "universal"]``
- ``backend/app/crawlers/adapters/tier1_tls/kwsuspensions.py` — `category_targets = ["coilover", "universal"]``
- ``backend/app/crawlers/adapters/tier1_tls/fortuneauto.py` — `category_targets = ["coilover", "universal"]``
- ``backend/app/crawlers/adapters/tier0_http/atpturbo.py` — `category_targets = ["turbo", "universal"]``
- ``backend/app/crawlers/adapters/tier0_http/fullrace.py` — `category_targets = ["turbo", "universal"]``
- ``backend/app/crawlers/adapters/tier2_browser/jegs.py` — `category_targets = ["universal"]` (representative catch-all)`
- `All other adapter files under `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/` (97 catch-alls + 4 brake + 5 coilover + 2 turbo specialists already listed above = 108 total) — each gains exactly one `category_targets: ClassVar[list[str]] = [...]` line`

## Verification

cd backend && python scripts/m002_s03_apply_category_targets.py && python -m app.crawlers.compliance_audit && python -c "from app.crawlers.adapters import ADAPTER_REGISTRY; assert len(ADAPTER_REGISTRY) == 108, len(ADAPTER_REGISTRY); assert all(getattr(c, 'category_targets', []) for c in ADAPTER_REGISTRY.values())"

## Observability Impact

No new runtime signals — declarative metadata only. After the retrofit, `__init_subclass__` validates every declared slug against `default_registry` at import time, so any future typo (`'breake'` instead of `'brake'`) raises TypeError during adapter discovery, not silently at extraction-time. The compliance audit's stdout becomes the canonical inspection surface for binary compliance.
