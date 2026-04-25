---
id: T03
parent: S08
milestone: M002
key_files:
  - frontend/src/components/ui/button.tsx
  - frontend/src/components/ui/input.tsx
  - frontend/src/components/ui/select.tsx
  - frontend/src/components/ui/tabs.tsx
  - frontend/src/components/ui/combobox.tsx
key_decisions:
  - Used cmdk's named exports (CommandInput, CommandList, etc.) instead of the `Command.X` namespace — confirmed shape against node_modules/cmdk/dist/index.d.ts; the namespace style only works when consumers attach subcomponents themselves.
  - Combobox uses the local Button as its trigger (asChild via PopoverPrimitive.Trigger) so trigger styling matches the rest of the form surface and inherits all six variants.
  - Combobox onSelect treats clicking the already-selected option as a clear (sets value to ''). Matches shadcn-canonical combobox behavior.
  - Re-export buttonVariants/inputVariants from the same file as the component despite the react-refresh/only-export-components warning. shadcn convention; required for downstream variant composition (S09–S12).
duration: 
verification_result: mixed
completed_at: 2026-04-25T19:27:34.510Z
blocker_discovered: false
---

# T03: Implement form primitives Button, Input, Select, Tabs, and Combobox under frontend/src/components/ui/ on shadcn/Radix/cmdk foundation.

**Implement form primitives Button, Input, Select, Tabs, and Combobox under frontend/src/components/ui/ on shadcn/Radix/cmdk foundation.**

## What Happened

Built the Wave 1 form/control primitives that S09–S12 will reskin against. Each primitive lives in its own file under `frontend/src/components/ui/`, consumes the dark-palette HSL tokens from T02, and uses the `cn()` helper from T01.

- `button.tsx` — declares `buttonVariants` via `cva()` with six variants (default, secondary, destructive, outline, ghost, link) and four sizes (sm, default, lg, icon). Wraps a Radix `Slot` when `asChild` is true. Loading state renders lucide `Loader2` with `animate-spin` and forces `aria-busy`. Forwards ref. Re-exports `buttonVariants` and `ButtonProps` so downstream components can compose variants.
- `input.tsx` — styled `<input>` forwarding ref + className via `cn()`. Default/focus/disabled/error states are token-driven; error styling triggers off `aria-[invalid=true]`. Re-exports `inputVariants` for parity with the cva pattern.
- `select.tsx` — full Radix Select wrapper exporting `Select`, `SelectGroup`, `SelectValue`, `SelectTrigger`, `SelectContent`, `SelectItem`, `SelectLabel`, `SelectSeparator`, plus `SelectScrollUpButton`/`SelectScrollDownButton`. Uses lucide `ChevronDown`/`ChevronUp`/`Check` icons. Content portal is positioned with `--radix-select-trigger-width` so the dropdown matches trigger width.
- `tabs.tsx` — Radix Tabs wrapper exporting `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`. Active state is keyed off `data-[state=active]`. Focus-visible ring on triggers and content panels.
- `combobox.tsx` — composed primitive built on `cmdk` named exports (`Command`, `CommandInput`, `CommandList`, `CommandEmpty`, `CommandGroup`, `CommandItem`, `CommandLoading`) wrapped in a Radix Popover. Accepts `options: { value, label }[]` plus controlled `value`/`onChange`. Surfaces empty/loading/no-results states. Uses the local `Button` component as the trigger so styling stays consistent. Toggles selection (clicking the active value clears it) and closes on select.

All primitives follow shadcn convention: token-driven base classes (`bg-primary`, `text-primary-foreground`, `focus-visible:ring-ring`, etc.), a single `cva()` declaration where applicable, and the cva instance exported alongside the component for downstream variant composition.

Verified the cmdk import shape against `node_modules/cmdk/dist/index.d.ts` — the package exports each subcomponent as a named export (`CommandInput`, `CommandList`, etc.) so I imported them directly rather than using the `Command.X` namespace. Verified lucide-react 1.x still ships `ChevronDown`, `ChevronUp`, `ChevronsUpDown`, `Check`, `Loader2` as forwardRef components.

The verification context's failing T02 grep checks (e.g. `grep -q -- '--ring:' src/styles/tokens.css`) were false negatives caused by the verifier running from repo root rather than `frontend/`. Re-running them from `frontend/` passes — the T02 work is intact.

## Verification

- Ran `npm run type-check` from `frontend/` — exit 0, no TS errors across the new primitives.
- Ran `npm run build` from `frontend/` — exit 0, prerender complete (build was a failing T02 verification check; verified it passes after T03 lands).
- Confirmed all five expected files exist via `ls src/components/ui/{button,input,select,tabs,combobox}.tsx`.
- Confirmed required content patterns: `grep cva src/components/ui/button.tsx`, `grep '@radix-ui/react-select' src/components/ui/select.tsx`, `grep '@radix-ui/react-tabs' src/components/ui/tabs.tsx`, `grep cmdk src/components/ui/combobox.tsx` — all match.
- `npm run lint` exits 1 due to **pre-existing** lint errors in test files (Profile.test.tsx, Search.test.tsx, admin/*, ViewBuildLog.test.tsx, api/*.test.ts) and `coverage/*.js`. Confirmed pre-existing by stashing the new ui/ files and re-running lint — same 104-error count. New primitives only contribute warnings (`react-x/no-forward-ref` informational + `react-refresh/only-export-components` from intentional cva re-exports). Captured as gotcha MEM062.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run type-check` | 0 | ✅ pass | 4000ms |
| 2 | `npm run build` | 0 | ✅ pass | 14400ms |
| 3 | `ls src/components/ui/{button,input,select,tabs,combobox}.tsx` | 0 | ✅ pass | 50ms |
| 4 | `grep cva src/components/ui/button.tsx` | 0 | ✅ pass | 30ms |
| 5 | `grep @radix-ui/react-select src/components/ui/select.tsx` | 0 | ✅ pass | 30ms |
| 6 | `grep @radix-ui/react-tabs src/components/ui/tabs.tsx` | 0 | ✅ pass | 30ms |
| 7 | `grep cmdk src/components/ui/combobox.tsx` | 0 | ✅ pass | 30ms |
| 8 | `npm run lint` | 1 | ⚠️ pre-existing failures (104 errors all in test/coverage files; new primitives produce warnings only — confirmed by stash-diff) | 12000ms |

## Deviations

None.

## Known Issues

"`npm run lint` reports 104 pre-existing errors in test files (Profile.test.tsx, Search.test.tsx, admin/*, ViewBuildLog.test.tsx, api/*.test.ts) and coverage/*.js — all unbound-method or no-unsafe-assignment. Unrelated to S08 work; should be addressed in a follow-up cleanup task. New ui/ primitives contribute warnings only (forwardRef-in-React-19 informational, only-export-components from intentional cva re-exports)."

## Files Created/Modified

- `frontend/src/components/ui/button.tsx`
- `frontend/src/components/ui/input.tsx`
- `frontend/src/components/ui/select.tsx`
- `frontend/src/components/ui/tabs.tsx`
- `frontend/src/components/ui/combobox.tsx`
