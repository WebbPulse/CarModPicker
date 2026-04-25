---
estimated_steps: 18
estimated_files: 2
skills_used: []
---

# T05: Build _KitchenSink page rendering every primitive in every state and wire dev-only route

The kitchen-sink is the canvas the visual-regression spec photographs. Every primitive from T03+T04 must be present in every meaningful state.

**Page structure (`frontend/src/pages/_KitchenSink.tsx`):**
- Top-level `<main className="bg-background text-foreground min-h-screen p-8 space-y-12">` so screenshot baseline is on the new tokenized background.
- One `<section data-testid="section-button">` per primitive, with `<h2>` heading + a grid of variants/states.
- **Button section:** every variant (default/secondary/destructive/outline/ghost/link) × every size (sm/default/lg/icon) + a row showing disabled and loading states.
- **Input section:** default, focused (use `autoFocus` on one), disabled, error (`aria-invalid="true"`), with a label + helper text.
- **Select section:** open variant (use `defaultOpen` on one Select; Radix portals it but Playwright can capture).
- **Combobox section:** rendered with sample 5-option list, one with no results state (empty input scenario shown statically beside it).
- **Tabs section:** TabsList with 3 triggers + content rendered for each, one disabled trigger.
- **Dialog section:** an open Dialog rendered via `defaultOpen={true}` so it's visible in the snapshot.
- **DropdownMenu section:** open via `defaultOpen={true}` showing items + checkbox + separator + sub-menu.
- **Sheet section:** open Sheet on the right side via `defaultOpen={true}`.
- **Toast section:** mount the `<Toaster />` once and on page mount call `toast("Sample toast")` inside a `useEffect` so the snapshot captures it. Also render a button that fires another toast for interactive testing.

**Routing (`frontend/src/App.tsx`):**
Add the import and route guarded by `import.meta.env.DEV` so the route — and therefore the entire `_KitchenSink.tsx` chunk — is excluded from production builds. Use `lazyWithReload` consistent with sibling lazy imports. Path: `/_kitchen-sink`. No header/footer wrapping (so screenshot baseline is the kitchen sink itself).

**Why dev-only:** kitchen sink is internal tooling; shipping it to prod would bloat the bundle and surface raw component states to users.

**Failure modes:** Toast `useEffect` firing twice in React strict mode — sonner dedupes by id, so call with explicit id `'kitchen-sink-static'`. Radix portal mounting outside the section root means screenshot must be `fullPage: true` (handled in T06).
**Load profile / negative tests:** N/A.

## Inputs

- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/components/ui/input.tsx``
- ``frontend/src/components/ui/select.tsx``
- ``frontend/src/components/ui/tabs.tsx``
- ``frontend/src/components/ui/combobox.tsx``
- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/dropdown-menu.tsx``
- ``frontend/src/components/ui/sheet.tsx``
- ``frontend/src/components/ui/toast.tsx``
- ``frontend/src/App.tsx``
- ``frontend/src/utils/lazyWithReload.ts``

## Expected Output

- ``frontend/src/pages/_KitchenSink.tsx``
- ``frontend/src/App.tsx` (imports `_KitchenSink` lazily, wraps route in `import.meta.env.DEV` guard)`

## Verification

cd frontend && npm run type-check && grep -q 'data-testid="section-button"' src/pages/_KitchenSink.tsx && grep -qE 'data-testid="section-(input|select|combobox|tabs|dialog|dropdown-menu|sheet|toast)"' src/pages/_KitchenSink.tsx && grep -q '_kitchen-sink' src/App.tsx && grep -q 'import.meta.env.DEV' src/App.tsx && npm run lint

## Observability Impact

Kitchen-sink failure paths (Toast mount race, missing portal root) surface as React console errors in dev. The Playwright spec in T06 captures `page.on('pageerror')` so any runtime exception during the screenshot run fails the test loud.
