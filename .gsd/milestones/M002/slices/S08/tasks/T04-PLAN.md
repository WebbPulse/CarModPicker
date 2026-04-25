---
estimated_steps: 10
estimated_files: 5
skills_used: []
---

# T04: Implement overlay primitives: Dialog, DropdownMenu, Sheet, Toast

Wave 2 — the overlay/layout surface. All Radix-portal-based, all token-driven.

**Per-primitive spec:**
- `dialog.tsx`: built on `@radix-ui/react-dialog`. Exports `Dialog`, `DialogTrigger`, `DialogPortal`, `DialogOverlay` (backdrop with blur + fade animation), `DialogContent` (slide+scale animation, `max-w-lg` default, focus trap from Radix), `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`, `DialogClose`. Includes `<X>` close icon button (lucide-react) in top-right.
- `dropdown-menu.tsx`: built on `@radix-ui/react-dropdown-menu`. Exports `DropdownMenu`, `DropdownMenuTrigger`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuCheckboxItem`, `DropdownMenuRadioGroup`, `DropdownMenuRadioItem`, `DropdownMenuLabel`, `DropdownMenuSeparator`, `DropdownMenuShortcut`, `DropdownMenuSub`, `DropdownMenuSubContent`, `DropdownMenuSubTrigger`. Uses lucide `Check`, `ChevronRight`, `Circle` icons.
- `sheet.tsx`: built on `@radix-ui/react-dialog` (Radix has no separate Sheet — we wrap Dialog with side variants). `cva` controls side: top | right | bottom | left, with proper slide-in animation each direction. Same headed/footer/title/description sub-components as Dialog.
- `toast.tsx`: built on `sonner`. Exports a `Toaster` component (mount once at app root) plus a re-exported `toast` function. Theme `Toaster` via `theme="dark"` and `toastOptions={{ classNames: { ... } }}` keyed to tokens.

**Animation tokens:** all overlays use `data-[state=open]:animate-in` / `data-[state=closed]:animate-out` patterns from Tailwind v4 + tailwindcss-animate semantics. If `tailwindcss-animate` is not present, declare the keyframes inline in `tokens.css` (additive). Prefer the inline approach to avoid one more dependency.

**Failure modes:** Radix portal mount race during fast open/close — Radix handles it; verify no console errors during kitchen-sink rapid-open scenario (covered by T05's loading/disabled states).
**Load profile:** N/A — UI primitives.
**Negative tests:** disabled DropdownMenuItem must not fire on Enter/click — covered by Radix; we don't reimplement.

## Inputs

- ``frontend/src/lib/utils.ts``
- ``frontend/src/styles/tokens.css``
- ``frontend/src/components/ui/button.tsx``
- ``frontend/package.json``

## Expected Output

- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/dropdown-menu.tsx``
- ``frontend/src/components/ui/sheet.tsx``
- ``frontend/src/components/ui/toast.tsx``
- ``frontend/src/styles/tokens.css` (animation keyframes appended if not using tailwindcss-animate)`

## Verification

cd frontend && npm run type-check && for f in dialog dropdown-menu sheet toast; do test -f src/components/ui/$f.tsx || (echo "missing $f.tsx" && exit 1); done && grep -q '@radix-ui/react-dialog' src/components/ui/dialog.tsx && grep -q '@radix-ui/react-dropdown-menu' src/components/ui/dropdown-menu.tsx && grep -q '@radix-ui/react-dialog' src/components/ui/sheet.tsx && grep -q 'sonner' src/components/ui/toast.tsx && grep -q 'animate-in\|@keyframes' src/styles/tokens.css && npm run lint
