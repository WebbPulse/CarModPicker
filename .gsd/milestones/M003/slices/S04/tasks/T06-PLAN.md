---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T06: Pass-1 deletion: @theme palette + :root legacy block + .glass* + .btn-* + .card* + .input-modern + legacy responsive @media blocks

The structural delete. With T01–T05 complete, every consumer of the about-to-be-deleted classes either (a) no longer exists in `frontend/src/`, (b) has migrated to a `<Button>` primitive (T02), (c) has dropped the legacy class (T03), or (d) has its color resolution rewired through `hsl(var(--*))` (T05). Delete these blocks from `frontend/src/index.css` in a single edit pass: lines 7–37 (the `@theme { --color-primary-... --color-accent-purple }` palette mirror); lines 39–99 (the `:root { --primary-... --gradient-... --glass-... }` legacy variables); lines 295–381 (`.glass`, `.glass:hover`, `.glass-card`, `.glass-card.card-interactive`, `.glass-card.card-interactive:hover`, `.glass-button`, `.glass-button::before`, `.glass-button:hover::before`, `.glass-button:hover`); lines 383–482 (`.btn-primary`, `.btn-primary::before`, `.btn-primary:hover::before`, `.btn-primary:hover`, `.btn-secondary`, `.btn-secondary:hover`, `.btn-outline`, `.btn-outline::before`, `.btn-outline:hover::before`, `.btn-outline:hover`); lines 484–537 (`.card`, `.card::before`, `.card-interactive`, `.card-interactive::before`, `.card-interactive:hover::before`, `.card-interactive:hover`); lines 539–582 (`.global-parts-table-scroll-layer` and `.card-table-container` rules — Read first to confirm exact scope); lines 584–616 (`.input-modern`, `.input-modern:focus`, `.input-modern::placeholder`, `.input-modern:focus::placeholder`); legacy responsive `@media (max-width: 768px) { .glass / .card / .btn-* }` and `@media (max-width: 480px) { .card / .btn-* }` blocks — Read first (likely lines 668-698 per research, but verify) and delete only the rules whose selectors target the just-deleted classes. PRESERVE `* { box-sizing }`, the `body` block as rewritten in T05, scrollbar styling, the rewritten `*:focus-visible` and `::selection` rules from T05, `.main-content .container`, `.tile-grid`, `.tile-grid-compact`. Run `cd frontend && npm run build` — must succeed (the `vite build` exit 0 is the load-bearing structural proof per R061). If any class fails to resolve at build time: STOP, identify the consumer file from the build error, fix in place (migrate to semantic token), retry. Single atomic commit per R053 with narrative explaining the pass-1 scope and that build success is the proof.

## Inputs

- `frontend/src/index.css`
- `frontend/src/styles/tokens.css`

## Expected Output

- `frontend/src/index.css`

## Verification

cd frontend && npm run build 2>&1 | tail -20 && rg -c '@theme' frontend/src/index.css; test $? -eq 1 && rg -c 'glass-card|glass-button|btn-primary|btn-secondary|btn-outline|card-interactive|card-table-container|input-modern' frontend/src/index.css; test $? -eq 1

## Observability Impact

Signals added/changed: the build IS the signal — vite build exit code is the canonical structural enforcement. How a future agent inspects this: `cd frontend && npm run build` succeeds = pass; failure names the unresolved class and consumer file. Failure state exposed: any reintroduction of a deleted class becomes a hard build error at PR time, replacing the soft grep gate the project relied on through S01–S03.
