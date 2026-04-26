---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T05: Polish admin pages: ReportReview, BugReportReview, UserManagement, CrawlerAdmin, SystemAdmin, SystemStatistics, PartsCuration — fix invisible-text bug, consume new admin primitives, tokenize bespoke StatPanels

Polish-pass batch covering 7 admin pages (research Batches 7+8+9+10 merged — admin touches the same primitives and shares the same off-palette stat-panel pattern; file-disjoint from T02/T03/T04). Critical bug fix: replace bg-warning text-warning at UserManagement.tsx:428 (invisible same-color text-on-bg) with bg-warning text-warning-foreground (or bg-warning/10 text-warning if a tinted-bg-with-warning-text reading is intended — pick whichever matches the surrounding badge pattern). Consume the new T01 primitives: ReportReview, BugReportReview replace their getStatusBadge factories with StatusBadge variant; UserManagement consumes StatusBadge for subscription tier badge; the 3 admin loading-overlay divs collapse to LoadingOverlay visible; ReportReview, BugReportReview replace any remaining hand-rolled <textarea> with Textarea. SystemStatistics + PartsCuration: tokenize the bespoke StatPanel/StatRow (text-[10px]/text-[11px]/min-[420px]:grid-cols-3 micro-breakpoint cruft) — replace with Card + semantic-token text utilities (text-xs/text-sm/text-foreground/text-muted-foreground). CrawlerAdmin: tokenize the custom TIER_META mixing semantic tokens with raw border-l-emerald-600/70 etc. — replace raw color literals with semantic tokens (border-l-success, etc.). SystemAdmin: tokenize the 10 near-identical danger panels in-place (do NOT extract DangerActionPanel — high-impact extraction deferred to S06 UAT; document in slice summary). UserManagement 11-column table responsive strategy is high-impact IA — defer to S06; in this slice just tokenize and accept the existing horizontal scroll behavior. Quality gate (Q3 Threat Surface): Admin pages handle privileged operations (delete-user, resolve-report, dismiss-bug-report, manual crawl trigger, system-wide deletes). All edits in this task are visual-only — submit handlers, fetch calls, role checks, and confirmation dialogs (ConfirmDialog) are unchanged. The invisible-text fix at UserManagement.tsx:428 is a pure CSS-class swap with no behavior change. No new abuse surface introduced. Quality gate (Q4): Touches R060 — admin pages already have partial baseline coverage (admin.spec.ts covers AdminDashboard + ExtractionHealth); this task changes other admin pages visually so T06's polish-coverage.spec.ts picks up baselines for the 5 currently-unbaselined admin pages. Quality gate (Q5): Status-badge factory replacement must preserve the variant-to-color mapping; mismatch would render the wrong color for a status. Mitigated by ReportReview.test.tsx + BugReportReview.test.tsx + UserManagement.test.tsx vitest assertions on rendered text/aria-label, plus visual review at T06 cascade refresh. Quality gate (Q7): Existing admin vitest specs cover the rendered status-badge text and the action button click handlers. The invisible-text bug at UserManagement.tsx:428 was previously passing tests because tests assert text presence, not color contrast — this slice adds no contrast assertion, but the visual baseline at T06 will lock the fixed contrast.

## Inputs

- ``frontend/src/components/ui/status-badge.tsx``
- ``frontend/src/components/ui/loading-overlay.tsx``
- ``frontend/src/components/ui/textarea.tsx``
- ``frontend/src/pages/admin/ReportReview.tsx``
- ``frontend/src/pages/admin/BugReportReview.tsx``
- ``frontend/src/pages/admin/UserManagement.tsx``
- ``frontend/src/pages/admin/CrawlerAdmin.tsx``
- ``frontend/src/pages/admin/SystemAdmin.tsx``
- ``frontend/src/pages/admin/SystemStatistics.tsx``
- ``frontend/src/pages/admin/PartsCuration.tsx``

## Expected Output

- ``frontend/src/pages/admin/ReportReview.tsx``
- ``frontend/src/pages/admin/BugReportReview.tsx``
- ``frontend/src/pages/admin/UserManagement.tsx``
- ``frontend/src/pages/admin/CrawlerAdmin.tsx``
- ``frontend/src/pages/admin/SystemAdmin.tsx``
- ``frontend/src/pages/admin/SystemStatistics.tsx``
- ``frontend/src/pages/admin/PartsCuration.tsx``

## Verification

1. rg 'getStatusBadge|getPriorityBadge' frontend/src/pages/admin/ returns 0. 2. rg 'bg-warning text-warning"' frontend/src/pages/admin/UserManagement.tsx returns 0; the file contains bg-warning text-warning-foreground (or equivalent visible-contrast pairing) at the prior line 428 location. 3. rg '<textarea\b' frontend/src/pages/admin/{ReportReview,BugReportReview,UserManagement}.tsx returns 0. 4. rg 'text-\[10px\]|text-\[11px\]|min-\[420px\]:grid-cols-3' frontend/src/pages/admin/{SystemStatistics,PartsCuration}.tsx returns 0. 5. rg 'border-l-(emerald|amber|indigo|rose)-[0-9]' frontend/src/pages/admin/CrawlerAdmin.tsx returns 0. 6. The 12 S04 grep gates remain green. 7. cd frontend && npm run type-check && npm run lint && npm test -- --run all exit 0; specifically ReportReview.test.tsx, BugReportReview.test.tsx, UserManagement.test.tsx, CrawlerAdmin.test.tsx, SystemAdmin.test.tsx, SystemStatistics.test.tsx, PartsCuration.test.tsx all pass.
