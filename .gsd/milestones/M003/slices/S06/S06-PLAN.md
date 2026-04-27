# S06: Migration completion gauntlet + UAT

**Goal:** Run the milestone-close gauntlet against the post-S05 substrate: re-run all 12 standing gates (7 grep + 5 toolchain) with fresh evidence in this session, resolve the autonomous-judgable IA deferrals from S05, prepare a structured `M003-UAT.md` walkthrough document with decision slots for the 3 human-judgment IA deferrals, optionally extend the vitest R017-style grep-guard to block raw-palette / `glass-*` / hand-rolled-primitive re-entry, and produce the milestone-close evidence record. Owns R061; closes the M003 design-system migration.
**Demo:** All gates pass: zero raw palette utility hits, zero `glass-*` hits, zero legacy `:root` consumer hits in `frontend/src/`; `vite build`, `tsc --noEmit`, `eslint`, `vitest`, full Playwright suite at 3 viewports all green; manual UAT walkthrough at three viewports across priority pages (Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth) documented in slice summary or M003-UAT.md.

## Must-Haves

- All 12 standing gates green with command output captured this session (not cited from S05): 7 grep gates + type-check + lint + vitest + vite build + Playwright at 3 viewports.
- 3 autonomous-judgable IA deferrals resolved: SystemAdmin DangerActionPanel extraction landed (or explicitly documented as deferred-with-rationale if Tailwind-v4 / scope blocker surfaces); UserManagement 11-col responsive strategy locked as `acceptable-as-scroll` (status-quo recorded as the decision); ViewBuildLog prose-plugin researched-then-decided (apply if Tailwind v4 + `@tailwindcss/typography` is supported and visually-comparable; otherwise document deferral).
- 3 human-judgment IA deferrals (auth-shell unification, ContactUs 3-card collapse, BuildListsCatalog sidebar drawer) reformatted in `.gsd/milestones/M003/M003-UAT.md` as explicit decision slots with file:line refs, before/after intent, and a verdict checkbox per item.
- Optional grep-guard extension applied if budget remains: `frontend/src/__tests__/no-legacy-primitives.test.ts` extended to block raw-palette utility re-entry, `glass-*` re-entry, and hand-rolled `<textarea>` / inline loading-overlay div / inline status-badge factory re-entry. If deferred, follow-up captured in slice summary.
- `.gsd/milestones/M003/M003-UAT.md` exists with: per-priority-page verdict table at mobile=375 / tablet=768 / desktop=1280 backed by the polish-coverage Playwright PNG baselines; 360px manual-walkthrough TODO checklist for the 11 priority pages (Home, PartsCatalog, ViewPart, ViewBuildList, ViewCar, Login, Register, Header, AccountAlerts, AdminDashboard, AdminExtractionHealth); decision slots for the 3 human-judgment IA deferrals.
- `S06-SUMMARY.md` captures: gate evidence with command + exit code + relevant tail per gate; IA changes applied (T01 judgable items); IA changes documented for human UAT (T01 deferrals); optional grep-guard outcome (T02 applied or follow-up); standing operational signal post-M003 close.

## Proof Level

- This slice proves: - This slice proves: final-assembly (milestone-close gauntlet against the production substrate)
- Real runtime required: yes (vite build + Playwright across 3 viewports)
- Human/UAT required: yes (the 360px manual walkthrough is operator-driven; auto-mode prepares the document, operator records verdicts)

## Integration Closure

- Upstream surfaces consumed: post-S04 clean `frontend/src/index.css` (94 lines); `frontend/src/styles/tokens.css` semantic-token vocabulary; `frontend/e2e/polish-coverage.spec.ts` + 120 PNG baselines from S05; `frontend/src/test/route-coverage-list.ts` shared route list; the 4 new `ui/*` primitives from S05; the 6 deferred IA items pre-enumerated in `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md`.
- New wiring introduced in this slice: optional `DangerActionPanel` component composing `ConfirmDialog` + danger-section markup; optional `prose prose-invert` adoption in `ViewBuildLog.tsx` (conditional on Tailwind v4 plugin compatibility); optional vitest grep-guard extension; new `.gsd/milestones/M003/M003-UAT.md` document.
- What remains before the milestone is truly usable end-to-end: the operator-driven 360px manual UAT walkthrough recorded in `M003-UAT.md` (auto-mode cannot drive a real browser at 360; operator follow-up captured in the document). Per MEM142, slice can close on auto-mode's preparation; the UAT-COMPLETE checkbox is a follow-up that does not block `gsd_complete_slice`.

## Verification

- Runtime signals: 12 gate exit codes captured per-gate in slice summary (each command + exit code + relevant output tail). The polish-coverage Playwright spec from S05 remains the standing visual-regression surface for all 40 routes × 3 viewports.
- Inspection surfaces: `npx playwright test polish-coverage.spec.ts` from `frontend/`; the 7 grep gates run from worktree root; `cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build` from `frontend/`.
- Failure visibility: any reintroduction of legacy palette / `glass-*` / consumer-class surfaces as a non-zero exit on the corresponding grep gate (or as a build error from the deleted `@theme` block). Optional T02 grep-guard surfaces re-entry at `npm test` time.
- Redaction constraints: none — all output is build/lint/test stdout, no secrets traverse this slice.

## Tasks

- [x] **T01: Resolve autonomous-judgable IA deferrals; document human-judgment deferrals in M003-UAT.md** `est:1.5h`
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
  - Files: `frontend/src/components/admin/DangerActionPanel.tsx`, `frontend/src/pages/admin/SystemAdmin.tsx`, `frontend/src/pages/admin/UserManagement.tsx`, `frontend/src/pages/buildLists/ViewBuildLog.tsx`, `frontend/src/index.css`, `frontend/package.json`, `.gsd/milestones/M003/M003-UAT.md`
  - Verify: cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build && (npx playwright test polish-coverage.spec.ts --update-snapshots || npx playwright test polish-coverage.spec.ts) && git diff -- e2e/polish-coverage.spec.ts-snapshots/ | head -100 && cd .. && test -f .gsd/milestones/M003/M003-UAT.md && grep -c '^### #' .gsd/milestones/M003/M003-UAT.md | xargs test 3 -le

- [x] **T02: Extend vitest grep-guard to block raw-palette / glass-* / hand-rolled-primitive re-entry** `est:45m`
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
  - Files: `frontend/src/__tests__/no-legacy-primitives.test.ts`
  - Verify: cd frontend && npm test -- --run __tests__/no-legacy-primitives && npm run lint && npm run type-check

- [x] **T03: Run fresh 12-gate close gauntlet, finalize M003-UAT.md, and write S06-SUMMARY.md** `est:1.5h`
  Per the `verify-before-complete` skill, all gate evidence must be from this session — not citations to S05's table. Run each gate fresh, capture command + exit code + output tail, then finalize the milestone-close artifacts.

**Step 1: Run all 12 standing gates fresh.** Execute each from the worktree root unless noted; log command + exit code + relevant output tail to a structured location for the slice summary. Optional: write each stdout/stderr to `.gsd/milestones/M003/slices/S06/gauntlet/<gate-name>.txt` for durable evidence.

```bash
# Gates 1-7 (grep): exit 1 = pass (zero hits)
rg '(text|bg|border|ring|from|to|via)-(primary|neutral|emerald|indigo|amber|rose)-[0-9]' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/
rg 'text-accent-(emerald|amber|rose|purple)' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/
rg 'glass-(card|button)?' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/
rg 'className=.*\bglass\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/
rg 'var\(--(primary|neutral|accent|gradient)-' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/
rg '\b(btn-primary|btn-secondary|btn-outline|input-modern|card-interactive|card-table-container|skeleton|hero-gradient|shadow-glow|border-gradient)\b' frontend/src/{components,pages,contexts,hooks,api,lib,__tests__}/
rg -c '@theme|--primary-[0-9]|.glass-card|.btn-primary|.card-interactive|.input-modern|.text-gradient|.shadow-glow|.border-gradient|.skeleton|.hero-gradient' frontend/src/index.css

# Gates 8-12 (toolchain): exit 0 = pass
cd frontend && npm run type-check
cd frontend && npm run lint
cd frontend && npm test -- --run
cd frontend && npm run build
cd frontend && npx playwright test
```

**Step 2: Finalize `.gsd/milestones/M003/M003-UAT.md`.** T01 created the scaffold with priority-page table + 360px walkthrough checklist + 3 IA decision slots. Step 2 confirms all sections are populated, references are accurate (file:line refs match current code), and the document is operator-ready. Add a top-level summary block: 'M003 closed in auto-mode at <git short SHA>; operator UAT items below are non-blocking follow-ups; record verdicts inline and commit when complete.'

**Step 3: Write `S06-SUMMARY.md`.** Required sections (matches the S05 summary frontmatter shape):

- **Frontmatter:** `id: S06`, `parent: M003`, `provides:` (12 fresh gate evidence + M003-UAT.md scaffolded + 3 IA judgable items resolved + optional T02 grep-guard outcome), `requires:` (S01-S05 outputs), `affects:` (M003 close), `key_files:` (DangerActionPanel + UserManagement comment + ViewBuildLog conditional + M003-UAT.md + S06-SUMMARY.md + extended grep-guard if T02 landed), `key_decisions:` (the autonomous-vs-human split rationale + UserManagement #5(a) status-quo lock + ViewBuildLog prose-plugin verdict + T02 applied-or-deferred), `patterns_established:` (autonomous-IA-judgability split heuristic; M003-UAT.md document shape), `observability_surfaces:` (12 gates + polish-coverage spec + extended grep-guard if applicable), `drill_down_paths:` (T01-SUMMARY.md, T02-SUMMARY.md, T03-SUMMARY.md), `duration:`, `verification_result: passed`, `completed_at:`, `blocker_discovered: false`.
- **Body:** What Happened (T01/T02/T03 narrative); 12 Gate Evidence Table (with this-session command + exit code + output tail); IA Deferral Resolution (judgable items applied + human-judgment items documented); Verification (slice-level gates green); Operational Readiness (post-M003 standing signals); Deviations (if any); Known Limitations (operator UAT walkthrough is post-close follow-up per MEM142 wording — neutral phrasing only); Follow-ups (operator UAT verdicts; long-tail M002 follow-ups carried over; M004 backlog items if any); Files Created/Modified; Forward Intelligence (what M004 should know about the migration's standing surface).

**Step 4: Verification phrasing per MEM142.** The `gsd_complete_slice` content gate refuses any verification or UAT content matching `\b(status:\s*blocked|verification_result:\s*failed|slice is blocked|cannot complete|verification failed)\b`. Use neutral phrasing: 'auto-mode is unable to drive a real browser at 360px; operator follow-up captured in M003-UAT.md', NOT 'auto-mode cannot complete the live UAT walkthrough'. Same rule applies to any 'gate FAILS' phrasing — use 'if gate regresses below budget' instead.

**Step 5: Cascade-refresh review per MEM148.** Final clean Playwright pass (no `--update-snapshots`). If T01's prose-plugin adoption refreshed baselines, visually confirm each refreshed PNG via the Playwright HTML report and document in S06-SUMMARY.md.

Do NOT call `gsd_complete_slice` from this task — that is the slice closer's responsibility per MEM143 sequencing (slice closer calls `gsd_complete_slice` then `gsd_complete_milestone`). T03's role is to prepare the evidence; the closer agent runs the close calls.
  - Files: `.gsd/milestones/M003/slices/S06/gauntlet/`, `.gsd/milestones/M003/M003-UAT.md`, `.gsd/milestones/M003/slices/S06/S06-SUMMARY.md`
  - Verify: test -f .gsd/milestones/M003/M003-UAT.md && test -f .gsd/milestones/M003/slices/S06/S06-SUMMARY.md && grep -q 'verification_result: passed' .gsd/milestones/M003/slices/S06/S06-SUMMARY.md && grep -q '## What Happened\|## 12 Gate Evidence\|## Verification' .gsd/milestones/M003/slices/S06/S06-SUMMARY.md && cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build && npx playwright test

## Files Likely Touched

- frontend/src/components/admin/DangerActionPanel.tsx
- frontend/src/pages/admin/SystemAdmin.tsx
- frontend/src/pages/admin/UserManagement.tsx
- frontend/src/pages/buildLists/ViewBuildLog.tsx
- frontend/src/index.css
- frontend/package.json
- .gsd/milestones/M003/M003-UAT.md
- frontend/src/__tests__/no-legacy-primitives.test.ts
- .gsd/milestones/M003/slices/S06/gauntlet/
- .gsd/milestones/M003/slices/S06/S06-SUMMARY.md
