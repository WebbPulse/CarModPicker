---
estimated_steps: 16
estimated_files: 1
skills_used: []
---

# T04: Close gauntlet: 3 grep gates + retailer-link cross-check + type-check + lint + vitest + build + Playwright with reviewed snapshot refresh

Slice-level close gauntlet. Run linearly — fix any failure before continuing.

## Sequential checks (all must pass)

1. **Grep gate 1 — raw palette (S01 carry-forward):** `rg 'bg-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]|text-(primary|neutral|emerald|indigo|accent|rose|amber|purple)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit code 1 (zero hits) is the pass condition.
2. **Grep gate 2 — glass-* (S02 carry-forward):** `rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1.
3. **Grep gate 3 — `var(--*)` legacy (S02 carry-forward):** `rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/` → exit 1.
4. **Grep gate 4 — retailer outbound link cross-check (NEW for S03):** Verify ViewPart's collapsed block + PartsCuration outbound link both carry `rel="noopener noreferrer"`. Run `rg -l 'target="_blank"' frontend/src/pages/builder/ViewPart.tsx frontend/src/pages/admin/PartsCuration.tsx` then for each file confirm `rg -q 'rel="noopener noreferrer"' <file>` returns exit 0. This is informational — non-retailer outbound links elsewhere with `rel="noreferrer"` alone (Footer, Header, PrivacyPolicy, Support, etc.) are out of scope and stay as-is.
5. **Type-check:** `npm --prefix frontend run type-check` → exit 0.
6. **Lint:** `npm --prefix frontend run lint` → exit 0 with zero net-new errors over the MEM062 baseline of 108 in slice-touched files.
7. **Vitest:** `npm --prefix frontend test -- --run` → exit 0; the rewritten 5 tests in `ViewPart.priceSummary.test.tsx` must all pass.
8. **Build:** `npm --prefix frontend run build` → exit 0.
9. **Playwright with snapshot refresh:** `cd frontend && npx playwright test --update-snapshots e2e/price-history.spec.ts`. Then run `git status --short frontend/e2e/price-history.spec.ts-snapshots/` and review every refreshed PNG visually before staging. Per MEM156 / MEM160, `--update-snapshots` defaults to `changed` mode in Playwright 1.59+ — only PNGs that actually differ rewrite. Expect 3 PNGs to change (`-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-{mobile,tablet,desktop}-linux.png`); if more drift than expected, investigate before continuing.
10. **Final Playwright re-run without `--update-snapshots`:** `cd frontend && npx playwright test` → exit 0 confirms baselines are stable post-refresh.

## Output

Write `.gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md` with: each check's exit code + duration, refreshed-PNG list with reviewed-OK note per file, lint-baseline confirmation, and any deviation observed.

## Manual visual spot-check

Skip under autonomous mode (per S02 precedent) — the 9 mechanical gates above are the slice's strongest objective signals. Coverage gap noted in slice summary.

## Inputs

- ``frontend/src/pages/builder/ViewPart.tsx` — refactored ViewPart from T03`
- ``frontend/src/pages/admin/PartsCuration.tsx` — link safety fix from T03`
- ``frontend/src/pages/admin/CrawlerAdmin.tsx` — overflow wrapper from T02`
- ``frontend/src/pages/admin/ExtractionHealth.tsx` — overflow wrapper from T02 (if applied)`
- ``frontend/e2e/price-history.spec.ts` — heading update from T03`
- ``frontend/e2e/price-history.spec.ts-snapshots/` — PNG baselines to refresh`

## Expected Output

- ``.gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md` — gauntlet results table with all 10 checks marked PASS, refreshed-PNG list (3 files for price-history spec at mobile/tablet/desktop), reviewed-OK confirmation per PNG, and final `git status --short` summary`
- ``frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-mobile-linux.png` — refreshed`
- ``frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-tablet-linux.png` — refreshed`
- ``frontend/e2e/price-history.spec.ts-snapshots/-parts-id-detail-renders-retailer-breakdown-stale-caveat-1-desktop-linux.png` — refreshed`

## Verification

test -f .gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md && grep -q 'all green\|all pass\|exit 0' .gsd/milestones/M003/slices/S03/tasks/T04-SUMMARY.md
