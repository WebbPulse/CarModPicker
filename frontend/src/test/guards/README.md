# Regression Guard Tests

These tests are **lint-style regression guards**, not ordinary unit tests.
They do not import application source files — instead they scan the source
tree with `globSync` + `readFileSync` and assert that every matching file
satisfies a repo-wide invariant. Because they never execute production
code, they contribute **zero coverage** and are neutral to the Phase 8
coverage thresholds.

Relocated to `src/test/guards/` in Phase 8 plan 08-01 per decision **D-17**,
to keep the root `src/test/` directory focused on test infrastructure
(setup, providers, mocks, utilities) rather than mixing it with lint
guards. Each file's logic is unchanged — the `resolve(__dirname, '..', '..')`
path math still resolves to `frontend/`, and the allowlist entries still
point at the guard files themselves.

## Guards in this directory

- **`no-process-env.test.ts` (FE-02)** — forbids `process.env.*` in any
  frontend browser source outside a tiny allowlist. Browser code must use
  `import.meta.env.VITE_*` so Vite can do build-time substitution.

- **`no-legacy-gradient.test.ts` (FE-05)** — forbids the Tailwind v3 legacy
  `bg-gradient-to-*` class prefix in frontend source. Tailwind v4 uses
  different gradient syntax; this guard catches stray v3-era classnames
  surviving migration.

- **`extension-content-type.test.ts` (QUAL-06)** — parses every `fetch(...)`
  call site in `chrome-extension/src/**/*.ts` and asserts POST bodies
  either set `Content-Type: application/json` or send `FormData`. Required
  because FastAPI 0.132+ strictly rejects typeless POST bodies.

## Running

These guards run as part of `npm test`. Because they are not tied to any
source file, they never need to be re-run when source changes — they simply
walk the tree and assert on textual content. A guard failure means a repo
invariant was violated; fix the offending source file (or deliberately
update the allowlist + guard test together in the same commit).
