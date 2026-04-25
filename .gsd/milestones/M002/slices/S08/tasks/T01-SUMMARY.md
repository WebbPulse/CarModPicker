---
id: T01
parent: S08
milestone: M002
key_files:
  - frontend/package.json
  - frontend/package-lock.json
  - frontend/src/lib/utils.ts
  - frontend/src/components/ui/.gitkeep
  - frontend/src/styles/.gitkeep
key_decisions:
  - Accepted lucide-react 1.x — npm registry confirms 0.x line is retired; icon imports remain backward-compatible.
  - Used npm install with no version pins so resolver picks React 19-compatible Radix versions automatically (Radix dialog 1.1.15, dropdown-menu 2.1.16, etc.).
duration: 
verification_result: passed
completed_at: 2026-04-25T19:18:36.818Z
blocker_discovered: false
---

# T01: Add shadcn/Radix runtime deps, cn() util, and scaffold frontend ui/ + styles/ directories

**Add shadcn/Radix runtime deps, cn() util, and scaffold frontend ui/ + styles/ directories**

## What Happened

Foundation task for the M002/S08 design-system substrate. Installed the runtime deps every primitive in T03/T04 will depend on: 7 Radix packages (`@radix-ui/react-{dialog,dropdown-menu,tabs,select,toast,slot,popover}`), the className composition trio (`class-variance-authority`, `clsx`, `tailwind-merge`), `lucide-react` (icons), `sonner` (Toast), and `cmdk` (Combobox). Resolved versions: Radix dialog 1.1.15, dropdown-menu 2.1.16, popover 1.1.15, select 2.2.6, slot 1.2.4, tabs 1.1.13, toast 1.2.15; cva 0.7.1, clsx 2.1.1, tailwind-merge 3.5.0, lucide-react 1.11.0, sonner 2.0.7, cmdk 1.1.1.\n\nAdded the standard shadcn `cn()` util at `frontend/src/lib/utils.ts` — `twMerge(clsx(inputs))` with `ClassValue[]` typing — exactly the contract every primitive in T03/T04 will import. Created landing-zone directories `frontend/src/components/ui/` and `frontend/src/styles/` with `.gitkeep` placeholders so subsequent tasks have an obvious place to drop primitives and tokens.\n\nNoted one surprise: `lucide-react` resolved to `^1.11.0` — npm registry confirms this is the current major (the 0.x line was retired). Captured as MEM060 so future tasks don't spend time second-guessing it. No code changes needed since the icon import API is unchanged.\n\nNo runtime behavior added — pure dev tooling, so no Failure Modes / Load Profile / Negative Tests sections apply per the task plan.

## Verification

Ran the full verification command from the task plan: `cd frontend && npm install --silent && grep -q 'class-variance-authority' package.json && grep -q '@radix-ui/react-dialog' package.json && grep -q 'export function cn' src/lib/utils.ts && npm run type-check`. All steps succeeded — npm install resolved with no warnings shown, all three greps matched, and `tsc -b --noEmit` exited 0 with no diagnostics. Slice-level verification (Playwright, kitchen-sink mount) is not yet runnable until T02–T05 complete and is correctly deferred to the final task per the slice plan.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm install --silent && grep -q 'class-variance-authority' package.json && grep -q '@radix-ui/react-dialog' package.json && grep -q 'export function cn' src/lib/utils.ts && npm run type-check` | 0 | ✅ pass | 18000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/lib/utils.ts`
- `frontend/src/components/ui/.gitkeep`
- `frontend/src/styles/.gitkeep`
