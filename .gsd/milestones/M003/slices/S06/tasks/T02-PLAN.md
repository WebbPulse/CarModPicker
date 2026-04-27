---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T02: Extend vitest grep-guard to block raw-palette / glass-* / hand-rolled-primitive re-entry

Optional but high-leverage: extend `frontend/src/__tests__/no-legacy-primitives.test.ts` with three additional `it()` blocks that block re-entry of legacy patterns now that primitives exist. The existing test already walks `src/` with glob + asserts no file matches a regex; pattern is identical for the new assertions.

**Three new assertions to add:**

1. **`it('no raw legacy palette utilities outside index.css/tokens.css')`** — replicates standing gates 1 and 2 (S01 raw-palette and S01 text-accent) as a vitest test. Walks `src/**/*.{ts,tsx,css}` excluding `index.css` and `tokens.css` (so the `@theme` deletion holds and tokens.css is not flagged). Regex: `/(?:text|bg|border|ring|from|to|via)-(?:primary|neutral|emerald|indigo|amber|rose)-[0-9]/` and `/text-accent-(?:emerald|amber|rose|purple)/`. Per MEM168, scope to consumer dirs only (`{components,pages,contexts,hooks,api,lib,__tests__}`). Per MEM163/MEM180, the existing `__tests__/` exclusion already prevents test-file false positives, but double-check that no test file source contains the literal palette utility in a comment that would trip the regex; if found, rewrite the comment to use placeholder strings (e.g. `bg-primaryNNN`) per MEM163.

2. **`it('no glass-* class references in consumer code')`** — replicates standing gates 3 and 4. Regex: `/\bglass-(?:card|button)?\b/` and `/className=.*\bglass\b/`. Same glob/exclusions as above.

3. **`it('no hand-rolled patterns now that ui/* primitives exist')`** — three sub-pattern checks combined into one test for compactness:
   - **Hand-rolled `<textarea>`**: regex `/<textarea\s/`, but allow `frontend/src/components/ui/textarea.tsx` (the primitive itself). Anything else must `import { Textarea } from '@/components/ui/textarea'` (or relative equivalent).
   - **Inline loading-overlay div**: regex `/className="absolute inset-0 bg-background\/80 backdrop-blur-sm/`, allow `frontend/src/components/ui/loading-overlay.tsx`.
   - **Inline status-badge factory**: heuristic regex `/(?:const|function)\s+(?:get(?:Status|Priority)Badge)/`, allow `frontend/src/components/ui/status-badge.tsx`. This is a heuristic but practical match for the factory functions S05/T05 collapsed; future false positives can be allowlisted.

**Implementation pattern** — preserve the existing structure (one `describe` block, one `it` per assertion, `globSync` + `readFileSync` + per-line scan). Add a top-of-file comment block summarizing what each assertion blocks and the memory references (MEM168, MEM163, MEM180).

**Verification probe** — temporarily reintroduce one violation per assertion (e.g. add `bg-primary-500` to a single file in `pages/`, add `<textarea ` to `pages/Home.tsx`, etc.) and re-run `npm test -- --run __tests__/no-legacy-primitives` to confirm the new assertions fail with a useful violation message. Revert before commit.

**Decision rule:** apply T02 if T01 lands cleanly and budget remains. If T01 expanded materially or produced unexpected baseline drift, defer T02 to M004 backlog and document in S06-SUMMARY.md as a follow-up. The slice description marks T02 as 'Optional' so deferral is sanctioned.

## Inputs

- ``frontend/src/__tests__/no-legacy-primitives.test.ts` — existing R017 grep-guard pattern to mirror`
- ``frontend/src/components/ui/textarea.tsx` — allowlisted primitive (only legitimate <textarea> site)`
- ``frontend/src/components/ui/loading-overlay.tsx` — allowlisted primitive`
- ``frontend/src/components/ui/status-badge.tsx` — allowlisted primitive`
- ``frontend/src/index.css` — excluded from the palette/glass scan`
- ``frontend/src/styles/tokens.css` — excluded from the palette/glass scan`

## Expected Output

- ``frontend/src/__tests__/no-legacy-primitives.test.ts` — 3 new `it()` blocks added (no-raw-palette, no-glass-*, no-hand-rolled-primitives); existing R017 assertion preserved unchanged`

## Verification

cd frontend && npm test -- --run __tests__/no-legacy-primitives && npm run lint && npm run type-check

## Observability Impact

Regression visibility at `npm test` time — any reintroduction of legacy palette / glass-* / hand-rolled primitive surfaces with a vitest assertion failure naming the file + line. Replaces the per-PR grep gates with a CI-enforced check that fails fast at PR validation.
