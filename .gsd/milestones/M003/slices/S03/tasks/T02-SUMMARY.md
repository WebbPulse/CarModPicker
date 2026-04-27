---
id: T02
parent: S03
milestone: M003
key_files:
  - frontend/src/pages/admin/CrawlerAdmin.tsx
key_decisions:
  - Chose the one-class swap (overflow-hidden → overflow-x-auto) over the nested-wrapper alternative because it produces a cleaner single-line diff while preserving the rounded chrome — both patterns yield identical observable behavior.
  - Skipped the ExtractionHealth.tsx:203 coverage table wrapper add per T01's `pass` verdict at 360 and T02 plan's explicit 'skip when 360 verdict is pass' rule; adding a prophylactic wrapper would inflate the diff without observable improvement.
  - No regression test added because the wrapper class itself is the durable verification artifact; MEM170's 360-vs-375 viewport divergence means a Playwright assertion at the mobile project's 375 width would not reliably catch a regression of this kind.
duration: 
verification_result: passed
completed_at: 2026-04-26T22:17:07.443Z
blocker_discovered: false
---

# T02: Swapped CrawlerAdmin rate-limit table wrapper from overflow-hidden to overflow-x-auto, fixing the only fixed-pending verdict from T01's responsive audit.

**Swapped CrawlerAdmin rate-limit table wrapper from overflow-hidden to overflow-x-auto, fixing the only fixed-pending verdict from T01's responsive audit.**

## What Happened

Mechanical wrapper-only fix landing the single `fixed-pending → T02` action from T01's verdict table.

**Action taken**

`frontend/src/pages/admin/CrawlerAdmin.tsx:322` — changed the wrapper class from `rounded border border-gray-700/60 overflow-hidden` to `rounded border border-gray-700/60 overflow-x-auto`. This preserves the rounded chrome while letting the 5-col rate-limit table scroll horizontally inside the rounded crop instead of being clipped. The "Rate-limited @ N/M" badge in the adapter column was the specific 360px overflow trigger documented in MEM172 and T01's verdict for that surface.

**Action skipped (with rationale)**

`frontend/src/pages/admin/ExtractionHealth.tsx:203` — left untouched. T01's verdict for the 2-col per-tier coverage table was `pass` at all three viewports (360/768/1280) because field names like `title`, `price`, `mpn` are short enough that the unwrapped table fits below 360px. The T02 plan explicitly says "skip the wrapper add when 360 verdict is pass" — adding a prophylactic wrapper would only inflate the diff with no observable improvement.

**Constraint compliance**

- No other admin tables were touched (UserManagement, PartsCuration scan-diff, ExtractionHealth failure-rate are all already wrapped per T01).
- No column widths, row heights, or font sizes changed — wrapper-only.
- No new tokens or design-system primitives — `overflow-x-auto` is a vanilla Tailwind utility.
- Type-check and lint both green post-edit.

**Why one-line swap, not nested wrapper**

The T02 plan offered two patterns: swap `overflow-hidden` → `overflow-x-auto` on the existing wrapper, OR insert an inner `overflow-x-auto` div and keep the outer for the border. Both produce the same observable behavior. The single-class swap is the cleaner diff (1 line vs 3) and the rounded chrome still works because `overflow-x-auto` clips the same way `overflow-hidden` does on the rounded edge — only horizontal overflow now scrolls instead of being hidden.

**MEM170 caveat carried forward to manual UAT**

Per MEM170 the Playwright `mobile` project runs at 375×667, not 360. The 15-pixel margin can mask the original CrawlerAdmin overflow even before T02. The fix lands without a regression test because the durable proof is the wrapper class itself — `rg -q 'overflow-x-auto'` against the file is the verification artifact. A future Playwright snapshot at 360 would show the scroll affordance, but that's outside the slice's scope.

## Verification

- `rg -q 'overflow-x-auto' frontend/src/pages/admin/CrawlerAdmin.tsx` → exit 0 (the swap landed, the file matches the verification command from the task plan)
- `npm --prefix frontend run type-check` → exit 0, no diagnostics emitted
- `npm --prefix frontend run lint` → exit 0, no eslint warnings or errors
- `git diff frontend/src/pages/admin/CrawlerAdmin.tsx` → single line changed (319→319, `overflow-hidden` → `overflow-x-auto`), no collateral edits

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -q 'overflow-x-auto' frontend/src/pages/admin/CrawlerAdmin.tsx` | 0 | ✅ pass | 50ms |
| 2 | `npm --prefix frontend run type-check` | 0 | ✅ pass | 4500ms |
| 3 | `npm --prefix frontend run lint` | 0 | ✅ pass | 3500ms |
| 4 | `git diff --stat frontend/src/pages/admin/CrawlerAdmin.tsx (1 line changed)` | 0 | ✅ pass | 30ms |

## Deviations

None — the task plan offered two implementation patterns (one-class swap vs nested-wrapper) and explicitly noted "the simpler pattern is changing overflow-hidden → overflow-x-auto on line 322's div className." Took the simpler pattern. ExtractionHealth was correctly skipped per the plan's documented rule, not as a deviation.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/admin/CrawlerAdmin.tsx`
