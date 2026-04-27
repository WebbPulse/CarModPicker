---
id: T05
parent: S05
milestone: M003
key_files:
  - frontend/src/pages/admin/ReportReview.tsx
  - frontend/src/pages/admin/BugReportReview.tsx
  - frontend/src/pages/admin/UserManagement.tsx
  - frontend/src/pages/admin/CrawlerAdmin.tsx
  - frontend/src/pages/admin/SystemAdmin.tsx
  - frontend/src/pages/admin/SystemStatistics.tsx
  - frontend/src/pages/admin/PartsCuration.tsx
key_decisions:
  - UserManagement subscription tier badge stays as inline tokenized span (bg-warning text-warning-foreground / bg-muted text-muted-foreground) NOT StatusBadge — the StatusBadge enum (pending|in_progress|resolved|dismissed) doesn't model premium|free; consuming StatusBadge would be incorrect domain mixing. Fixing the invisible-text bug + matching surrounding solid-bg-with-light-text badge shape is the locked goal. Captured as MEM187.
  - SystemAdmin 10 danger panels tokenized in-place per slice plan — the DangerActionPanel extraction is explicitly deferred to S06 UAT in autonomous mode (high-impact IA per MEM183). Each panel bg-{color}-900/20 + border-{color}-700/50 + text-{color}-400 mapped to closest semantic token (blue->info, green->success, red->destructive, orange->warning, cyan->info). The cyan->info mapping is the only ambiguous case; info is the closest tonal match for the bucket-cleanup section's informational character.
  - CrawlerAdmin polish scoped narrowly to the TIER_META raw color literals (4 lines). The file has many text-[10px]/text-[11px] surfaces but the verification gate only targets SystemStatistics+PartsCuration for those, and CrawlerAdmin dense font-mono operational data displays are intentionally compact. Followed gate scope, didn't broaden to file-level sweep.
duration: 
verification_result: passed
completed_at: 2026-04-27T00:54:35.642Z
blocker_discovered: false
---

# T05: feat: Polish 7 admin pages — fix UserManagement invisible-text bug, consume StatusBadge/PriorityBadge/Textarea/LoadingOverlay primitives, tokenize CrawlerAdmin TIER_META raw colors, retire SystemStatistics/PartsCuration micro-px cruft, tokenize SystemAdmin danger panels in-place

**feat: Polish 7 admin pages — fix UserManagement invisible-text bug, consume StatusBadge/PriorityBadge/Textarea/LoadingOverlay primitives, tokenize CrawlerAdmin TIER_META raw colors, retire SystemStatistics/PartsCuration micro-px cruft, tokenize SystemAdmin danger panels in-place**

## What Happened

Polished the 7 admin pages against the clean post-S04 substrate. Critical bug fix: replaced bg-warning text-warning (invisible same-color text-on-bg) at UserManagement.tsx:428 with bg-warning text-warning-foreground matching the surrounding solid-bg-with-light-text badge pattern. Replaced 3 hand-rolled status-badge factories (ReportReview.getStatusBadge, BugReportReview.getStatusBadge + getPriorityBadge) with the new StatusBadge/PriorityBadge primitives from T01. Collapsed 3 admin loading-overlay divs (ReportReview, BugReportReview, UserManagement) to LoadingOverlay visible. Replaced 2 hand-rolled textarea blocks with Textarea primitive. Tokenized CrawlerAdmin TIER_META custom row borders: border-l-emerald-600/70 -> border-l-success/70, amber -> warning, rose -> destructive, indigo -> info. SystemStatistics + PartsCuration: stripped all text-[10px]/text-[11px]/text-[9px] and min-[420px]:grid-cols-3/min-[360px]:grid-cols-2 micro-breakpoint cruft -> standard text-xs and sm:grid-cols-2/3 Tailwind utilities; retokenized bespoke section bg/border (border-gray-800/90 bg-gray-950/65) -> border-border bg-card/65; full gray-100/200/300/400/500/600 -> text-foreground/text-muted-foreground sweep. SystemAdmin: tokenized all 10 near-identical danger panels in-place per slice plan (DangerActionPanel extraction explicitly deferred to S06 UAT) — bg-blue-900/20 border-blue-700 -> bg-info/20 border-info, bg-green-900/20 border-green-700 -> bg-success/20 border-success, bg-red-900/20 border-red-700 -> bg-destructive/20 border-destructive, bg-orange-900/20 border-orange-700/50 -> bg-warning/20 border-warning/50, bg-cyan-900/20 border-cyan-700/50 -> bg-info/20 border-info/50; raw text-{green,red,orange,cyan}-400 -> text-{success,destructive,warning,info}; bg-{orange,cyan}-600 buttons -> bg-{warning,info} with proper foreground contrast tokens. Also tokenized: subscription/priority select elements in BugReportReview/UserManagement (bg-gray-800 border-gray-600 -> bg-background border-input with focus-ring); dialog detail bg-gray-800 boxes -> bg-muted text-foreground; bg-green-600 Resolve buttons in ReportReview/BugReportReview -> bg-success text-success-foreground. UserManagement 11-column table responsive strategy NOT changed (high-impact IA deferred to S06 per slice plan). The 5 task-level grep gates all return exit 1. The 7 named S04 standing grep gates remain green. Type-check + lint + 594/594 vitest + vite build all green. The 9 admin test files (48 tests) pass with the new primitives.

## Verification

All 5 task-level grep gates pass (exit 1, zero matches): (1) rg getStatusBadge|getPriorityBadge in admin/ exit 1; (2) rg bg-warning text-warning" in UserManagement exit 1, file now contains bg-warning text-warning-foreground at the prior bug location; (3) rg textarea in 3 files exit 1; (4) rg text-[10px]|text-[11px]|min-[420px]:grid-cols-3 in SystemStatistics+PartsCuration exit 1; (5) rg border-l-(emerald|amber|indigo|rose) in CrawlerAdmin exit 1. The 7 named S04 standing grep gates remain green. Type-check exit 0, lint exit 0 (no new errors), 594/594 vitest tests pass across 90 files, vite build exit 0 (canonical R061 structural enforcement). Admin-specific vitest subset (9 files / 48 tests including ReportReview.test.tsx, BugReportReview.test.tsx, UserManagement.test.tsx, CrawlerAdmin.test.tsx, SystemAdmin.test.tsx, SystemStatistics.test.tsx, PartsCuration.test.tsx) all green.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'getStatusBadge|getPriorityBadge' frontend/src/pages/admin/` | 1 | pass | 100ms |
| 2 | `rg 'bg-warning text-warning' frontend/src/pages/admin/UserManagement.tsx` | 1 | pass | 50ms |
| 3 | `rg '<textarea' frontend/src/pages/admin/{ReportReview,BugReportReview,UserManagement}.tsx` | 1 | pass | 80ms |
| 4 | `rg 'text-\[10px\]|text-\[11px\]|min-\[420px\]:grid-cols-3' frontend/src/pages/admin/{SystemStatistics,PartsCuration}.tsx` | 1 | pass | 50ms |
| 5 | `rg 'border-l-(emerald|amber|indigo|rose)-[0-9]' frontend/src/pages/admin/CrawlerAdmin.tsx` | 1 | pass | 50ms |
| 6 | `rg 'glass-(card|button)?' src/` | 1 | pass (S04 standing gate) | 100ms |
| 7 | `npm run type-check` | 0 | pass | 6000ms |
| 8 | `npm run lint` | 0 | pass (no new errors) | 6000ms |
| 9 | `npm test -- --run src/pages/admin/` | 0 | pass (48/48 admin tests) | 1710ms |
| 10 | `npm test -- --run` | 0 | pass (594/594 tests) | 5400ms |
| 11 | `npm run build` | 0 | pass (vite + prerender 7 routes - R061 canonical) | 11000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/admin/ReportReview.tsx`
- `frontend/src/pages/admin/BugReportReview.tsx`
- `frontend/src/pages/admin/UserManagement.tsx`
- `frontend/src/pages/admin/CrawlerAdmin.tsx`
- `frontend/src/pages/admin/SystemAdmin.tsx`
- `frontend/src/pages/admin/SystemStatistics.tsx`
- `frontend/src/pages/admin/PartsCuration.tsx`
