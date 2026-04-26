---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T08: Close gauntlet: 12 grep gates + build + lint + type-check + vitest + Playwright with cascade refresh

Slice-level close gauntlet, all gates must pass before slice completion. Sequential: (1) Inherited S01 raw-palette gates (excluding `purple` per S01 commit 390fb4c precedent) — `rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1, `rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1; (2) Inherited S02 gates — `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1, `rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1, `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1; (3) New S04 gates — `rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` exit 1, AND verify `frontend/src/index.css` itself contains zero `.glass*` / `.btn-*` / `.card*` / `.input-modern` / `.text-gradient` / `.shadow-glow` / `.border-gradient` / `.skeleton` / `.hero-gradient` / `@theme` / legacy `:root` blocks via `rg -c '@theme|--primary-[0-9]|\.glass-card|\.btn-primary|\.card-interactive|\.input-modern|\.text-gradient|\.shadow-glow|\.border-gradient|\.skeleton|\.hero-gradient' frontend/src/index.css; test $? -eq 1`; (4) `cd frontend && npm run type-check` exit 0; (5) `npm run lint` exit 0 (zero net-new errors over MEM062 baseline of 108); (6) `npm test -- --run` exit 0 (full vitest suite); (7) `npm run build` exit 0 (the load-bearing proof — any missed consumer becomes an unresolved-class build error); (8) `npx playwright test --update-snapshots` to cascade-refresh baselines for any spec that visits a page where T05's body-background rewrite or T01's tokenized animation utilities pixel-differ from the legacy renders. Per MEM176, expect refreshes for `smoke.spec.ts` (Home — heavy `animate-slideInUp`/`animate-glow`/`animate-float` consumer; body-background rewrite) and possibly `components.spec.ts` (kitchen-sink — body-background only). Review each refreshed PNG visually before committing; document in slice summary. (9) `npx playwright test` (no --update-snapshots) — final clean run, must exit 0 across 3 viewports × 6 specs. If a gate fails: fix the underlying issue (migrate the missed consumer, repair the snapshot regression), commit atomically per R053, re-run from step 1. Document the final state in T08-SUMMARY.md including the wc -l of `index.css` (target ~50–80) and the count of refreshed PNG baselines.

## Inputs

- `frontend/src/index.css`
- `frontend/src/styles/tokens.css`
- `frontend/src/components/ui/button.tsx`
- `frontend/e2e/smoke.spec.ts`
- `frontend/e2e/components.spec.ts`

## Expected Output

- `.gsd/milestones/M003/slices/S04/tasks/T08-SUMMARY.md`
- `frontend/e2e/smoke.spec.ts-snapshots/`
- `frontend/e2e/components.spec.ts-snapshots/`

## Verification

cd frontend && rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' src/{components,pages,contexts,hooks,api,lib,__tests__}/ ; test $? -eq 1 && rg 'glass-(card|button)?' src/{components,pages,contexts,hooks,api,lib,__tests__}/ ; test $? -eq 1 && rg 'var\(--(primary|neutral|accent|gradient)-' src/{components,pages,contexts,hooks,api,lib,__tests__}/ ; test $? -eq 1 && rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' src/{components,pages,contexts,hooks,api,lib,__tests__}/ ; test $? -eq 1 && npm run type-check && npm run lint && npm test -- --run && npm run build && npx playwright test

## Observability Impact

Signals added/changed: 12-gate standing inspection surface (5 inherited from S01/S02 + 1 inherited variant from S03 + 6 new from S04). How a future agent inspects this: any single `rg` gate from the verify command can be run independently to detect regression; the canonical full-gate run is the verify command itself. Failure state exposed: each gate names the file and line of the violator; the build gate names the unresolved utility class. The cascade snapshot refresh produces a reviewable PNG diff per MEM176 — accept only if visually reasonable for the geometry/animation change introduced.
