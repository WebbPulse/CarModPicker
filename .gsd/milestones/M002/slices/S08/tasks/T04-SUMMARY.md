---
id: T04
parent: S08
milestone: M002
key_files:
  - frontend/src/components/ui/dialog.tsx
  - frontend/src/components/ui/dropdown-menu.tsx
  - frontend/src/components/ui/sheet.tsx
  - frontend/src/components/ui/toast.tsx
  - frontend/src/styles/tokens.css
key_decisions:
  - Inlined animation keyframes + @utility declarations in tokens.css instead of installing tailwindcss-animate — matches the slice plan's explicit preference and avoids one more dependency. Captured the technique as MEM063 for future Tailwind v4 work.
  - Used conditional prop spread `{...(value !== undefined ? { value } : {})}` for `checked` on DropdownMenuCheckboxItem and `className` on Sonner Toaster to satisfy `exactOptionalPropertyTypes: true`. Captured as MEM064 — will recur in every Radix wrapper.
  - Sheet uses `cva()` with a `side` variant rather than four separate components, exposing default `side: 'right'` so the common case stays one-line. Mirrors shadcn-canonical Sheet API and lets consumers do `<SheetContent side="left">…</SheetContent>`.
duration: 
verification_result: mixed
completed_at: 2026-04-25T19:32:38.964Z
blocker_discovered: false
---

# T04: Implement overlay primitives Dialog, DropdownMenu, Sheet, and Toast on Radix + sonner with inline Tailwind v4 animation utilities.

**Implement overlay primitives Dialog, DropdownMenu, Sheet, and Toast on Radix + sonner with inline Tailwind v4 animation utilities.**

## What Happened

Built the Wave 2 overlay/layout primitives for the S08 design-system substrate. Each primitive lives in `frontend/src/components/ui/`, consumes the dark-palette HSL tokens from T02 via Tailwind utilities (`bg-popover`, `bg-background/80`, `border-border`, `text-popover-foreground`, etc.), and uses the `cn()` helper from T01.

- `dialog.tsx` — full Radix dialog wrapper exporting `Dialog`, `DialogTrigger`, `DialogPortal`, `DialogClose`, `DialogOverlay` (backdrop with `backdrop-blur-sm` + fade animation), `DialogContent` (slide+scale + fixed top-right close button with lucide `X` icon, `max-w-lg`), `DialogHeader`/`DialogFooter` layout helpers, `DialogTitle`, `DialogDescription`. Focus trap and a11y come for free from Radix.
- `dropdown-menu.tsx` — full Radix dropdown wrapper exporting `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuCheckboxItem` (with lucide `Check` indicator), `DropdownMenuRadioGroup`, `DropdownMenuRadioItem` (with lucide `Circle` indicator), `DropdownMenuLabel`, `DropdownMenuSeparator`, `DropdownMenuShortcut`, plus `DropdownMenuSub`, `DropdownMenuSubTrigger` (with lucide `ChevronRight`), `DropdownMenuSubContent`, `DropdownMenuPortal`, `DropdownMenuGroup`. `inset` prop on item/label/sub-trigger mirrors shadcn's canonical API.
- `sheet.tsx` — wraps `@radix-ui/react-dialog` with a `cva()`-driven `side` variant (top/right/bottom/left), each direction with the right slide-in/slide-out animations and border-edge styling. Default side is `right`. Same header/footer/title/description sub-components as Dialog. Includes the same close button as Dialog.
- `toast.tsx` — wraps sonner's `Toaster` with `theme="dark"` + `toastOptions.classNames` keyed to popover/foreground/destructive tokens. Re-exports `toast` so callers import everything from one place.

**Animation tokens.** No `tailwindcss-animate` is installed, and the slice plan explicitly preferred the inline approach. Appended to `frontend/src/styles/tokens.css`:
- `@keyframes enter` and `@keyframes exit` driven by `--tw-enter-*` / `--tw-exit-*` CSS custom properties so per-axis modifiers compose, exactly matching tailwindcss-animate's runtime model.
- `@utility animate-in` / `@utility animate-out` declarations (Tailwind v4 syntax) that bind the keyframes and reset the custom properties.
- `@utility fade-in-0`, `fade-out-0`, `fade-in-80`, `zoom-in-95`, `zoom-out-95`, `slide-in-from-{top,bottom,left,right}-2`, `slide-in-from-{top,bottom,left,right}` (full), `slide-out-to-{top,bottom,left,right}`, `duration-200`, `duration-300` — every utility name referenced by any T03/T04 overlay class string.

This retroactively fixes the existing `select.tsx` from T03, which already used `data-[state=open]:animate-in data-[state=closed]:fade-out-0` etc. but had no backing utilities — now those animations actually run.

**Type-check fix.** The frontend `tsconfig` has `exactOptionalPropertyTypes: true`, so `<DropdownMenuPrimitive.CheckboxItem checked={maybeUndefined} />` and `<SonnerToaster className={maybeUndefined} />` rejected `undefined` against required-ish prop types. Worked around with conditional spread (`{...(checked !== undefined ? { checked } : {})}`). Captured as MEM064 since this will recur whenever wrapping third-party components in this codebase.

## Verification

Ran the inlined task verification chain from `frontend/`:

1. `npm run type-check` — exit 0, no TS errors after the `exactOptionalPropertyTypes` workaround.
2. File-existence loop for dialog/dropdown-menu/sheet/toast — all four present.
3. `grep '@radix-ui/react-dialog' src/components/ui/dialog.tsx` — match.
4. `grep '@radix-ui/react-dropdown-menu' src/components/ui/dropdown-menu.tsx` — match.
5. `grep '@radix-ui/react-dialog' src/components/ui/sheet.tsx` — match (Sheet wraps Dialog per task spec).
6. `grep 'sonner' src/components/ui/toast.tsx` — match.
7. `grep 'animate-in\|@keyframes' src/styles/tokens.css` — match (`@keyframes enter`, `@keyframes exit`, `@utility animate-in`).
8. `npm run lint` — exit 1 due to **pre-existing** 104 errors in test files and `coverage/*.js` (same set documented in T03/MEM062). New T04 files contribute warnings only (`react-x/no-forward-ref` informational + intentional `react-refresh/only-export-components` from `sheetVariants` cva re-export and `toast` re-export — same pattern accepted in T03).
9. Bonus: `npm run build` — exit 0, prerender complete; confirms the new `@utility` declarations parse cleanly under Tailwind v4 and the production CSS bundle includes the animation utilities.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `npm run type-check` | 0 | ✅ pass | 4000ms |
| 2 | `for f in dialog dropdown-menu sheet toast; do test -f src/components/ui/$f.tsx; done` | 0 | ✅ pass | 50ms |
| 3 | `grep -q '@radix-ui/react-dialog' src/components/ui/dialog.tsx` | 0 | ✅ pass | 30ms |
| 4 | `grep -q '@radix-ui/react-dropdown-menu' src/components/ui/dropdown-menu.tsx` | 0 | ✅ pass | 30ms |
| 5 | `grep -q '@radix-ui/react-dialog' src/components/ui/sheet.tsx` | 0 | ✅ pass | 30ms |
| 6 | `grep -q 'sonner' src/components/ui/toast.tsx` | 0 | ✅ pass | 30ms |
| 7 | `grep -q 'animate-in\|@keyframes' src/styles/tokens.css` | 0 | ✅ pass | 30ms |
| 8 | `npm run lint` | 1 | ⚠️ pre-existing failures (104 errors all in test/coverage files; new T04 primitives produce warnings only — same pattern as T03/MEM062) | 12000ms |
| 9 | `npm run build` | 0 | ✅ pass (Tailwind v4 accepts @utility declarations; prerender succeeded) | 14500ms |

## Deviations

None.

## Known Issues

npm run lint still reports the same 104 pre-existing errors in test/coverage files documented in T03/MEM062 — unrelated to S08, should be cleaned up in a follow-up. New T04 primitives only produce informational warnings (forwardRef-in-React-19 + the intentional non-component re-exports from sheet.tsx and toast.tsx, matching the shadcn convention codified in MEM061).

## Files Created/Modified

- `frontend/src/components/ui/dialog.tsx`
- `frontend/src/components/ui/dropdown-menu.tsx`
- `frontend/src/components/ui/sheet.tsx`
- `frontend/src/components/ui/toast.tsx`
- `frontend/src/styles/tokens.css`
