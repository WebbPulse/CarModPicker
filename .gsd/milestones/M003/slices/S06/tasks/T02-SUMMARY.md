---
id: T02
parent: S06
milestone: M003
key_files:
  - frontend/src/__tests__/no-legacy-primitives.test.ts
key_decisions:
  - Refactored to a shared `scan(globs, patterns, allowlist)` helper rather than duplicating the three new it() bodies — reduces maintenance surface and makes future gates trivial to add (captured as MEM192).
  - Allowlisted `index.css` and `styles/tokens.css` for the palette + glass gates (per MEM168); allowlisted each ui/ primitive source file for the hand-rolled gate so the primitives themselves don't trip their own regex.
  - Combined raw-palette + text-accent into one assertion (palette gate) and glass-class + className-glass into one assertion (glass gate); each uses an array of regexes with first-match short-circuit. Avoids 5 separate it() blocks that would all share the same scope/allowlist.
  - Used regex strings as `const RE = /.../;` declarations at module top so the source is reviewable without scanning helper bodies — keeps the contract auditable.
duration: 
verification_result: passed
completed_at: 2026-04-27T01:39:42.279Z
blocker_discovered: false
---

# T02: Extend vitest grep-guard with 3 assertions blocking raw-palette, glass-*, and hand-rolled primitive re-entry

**Extend vitest grep-guard with 3 assertions blocking raw-palette, glass-*, and hand-rolled primitive re-entry**

## What Happened

Extended `frontend/src/__tests__/no-legacy-primitives.test.ts` with a new `describe('M003-S06: no legacy design-system re-entry')` block containing three `it()` assertions that promote the per-PR grep gates into vitest assertions:

1. **`no raw legacy palette utilities outside index.css/tokens.css`** — combines the standing palette gates 1+2 (raw `text|bg|border|ring|from|to|via-(primary|neutral|emerald|indigo|amber|rose)-N` and `text-accent-(emerald|amber|rose|purple)`) into a single line scan over consumer dirs (`components,pages,contexts,hooks,api,lib,__tests__`). Allowlist excludes `index.css` and `styles/tokens.css`.

2. **`no glass-* class references in consumer code`** — combines the standing glass gates 3+4 (`\bglass-(card|button)?\b` and `className=.*\bglass\b`). Same scope and allowlist as palette gate. The `<Card variant="glass">` syntax intentionally does not match because the regex requires `className=` prefix (per MEM168).

3. **`no hand-rolled patterns now that ui/* primitives exist`** — three sub-checks combined: hand-rolled `<textarea ` (allowlisted `ui/textarea.tsx`), inline `className="absolute inset-0 bg-background/80 backdrop-blur-sm` overlay div (allowlisted `ui/loading-overlay.tsx`), and inline `getStatusBadge`/`getPriorityBadge` factory functions (allowlisted `ui/status-badge.tsx`).

Refactored the existing R017 assertion to share a `scan()` helper that dedupes files across multiple globs, applies a regex-array per file, and short-circuits on first match. Allowlist always includes the guard file itself (since the test source contains the literal regex source strings).

Followed MEM168 (consumer-dir scoping), MEM163 (pre-checked test files for literal palette strings — none found, so no placeholder rewrites needed), and MEM180 (file is self-allowlisted). Pre-write probes against the entire `frontend/src` tree confirmed all 7 patterns are currently clean (zero matches), so the new assertions land green on the post-S05 substrate.

**Verification probe** (per task plan): created a temporary `frontend/src/pages/__probe_violation__.tsx` with one violation per assertion. The probe run produced 3 failing tests with file:line:match output for each violation (raw-palette + glass on the same line counted as one violation in the palette gate; the glass and hand-rolled gates each fired separately). Probe file was deleted before the final verification run, which is now green: 4/4 vitest tests pass, eslint clean, tsc -b --noEmit clean.

This T02 application is sanctioned by the slice plan: T01 landed cleanly with 3 atomic commits and budget remained. Pattern memory captured as MEM192 for future "no re-entry of retired pattern" grep-guards.

## Verification

Ran the slice-defined verification command from the task plan: `cd frontend && npm test -- --run __tests__/no-legacy-primitives && npm run lint && npm run type-check`. All three checks green. Verification probe (temporary `__probe_violation__.tsx` reintroducing one violation per new assertion) confirmed each new `it()` block fails with file:line:match output identifying the offending file — the regression-visibility goal of the gate. Probe deleted before final run.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm test -- --run __tests__/no-legacy-primitives` | 0 | ✅ pass — 4/4 tests (1 R017 + 3 M003-S06) | 656ms |
| 2 | `cd frontend && npm run lint` | 0 | ✅ pass — no eslint violations | 4500ms |
| 3 | `cd frontend && npm run type-check` | 0 | ✅ pass — tsc -b --noEmit clean | 6000ms |
| 4 | `verification probe — npm test with temporary __probe_violation__.tsx in pages/` | 1 | ✅ pass — 3 new assertions fail with file:line:match for each violation, R017 assertion stays green (probe targets new gates only) | 650ms |

## Deviations

Minor structural deviation: the task plan suggested 3 new `it()` blocks, one per category. Implementation uses 3 new `it()` blocks but factors a shared `scan()` helper for DRY-ness (the original R017 it() also got refactored to use the helper-adjacent pattern, though it kept its own local loop to preserve the existing exclusion-glob shape). Net effect identical to the plan; per-assertion failure messages still surface file/line/match individually.

## Known Issues

None. The hand-rolled `<textarea>` regex is `<textarea\s` which matches both `<textarea ` and `<textarea\n`; the loading-overlay regex is a string literal match (not a token-decomposed match) so any reformulation of those exact 4 utilities (e.g. reordering `inset-0` and `absolute`) would slip past — accepted as heuristic, future false-negatives can be tightened. The `getStatusBadge`/`getPriorityBadge` regex is heuristic-only; if a future legitimate use emerges outside `ui/status-badge.tsx`, allowlist that file.

## Files Created/Modified

- `frontend/src/__tests__/no-legacy-primitives.test.ts`
