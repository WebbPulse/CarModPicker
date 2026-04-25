# S08: Design system spike + tokens + shadcn primitives + kitchen sink

**Goal:** Land the design-system substrate: install shadcn-compatible tooling, lock dark-mode CSS-variable tokens, ship 9 Radix-based primitives under `frontend/src/components/ui/`, expose a dev-only kitchen-sink page that exercises every primitive in every state, and wire a Playwright visual-regression spec at three breakpoints. This is the foundation S09–S12 will reskin against.
**Demo:** Open the kitchen-sink page in dev — every primitive (Button, Dialog, DropdownMenu, Combobox, Toast, Tabs, Input, Select, Sheet) renders in every state (default, hover, focus, disabled, loading, error) under the new tokens. Run npm run test:e2e — components.spec.ts kitchen-sink screenshots green at mobile/tablet/desktop. playwright.config.ts and frontend/e2e/smoke.spec.ts committed.

## Must-Haves

- `frontend/src/styles/tokens.css` defines a complete dark-palette token layer (color/spacing/type/radii/shadows) consumed by Tailwind v4 via `@theme` and by primitive class strings via CSS variables.
- `frontend/src/components/ui/{button,dialog,dropdown-menu,combobox,toast,tabs,input,select,sheet}.tsx` exist, are Radix-based, and each render correctly across default/hover/focus/disabled/loading/error states where applicable.
- `frontend/src/pages/_KitchenSink.tsx` mounts in dev at `/_kitchen-sink`, renders every primitive in every state, and is reachable in `npm run dev`.
- `frontend/playwright.config.ts` declares three projects (mobile/tablet/desktop viewports) and is committed.
- `frontend/e2e/components.spec.ts` runs `toHaveScreenshot()` against the kitchen-sink page at all three breakpoints; baseline snapshots committed under `frontend/e2e/components.spec.ts-snapshots/`.
- `frontend/e2e/smoke.spec.ts` continues to pass.
- `npm run test:e2e` exits 0 locally with pixel-diff threshold ~0.2%.
- **Threat Surface:** N/A — dev-only kitchen sink page is gated behind `import.meta.env.DEV`. No new auth, user input, or data exposure. Primitives forward props to Radix which handles a11y/keyboard nav.
- **Requirement Impact:**
- Requirements implemented: R011 (token layer), R012 (primitives under `components/ui/`), R013 (kitchen-sink visual-regression spec).
- Re-verify after shipping: existing visual smoke (`smoke.spec.ts`) — must still pass since tokens.css is additive (doesn't touch the global `index.css` body class chain).
- Decisions revisited: D003 (substrate), D006 (visual-regression strategy) — both reaffirmed by execution.

## Proof Level

- This slice proves: - This slice proves: contract (primitive surface + visual-regression harness) and operational (kitchen sink mounts in dev).
- Real runtime required: yes — Playwright spawns the dev server and renders the kitchen sink against real Vite + Tailwind output.
- Human/UAT required: no — visual regression is the bar; baseline snapshots are the human-approved truth.

## Integration Closure

- Upstream surfaces consumed: nothing (foundation slice).
- New wiring introduced: dev-only `/_kitchen-sink` route in `App.tsx` (gated by `import.meta.env.DEV` so production bundle excludes it); `tokens.css` imported once from `index.css`; `cn()` utility in `frontend/src/lib/utils.ts` consumed by every primitive.
- What remains before milestone is usable end-to-end: S09 (build-list), S10 (parts catalog), S11 (admin), S12 (ripple) reskin onto these primitives. S08 alone is invisible to end users.

## Verification

- Runtime signals: Playwright HTML reporter at `frontend/playwright-report/` on failed runs; pixel-diff PNGs alongside snapshots on regression.
- Inspection surfaces: `npm run test:e2e -- --reporter=list` for terminal output; `npm run test:e2e:ui` for interactive trace; `/_kitchen-sink` in dev for live primitive state inspection.
- Failure visibility: Playwright trace + diff image written to `test-results/` per failed test, including viewport size.
- Redaction constraints: none — kitchen sink renders only synthetic content.

## Tasks

- [x] **T01: Install shadcn deps, add cn() util, scaffold ui/ + styles/ directories** `est:30m`
  Foundation task. Adds the runtime deps every primitive needs (Radix packages, class-variance-authority, clsx, tailwind-merge, lucide-react for icons, sonner for Toast, cmdk for Combobox). Adds `frontend/src/lib/utils.ts` exporting `cn(...inputs)` (the standard shadcn util that merges clsx + tailwind-merge — primitives use this everywhere). Creates empty `frontend/src/components/ui/` and `frontend/src/styles/` directories with `.gitkeep` placeholders so subsequent tasks have a clear landing zone. Does NOT yet add tokens or primitives — those land in T02/T03/T04.

**Why this task exists:** every primitive's `className` is built via `cn()`, and the Radix peer deps must resolve before primitives can be authored. Splitting this out keeps T02–T04 single-purpose.

**Why no Failure Modes / Load Profile / Negative Tests:** pure dev tooling — no runtime input, no shared resource, no external dependency at runtime.
  - Files: `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/lib/utils.ts`, `frontend/src/components/ui/.gitkeep`, `frontend/src/styles/.gitkeep`
  - Verify: cd frontend && npm install --silent && grep -q 'class-variance-authority' package.json && grep -q '@radix-ui/react-dialog' package.json && grep -q 'export function cn' src/lib/utils.ts && npm run type-check

- [ ] **T02: Define dark-palette token layer in styles/tokens.css and wire into Tailwind v4 @theme** `est:1h`
  Land the CSS-variable token substrate that every primitive and every reskinned page will consume. Per D003 + R011, the dark palette is locked in M002; light mode is deferred unless it falls out free.

**Token categories required:** color (background, foreground, card, popover, primary, secondary, muted, accent, destructive, border, input, ring), spacing scale (radius mainly — `--radius-sm/md/lg/xl`), typography (font-sans + font-mono families, `--font-size-*` scale already provided by Tailwind), shadows (`--shadow-sm/md/lg/xl`), z-index layers (`--z-dropdown/modal/toast`).

**Implementation:** create `frontend/src/styles/tokens.css` with `:root` block declaring all tokens (dark values). Use shadcn's standard naming so future shadcn CLI imports work without translation: `--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`, `--border`, `--input`, `--ring`, `--radius`. Values express HSL channels (e.g. `222 47% 11%`) so consumers can wrap with `hsl(var(--background) / <alpha>)`.

In the same file, extend `@theme` so Tailwind utilities like `bg-background`, `text-foreground`, `border-border` resolve. Mirror existing `index.css` `@theme` block style.

`@import './styles/tokens.css'` from `frontend/src/index.css` immediately after the existing `@import 'tailwindcss'` line. Do NOT remove the existing `--primary-*/--neutral-*/--accent-*` blocks — they are still consumed by hand-rolled `components/common/` until S12. New tokens are additive.

**Why no Failure Modes etc:** no runtime — pure CSS.
  - Files: `frontend/src/styles/tokens.css`, `frontend/src/index.css`
  - Verify: cd frontend && grep -q '@import .\./styles/tokens.css' src/index.css && grep -q -- '--background:' src/styles/tokens.css && grep -q -- '--ring:' src/styles/tokens.css && grep -q -- '--radius:' src/styles/tokens.css && grep -q '@theme' src/styles/tokens.css && npm run build > /tmp/s08-t02-build.log 2>&1 && grep -q '\.bg-background\|--background' dist/assets/*.css

- [ ] **T03: Implement form primitives: Button, Input, Select, Combobox, Tabs** `est:2h`
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
  - Files: `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/src/components/ui/select.tsx`, `frontend/src/components/ui/tabs.tsx`, `frontend/src/components/ui/combobox.tsx`
  - Verify: cd frontend && npm run type-check && for f in button input select tabs combobox; do test -f src/components/ui/$f.tsx || (echo "missing $f.tsx" && exit 1); done && grep -q 'cva' src/components/ui/button.tsx && grep -q '@radix-ui/react-select' src/components/ui/select.tsx && grep -q '@radix-ui/react-tabs' src/components/ui/tabs.tsx && grep -q 'cmdk' src/components/ui/combobox.tsx && npm run lint

- [ ] **T04: Implement overlay primitives: Dialog, DropdownMenu, Sheet, Toast** `est:2h`
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
  - Files: `frontend/src/components/ui/dialog.tsx`, `frontend/src/components/ui/dropdown-menu.tsx`, `frontend/src/components/ui/sheet.tsx`, `frontend/src/components/ui/toast.tsx`, `frontend/src/styles/tokens.css`
  - Verify: cd frontend && npm run type-check && for f in dialog dropdown-menu sheet toast; do test -f src/components/ui/$f.tsx || (echo "missing $f.tsx" && exit 1); done && grep -q '@radix-ui/react-dialog' src/components/ui/dialog.tsx && grep -q '@radix-ui/react-dropdown-menu' src/components/ui/dropdown-menu.tsx && grep -q '@radix-ui/react-dialog' src/components/ui/sheet.tsx && grep -q 'sonner' src/components/ui/toast.tsx && grep -q 'animate-in\|@keyframes' src/styles/tokens.css && npm run lint

- [ ] **T05: Build _KitchenSink page rendering every primitive in every state and wire dev-only route** `est:1.5h`
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
  - Files: `frontend/src/pages/_KitchenSink.tsx`, `frontend/src/App.tsx`
  - Verify: cd frontend && npm run type-check && grep -q 'data-testid="section-button"' src/pages/_KitchenSink.tsx && grep -qE 'data-testid="section-(input|select|combobox|tabs|dialog|dropdown-menu|sheet|toast)"' src/pages/_KitchenSink.tsx && grep -q '_kitchen-sink' src/App.tsx && grep -q 'import.meta.env.DEV' src/App.tsx && npm run lint

- [ ] **T06: Configure Playwright multi-viewport projects and ship components.spec.ts visual-regression suite** `est:1h`
  Slice's objective stopping condition (R013, D006). Updates `playwright.config.ts` to declare three viewport projects, then writes `e2e/components.spec.ts` that visits the kitchen sink at each breakpoint, settles state, and runs `toHaveScreenshot()`.

**playwright.config.ts changes:**
- Replace the single `chromium` project with three: `mobile` (375×667, iPhone SE), `tablet` (768×1024, iPad), `desktop` (1280×800, Desktop Chrome). Each entry uses `...devices['<name>']` overrides only where needed; viewport explicitly set to the listed dimensions.
- Add `expect.toHaveScreenshot.maxDiffPixelRatio: 0.002` (0.2%, per R013) and `expect.toHaveScreenshot.animations: 'disabled'`.
- Keep `webServer` block (already present) and `baseURL` (already present).
- Bump `timeout` per test to 30_000ms to absorb slow first-paint on cold dev server.

**e2e/components.spec.ts:**
- Single test: `'kitchen-sink visual regression'` per project.
- `await page.goto('/_kitchen-sink')`.
- `await page.waitForLoadState('networkidle')`.
- `await page.evaluate(() => document.fonts.ready)` so font metric is stable across runs.
- A small `await page.waitForTimeout(300)` to let toast/dropdown/dialog enter animations settle (animations are disabled in expect, but mount-time effects need a tick).
- `await expect(page).toHaveScreenshot({ fullPage: true })` — Playwright auto-keys snapshot by project name, producing `components.spec.ts-snapshots/kitchen-sink-visual-regression-1-{mobile,tablet,desktop}-linux.png`.
- Listen for `pageerror`: `page.on('pageerror', err => { throw err; })` at top of test so any runtime React error surfaces.

**Baseline generation:** First task run will fail with 'no baseline'. Re-run with `--update-snapshots` to capture. Commit the resulting PNGs.

**Threat-surface considerations:** N/A — dev tooling.
**Failure modes:** flake from animations/fonts/network → mitigated above. Snapshot drift from minor anti-aliasing → 0.2% threshold.
**Negative tests:** Run with the kitchen sink intentionally broken (e.g. delete a primitive import) and confirm test fails with a clear error — not in CI but verified manually before shipping.
**Load profile:** Playwright runs serially per project; `webServer.reuseExistingServer` keeps dev startup amortized.
  - Files: `frontend/playwright.config.ts`, `frontend/e2e/components.spec.ts`, `frontend/e2e/components.spec.ts-snapshots/`
  - Verify: cd frontend && grep -q "name: 'mobile'" playwright.config.ts && grep -q "name: 'tablet'" playwright.config.ts && grep -q "name: 'desktop'" playwright.config.ts && grep -q 'maxDiffPixelRatio' playwright.config.ts && grep -q '_kitchen-sink' e2e/components.spec.ts && grep -q 'toHaveScreenshot' e2e/components.spec.ts && npm run test:e2e -- --update-snapshots > /tmp/s08-t06-snap.log 2>&1 && npm run test:e2e > /tmp/s08-t06-run.log 2>&1

## Files Likely Touched

- frontend/package.json
- frontend/package-lock.json
- frontend/src/lib/utils.ts
- frontend/src/components/ui/.gitkeep
- frontend/src/styles/.gitkeep
- frontend/src/styles/tokens.css
- frontend/src/index.css
- frontend/src/components/ui/button.tsx
- frontend/src/components/ui/input.tsx
- frontend/src/components/ui/select.tsx
- frontend/src/components/ui/tabs.tsx
- frontend/src/components/ui/combobox.tsx
- frontend/src/components/ui/dialog.tsx
- frontend/src/components/ui/dropdown-menu.tsx
- frontend/src/components/ui/sheet.tsx
- frontend/src/components/ui/toast.tsx
- frontend/src/pages/_KitchenSink.tsx
- frontend/src/App.tsx
- frontend/playwright.config.ts
- frontend/e2e/components.spec.ts
- frontend/e2e/components.spec.ts-snapshots/
