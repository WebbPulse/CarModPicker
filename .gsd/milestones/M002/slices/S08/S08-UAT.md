# S08: Design system spike + tokens + shadcn primitives + kitchen sink — UAT

**Milestone:** M002
**Written:** 2026-04-25T19:48:23.659Z

# S08 UAT — Design system substrate

**Scope:** verify the design-system foundation (tokens, primitives, kitchen-sink page, Playwright visual-regression harness) is in place and matches the M002 substrate contract that S09–S12 will consume.

## Preconditions

- Working tree at the S08 completion commit.
- `cd frontend && npm install` completed (Radix/shadcn deps resolved).
- Node 20+, Playwright browsers installed (`npx playwright install chromium` if first run).
- No backend running is required for the visual tests (the Vite proxy will log `ECONNREFUSED 127.0.0.1:8000` for `/api/*` — those proxy errors are expected and do not affect the kitchen sink).

## Test 1 — Tokens land in production CSS

**Steps:**
1. `cd frontend && npm run build`
2. `grep -E -- '--background:|--ring:|--radius:|\.bg-background' dist/assets/*.css`

**Expected:** Build exits 0. Grep matches all four patterns. The bundled CSS contains the dark-palette HSL channels (e.g. `--background:222 47% 6%`) and the Tailwind utilities they back.

## Test 2 — Nine primitives compile and type-check

**Steps:**
1. `cd frontend`
2. `for f in button input select tabs combobox dialog dropdown-menu sheet toast; do test -f src/components/ui/$f.tsx || echo "missing $f"; done`
3. `npm run type-check`

**Expected:** No "missing" lines printed. `tsc -b --noEmit` exits 0 with no diagnostics.

## Test 3 — Kitchen-sink page mounts in dev

**Steps:**
1. `cd frontend && npm run dev` (dev server on port 4000).
2. Open `http://localhost:4000/_kitchen-sink` in a browser.
3. Visually inspect the page.

**Expected:**
- Page loads on the new dark token background (`bg-background text-foreground`).
- 9 sections render with headings and `data-testid="section-{button,input,select,combobox,tabs,dialog,dropdown-menu,sheet,toast}"`.
- **Button section:** every variant (default/secondary/destructive/outline/ghost/link) × every size (sm/default/lg/icon) plus a row of disabled and a row of loading buttons (with `Loader2` spinner).
- **Input section:** default + focused (autofocus on one) + disabled + `aria-invalid` error variants with labels and helper text.
- **Select section:** a closed Select trigger and a separate Select with `defaultOpen` (Radix portals the open content).
- **Combobox section:** a populated 5-option list with a selected value, plus an empty-options instance demonstrating the no-results path.
- **Tabs section:** 3 triggers, one disabled; each tab's content panel renders.
- **Dialog section:** a Dialog open via `defaultOpen modal={false}` showing title/description/content/footer with a close (`X`) button.
- **DropdownMenu section:** open via `defaultOpen modal={false}` showing items + 2 CheckboxItems + separators + sub-menu trigger.
- **Sheet section:** open on the right via `defaultOpen modal={false}` with header/description/form inputs.
- **Toast section:** Toaster mounted; one persistent "Sample toast" visible (id `kitchen-sink-static`); clicking the demo button fires another toast.

## Test 4 — Production bundle excludes the kitchen-sink chunk

**Steps:**
1. `cd frontend && npx vite build --mode production`
2. `ls dist/assets | grep -i 'kitchen' || echo "no kitchen-sink chunk"`

**Expected:** Build succeeds. `grep -i 'kitchen'` returns nothing → "no kitchen-sink chunk" prints. The dev-only `import.meta.env.DEV` guard on the `lazy()` factory tree-shakes the chunk out.

## Test 5 — Playwright multi-viewport visual-regression suite

**Steps:**
1. `cd frontend && npm run test:e2e`

**Expected:** Exit code 0, "6 passed" reported (3 components.spec runs + 3 smoke.spec runs across mobile/tablet/desktop projects). No diff PNGs written under `test-results/`. (Some Vite proxy `ECONNREFUSED` lines for `/api/*` may appear in stderr — expected, no backend.)

**Edge:** if a baseline drifts (e.g. font-rendering nondeterminism after an OS update), Playwright writes a `*-actual.png` and `*-diff.png` under `test-results/` and the run exits non-zero. Inspect the diff; if intentional, re-run with `npm run test:e2e -- --update-snapshots` and commit the new baselines.

## Test 6 — Visual regression catches a real change

**Steps:**
1. Open `frontend/src/components/ui/button.tsx` and temporarily change the default variant background utility (e.g. `bg-primary` → `bg-destructive`).
2. `cd frontend && npm run test:e2e`
3. Revert the edit.

**Expected:** The 3 components.spec runs fail with pixel-diff PNGs written under `test-results/`. Each failure names the project (mobile/tablet/desktop) and ships a `kitchen-sink-visual-regression-1-{project}-linux-actual.png` + `*-diff.png`. After reverting and re-running, all 6 tests pass again. (This is informational — not run in CI; documents the intended failure path.)

## Test 7 — Smoke spec continues to work after token import

**Steps:**
1. `cd frontend && npm run test:e2e -- e2e/smoke.spec.ts`

**Expected:** All 3 project runs pass (smoke spec runs once per viewport project now that the project list expanded from 1 → 3).

## Test 8 — TypeScript exactOptionalPropertyTypes path

**Steps:**
1. `cd frontend && npm run type-check`

**Expected:** Exit 0. The DropdownMenuCheckboxItem `checked` and Sonner Toaster `className` conditional-spread workarounds keep `exactOptionalPropertyTypes: true` happy. (If a future primitive forgets the workaround, `tsc` will fail with "Type 'X | undefined' is not assignable to type 'X'" — apply MEM069 to fix.)

## Negative tests

- **Loaded primitives behave correctly when disabled:** click a `disabled` Button → no `onClick` fires (Radix/native handles it). Verified at the visual layer; explicit interaction test deferred to S09–S12 page-level tests.
- **Sonner dedup:** the kitchen-sink fires `toast('Sample toast', { id: 'kitchen-sink-static' })` inside `useEffect`. React strict mode invokes the effect twice; only one toast appears (sonner dedupes by id). Verify by counting toast nodes in the DOM — exactly one.
- **Multi-overlay coexistence:** Dialog + DropdownMenu + Sheet open simultaneously do NOT fight for focus or block pointer events on each other (`modal={false}` on each). Verify by clicking a Button outside any overlay — the click registers and the overlays stay open.

## Pass criteria

All 8 tests in this UAT exit 0 / show the expected behavior. Tests 5 and 7 are the load-bearing automated checks; the rest are visual confirmations on the dev kitchen-sink page or build artifacts.
