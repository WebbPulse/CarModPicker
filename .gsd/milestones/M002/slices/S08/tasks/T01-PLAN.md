---
estimated_steps: 3
estimated_files: 5
skills_used: []
---

# T01: Install shadcn deps, add cn() util, scaffold ui/ + styles/ directories

Foundation task. Adds the runtime deps every primitive needs (Radix packages, class-variance-authority, clsx, tailwind-merge, lucide-react for icons, sonner for Toast, cmdk for Combobox). Adds `frontend/src/lib/utils.ts` exporting `cn(...inputs)` (the standard shadcn util that merges clsx + tailwind-merge — primitives use this everywhere). Creates empty `frontend/src/components/ui/` and `frontend/src/styles/` directories with `.gitkeep` placeholders so subsequent tasks have a clear landing zone. Does NOT yet add tokens or primitives — those land in T02/T03/T04.

**Why this task exists:** every primitive's `className` is built via `cn()`, and the Radix peer deps must resolve before primitives can be authored. Splitting this out keeps T02–T04 single-purpose.

**Why no Failure Modes / Load Profile / Negative Tests:** pure dev tooling — no runtime input, no shared resource, no external dependency at runtime.

## Inputs

- ``frontend/package.json``
- ``frontend/src/lib/sentry.ts``

## Expected Output

- ``frontend/package.json` (deps added: @radix-ui/react-dialog, @radix-ui/react-dropdown-menu, @radix-ui/react-tabs, @radix-ui/react-select, @radix-ui/react-toast, @radix-ui/react-slot, @radix-ui/react-popover, class-variance-authority, clsx, tailwind-merge, lucide-react, sonner, cmdk)`
- ``frontend/package-lock.json``
- ``frontend/src/lib/utils.ts` (exports `cn(...inputs: ClassValue[])` returning `twMerge(clsx(inputs))`)`
- ``frontend/src/components/ui/.gitkeep``
- ``frontend/src/styles/.gitkeep``

## Verification

cd frontend && npm install --silent && grep -q 'class-variance-authority' package.json && grep -q '@radix-ui/react-dialog' package.json && grep -q 'export function cn' src/lib/utils.ts && npm run type-check
