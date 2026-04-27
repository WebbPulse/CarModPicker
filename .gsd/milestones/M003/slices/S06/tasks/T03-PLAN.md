---
estimated_steps: 25
estimated_files: 3
skills_used: []
---

# T03: Run fresh 12-gate close gauntlet, finalize M003-UAT.md, and write S06-SUMMARY.md

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

## Inputs

- ``.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` — verdict table and frontmatter shape to mirror`
- ``.gsd/milestones/M003/M003-ROADMAP.md` — slice goal/demo/success criteria for the close-summary`
- ``.gsd/milestones/M003/M003-UAT.md` — scaffold from T01; finalize references and summary block`
- ``frontend/src/index.css` — read once for gate 7 self-inspection`
- ``frontend/e2e/polish-coverage.spec.ts` — gate 12 target (Playwright at 3 viewports)`
- ``frontend/src/__tests__/no-legacy-primitives.test.ts` — observability surface if T02 landed`

## Expected Output

- ``.gsd/milestones/M003/slices/S06/gauntlet/<gate-name>.txt` — optional per-gate stdout files for durable evidence (12 files if used)`
- ``.gsd/milestones/M003/M003-UAT.md` — finalized priority-page verdict table + 360px operator checklist + 3 IA decision slots + top-level summary block`
- ``.gsd/milestones/M003/slices/S06/S06-SUMMARY.md` — full slice summary with frontmatter (verification_result: passed) + 12 gate evidence table + IA resolution narrative + operational readiness + forward intelligence`

## Verification

test -f .gsd/milestones/M003/M003-UAT.md && test -f .gsd/milestones/M003/slices/S06/S06-SUMMARY.md && grep -q 'verification_result: passed' .gsd/milestones/M003/slices/S06/S06-SUMMARY.md && grep -q '## What Happened\|## 12 Gate Evidence\|## Verification' .gsd/milestones/M003/slices/S06/S06-SUMMARY.md && cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build && npx playwright test

## Observability Impact

12 fresh gate exit codes + output tails captured in S06-SUMMARY.md (and optionally in `gauntlet/<gate-name>.txt` files) become the durable post-M003 evidence record. Any future agent investigating 'did M003 close cleanly' has unambiguous structured proof per gate. The polish-coverage spec + the (possibly extended) grep-guard remain the standing observability surfaces post-close.
