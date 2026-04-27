---
estimated_steps: 25
estimated_files: 7
skills_used: []
---

# T01: Resolve autonomous-judgable IA deferrals; document human-judgment deferrals in M003-UAT.md

S05 deferred 6 IA decisions to S06 UAT. They split cleanly: 3 are autonomous-judgable (refactor-only or status-quo confirmations), 3 require human visual judgment. Apply the autonomous-judgable items as atomic commits with rationale + cascade-aware baseline refresh; reformat the human-judgment items as decision slots in a new `.gsd/milestones/M003/M003-UAT.md` so the operator UAT walkthrough has a checklist with file:line refs.

**Autonomous-judgable items to apply:**

1. **SystemAdmin DangerActionPanel extraction** (deferral #6) — extract a `DangerActionPanel` component composing heading + danger description + ConfirmDialog wrapper. The 10 near-identical danger sections in `frontend/src/pages/admin/SystemAdmin.tsx` (resolve-all-reports, dismiss-all-bug-reports, force-reseed-categories, etc.) collapse to 10 component instances. Pure refactor: semantic-token output unchanged → polish-coverage baseline of `/admin/system` should be byte-identical. Component lives at `frontend/src/components/admin/DangerActionPanel.tsx` (admin-specific not ui-generic, matching the existing `ReportDialog.tsx` placement). API shape: `{ title, description, dangerColor: 'destructive' | 'warning' | 'info', confirmDialogProps, children? }` — derive from the 10 sites' shared shape.

2. **UserManagement 11-column table responsive strategy** (deferral #5) — lock option (a) `acceptable-as-scroll` as the explicit decision. No code change. Document the decision in `M003-UAT.md` decision-record section + add a one-line code comment at the table boundary in `frontend/src/pages/admin/UserManagement.tsx` referencing the decision and MEM179. The other options (b)-(d) remain available as future M004 backlog.

3. **ViewBuildLog markdown prose plugin** (deferral #4) — research-then-decide. Check Tailwind v4 + `@tailwindcss/typography` compatibility (Tailwind v4 plugin registration moved to `@plugin` directive in CSS). If plugin loads cleanly AND output is visually-comparable to the per-element tokenization landed in S05/T04 (~25 sites), apply: `npm i -D @tailwindcss/typography`, register via `@plugin '@tailwindcss/typography';` in `frontend/src/index.css` after `@import 'tailwindcss';`, replace the per-element `components` overrides in `frontend/src/pages/buildLists/ViewBuildLog.tsx` with one `<div className="prose prose-invert">` wrapper, refresh the affected baselines. If incompatible or visually-divergent, leave the per-element tokenization in place and document the deferral with the specific incompatibility note in `M003-UAT.md`. **Decision rule:** prefer the per-element tokenization if there is any visual ambiguity — MEM186 captures the conservative path as already valid.

**Human-judgment items to document in M003-UAT.md (do NOT modify code):**

1. **Auth-shell unification** — `frontend/src/pages/authentication/{Login.tsx, Register.tsx, ExtensionAuth.tsx}` use a glass-card-style surrounding wrapper (now tokenized); `frontend/src/pages/authentication/{ForgotPassword.tsx, ForgotPasswordConfirm.tsx, VerifyEmail.tsx}` use the `AuthCard` component (`frontend/src/components/auth/AuthCard.tsx`). Decision slot: which shell wins, or do they merge into a third primitive?

2. **ContactUs 3-card collapse** — `frontend/src/pages/ContactUs.tsx` renders 3 near-identical email-cards. Collapsing to one card with a recipient toggle is medium-to-high-impact UX change.

3. **BuildListsCatalog sidebar drawer** — `frontend/src/pages/buildLists/BuildListsCatalog.tsx` left filter sidebar pushes content rightward at narrow viewports. Decision slot: drawer-vs-bottom-sheet at `<lg` breakpoint; likely needs a new `ui/drawer.tsx` primitive (M002 inventory check needed).

**M003-UAT.md structure:**

```markdown
# M003 — Migration Completion UAT

## Priority Pages — Per-Viewport Verdicts

[Per-page table sourced from S05-SUMMARY.md verdict table for the 11 priority pages: Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth. Mobile=375 / tablet=768 / desktop=1280 columns; verdict per cell with PNG baseline reference.]

## 360px Manual Walkthrough — Operator Checklist

[For each priority page, a TODO checkbox: `- [ ] /home — open in DevTools at 360×640, confirm: no horizontal overflow, header navigation usable, primary CTA reachable. Operator notes: ___`]

## IA Deferral Decisions

### #1 Auth-shell unification
Files: ...
Observation: ...
Decision: [ ] keep both shells | [ ] unify on glass-card | [ ] unify on AuthCard | [ ] merge to new primitive
Operator notes: ___

[Repeat for #2 ContactUs and #3 BuildListsCatalog drawer.]
```

**Cascade-refresh expectation per MEM176:** DangerActionPanel extraction is a pure refactor with semantic-token output unchanged, so polish-coverage's `/admin/system` baseline should refresh zero PNGs (per MEM156/MEM160 default `=changed` mode). If ViewBuildLog prose plugin is applied, expect 3 baselines to drift (`/build-lists/<uuid>/build-log` × 3 viewports in polish-coverage.spec.ts; cross-check with `grep -l "build-log" frontend/e2e/*.spec.ts` to confirm no other spec covers the route). UserManagement #5(a) is no-code-change.

## Inputs

- ``.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` — Deferrals to S06 UAT section (the 6 IA items with file paths)`
- ``.gsd/milestones/M003/slices/S06/S06-RESEARCH.md` — research recommendation for the autonomous-vs-human split`
- ``frontend/src/pages/admin/SystemAdmin.tsx` — 10 danger sections to refactor (lines ~383–680)`
- ``frontend/src/pages/admin/UserManagement.tsx` — 11-column table boundary`
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx` — ~25 markdown component overrides for prose-plugin candidate`
- ``frontend/src/components/ui/confirm-dialog.tsx` — primitive consumed by DangerActionPanel`
- ``frontend/src/components/admin/ReportDialog.tsx` — placement reference for the new admin-scoped component`
- ``frontend/e2e/polish-coverage.spec.ts` — affected spec for cascade refresh`
- ``frontend/e2e/polish-coverage.spec.ts-snapshots/` — 120 PNG baselines (refresh policy)`

## Expected Output

- ``frontend/src/components/admin/DangerActionPanel.tsx` — new admin-scoped component composing ConfirmDialog (~40 LOC)`
- ``frontend/src/pages/admin/SystemAdmin.tsx` — 10 danger sections collapsed to DangerActionPanel instances; semantic-token output preserved`
- ``frontend/src/pages/admin/UserManagement.tsx` — one-line decision-record code comment near the 11-column table referencing M003-UAT.md and MEM179`
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx` — either `prose prose-invert` adoption (if plugin compatible) or unchanged with deferral note`
- ``frontend/src/index.css` — `@plugin '@tailwindcss/typography';` line added (only if prose plugin applied)`
- ``frontend/package.json` — `@tailwindcss/typography` devDependency entry (only if prose plugin applied)`
- ``.gsd/milestones/M003/M003-UAT.md` — new file with priority-page verdict table, 360px walkthrough checklist, 3 IA decision slots`
- ``frontend/e2e/polish-coverage.spec.ts-snapshots/` — refreshed baselines for any drifted route (expected: 0 for DangerActionPanel; 3 for prose plugin if applied; 0 for UserManagement)`

## Verification

cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build && (npx playwright test polish-coverage.spec.ts --update-snapshots || npx playwright test polish-coverage.spec.ts) && git diff -- e2e/polish-coverage.spec.ts-snapshots/ | head -100 && cd .. && test -f .gsd/milestones/M003/M003-UAT.md && grep -c '^### #' .gsd/milestones/M003/M003-UAT.md | xargs test 3 -le

## Observability Impact

Visual surface for /admin/system, /admin/users, and /build-lists/<uuid>/build-log is now locked by polish-coverage baselines; any future regression that mutates rendered geometry surfaces as a Playwright PNG diff naming the route + viewport. Decision-record code comment at UserManagement table boundary makes the `acceptable-as-scroll` decision discoverable to future agents (`grep MEM179 frontend/src/pages/admin/UserManagement.tsx`).
