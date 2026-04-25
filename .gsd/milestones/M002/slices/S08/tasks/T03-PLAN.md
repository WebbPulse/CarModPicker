---
estimated_steps: 10
estimated_files: 5
skills_used: []
---

# T03: Implement form primitives: Button, Input, Select, Combobox, Tabs

Wave 1 of the primitive set — the form/control surface. Each primitive lives in its own file under `frontend/src/components/ui/`, follows shadcn conventions, and consumes tokens from T02 + `cn()` from T01.

**Per-primitive spec:**
- `button.tsx`: variants = default | secondary | destructive | outline | ghost | link; sizes = sm | default | lg | icon. Implements via `cva()`. States: default, hover, focus-visible (ring uses `--ring`), disabled, loading (renders spinner from lucide-react `Loader2` with `animate-spin`). Forwards ref. Accepts `asChild` via `@radix-ui/react-slot`.
- `input.tsx`: a styled `<input>` forwarding ref + className via `cn()`. States: default, focus (ring), disabled, error (`aria-invalid` style hook).
- `select.tsx`: built on `@radix-ui/react-select` — exports `Select`, `SelectTrigger`, `SelectValue`, `SelectContent`, `SelectItem`, `SelectGroup`, `SelectLabel`, `SelectSeparator`. Use lucide `ChevronDown`/`Check` icons.
- `tabs.tsx`: built on `@radix-ui/react-tabs` — exports `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`. States: active/inactive, focus, disabled.
- `combobox.tsx`: built on `cmdk` + `@radix-ui/react-popover` — exports `Combobox` accepting `options: { value, label }[]` plus controlled `value`/`onChange`. Surfaces command-palette UX with empty/loading/no-results states.

**Pattern (reuse in every file):** declare `cva()` with token-driven base classes (e.g. `bg-primary text-primary-foreground hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-ring`); export the component + the `cva` instance for downstream variant composition. No external state — all uncontrolled-friendly.

**Negative tests:** Each primitive's disabled state must not fire onClick/onChange. Verified at the kitchen-sink visual-regression layer (T05/T06) since these are stateless wrappers.

**Failure modes:** none — pure presentation. **Load profile:** none — render-only.

## Inputs

- ``frontend/src/lib/utils.ts``
- ``frontend/src/styles/tokens.css``
- ``frontend/src/index.css``
- ``frontend/package.json``

## Expected Output

- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/components/ui/input.tsx``
- ``frontend/src/components/ui/select.tsx``
- ``frontend/src/components/ui/tabs.tsx``
- ``frontend/src/components/ui/combobox.tsx``

## Verification

cd frontend && npm run type-check && for f in button input select tabs combobox; do test -f src/components/ui/$f.tsx || (echo "missing $f.tsx" && exit 1); done && grep -q 'cva' src/components/ui/button.tsx && grep -q '@radix-ui/react-select' src/components/ui/select.tsx && grep -q '@radix-ui/react-tabs' src/components/ui/tabs.tsx && grep -q 'cmdk' src/components/ui/combobox.tsx && npm run lint
