---
id: T01
parent: S02
milestone: M003
key_files:
  - frontend/src/pages/Home.tsx
  - frontend/src/pages/authentication/Login.tsx
  - frontend/src/pages/authentication/Register.tsx
  - frontend/src/pages/authentication/ExtensionAuth.tsx
  - frontend/src/pages/NotFound.tsx
  - frontend/src/pages/PrivacyPolicy.tsx
  - frontend/src/pages/TermsOfService.tsx
key_decisions:
  - Used <Card variant="glass"> at Home.tsx:385 since the site is already a <Card> and the ui/Card cva exposes the glass variant directly (no import change needed).
  - Inlined `border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5` for the 6 raw-<div> sites instead of converting to <Card> — preserves the divs' bespoke padding shapes (p-12, p-8 md:p-12) and keeps the diff className-only.
duration: 
verification_result: passed
completed_at: 2026-04-26T21:49:25.230Z
blocker_discovered: false
---

# T01: refactor(palette): swap glass-card consumers in 7 pages to Card variant or inline tokenized surface

**refactor(palette): swap glass-card consumers in 7 pages to Card variant or inline tokenized surface**

## What Happened

Migrated all 7 `glass-card` consumers listed in the T01 mapping table off the legacy `.glass-card` utility. Home.tsx:385 was already a `<Card>` and converted to `<Card variant="glass">` (the M002/S08 ui/Card primitive already exposes a `glass` variant — confirmed in `frontend/src/components/ui/card.tsx:9-15`). The 6 raw-`<div>` consumers (Login, Register, ExtensionAuth, NotFound, PrivacyPolicy, TermsOfService) received the inline tokenized equivalent `border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5`, prepended verbatim to each existing className (preserving the trailing `rounded-2xl p-* animate-*` chrome). No imports were added to the div consumers — the diff is className-only as the plan required.

Header.tsx:156 still contains a `glass-card` reference; that consumer is explicitly assigned to T02 ("Migrate `glass`/`glass-button` consumers in Header.tsx and Footer.tsx") which also handles the duplicated `border border-white/10` reduction at that site. T01's verification scope is the 7 listed files; the slice-wide grep gate will be cleared at the end of T02. Surrounding decorative blob containers, `btn-primary`, `text-gradient`, and `animate-*` classes remain untouched per the pitfalls list (all S04 territory).

## Verification

Ran the T01 file-scoped grep gate `rg 'glass-card'` against the 7 modified files — exit 1 (zero hits). Ran `npm run type-check` (tsc -b --noEmit) in `frontend/` — exit 0. Ran `npm run build` (tsc -b && vite build && prerender) in `frontend/` — exit 0, all 7 prerendered routes succeeded. The slice-wide grep gate (across components/ pages/ contexts/ hooks/ api/ lib/ __tests__/) still shows the single Header.tsx:156 hit assigned to T02; that closure is part of the slice-level verification on the final task, not T01.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg 'glass-card' frontend/src/pages/Home.tsx frontend/src/pages/authentication/Login.tsx frontend/src/pages/authentication/Register.tsx frontend/src/pages/authentication/ExtensionAuth.tsx frontend/src/pages/NotFound.tsx frontend/src/pages/PrivacyPolicy.tsx frontend/src/pages/TermsOfService.tsx` | 1 | ✅ pass | 50ms |
| 2 | `npm --prefix frontend run type-check` | 0 | ✅ pass | 9000ms |
| 3 | `npm --prefix frontend run build` | 0 | ✅ pass | 16000ms |

## Deviations

None — all 7 mapping-table entries applied verbatim. Header.tsx:156 still shows `glass-card` but that consumer is assigned to T02 per the slice plan; T01's verification scope is the 7 files in its mapping table.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/authentication/Login.tsx`
- `frontend/src/pages/authentication/Register.tsx`
- `frontend/src/pages/authentication/ExtensionAuth.tsx`
- `frontend/src/pages/NotFound.tsx`
- `frontend/src/pages/PrivacyPolicy.tsx`
- `frontend/src/pages/TermsOfService.tsx`
