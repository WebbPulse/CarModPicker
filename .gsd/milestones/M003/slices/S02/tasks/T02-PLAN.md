---
estimated_steps: 21
estimated_files: 2
skills_used: []
---

# T02: Migrate `glass` / `glass-button` chrome on Header (7 sites) and Footer (3 sites) to inline tokenized equivalents

Replace every `glass` and `glass-button` class string in `frontend/src/components/layout/globalHeader/Header.tsx` and `frontend/src/components/layout/globalFooter/Footer.tsx` with the inline tokenized equivalent. The migration drops the legacy `::before` left-to-right shimmer overlay (defined in `index.css` lines 353–371) since the M002 design language doesn't preserve it. The Header line 156 mobile-menu container also drops a duplicated `border border-white/10` Tailwind class layered on top of the legacy `.glass-card` border.

**Per-site mapping table** (apply mechanically):

| Site | Old | New |
|------|-----|-----|
| `Header.tsx:67` profile-link | `flex items-center space-x-2 glass px-4 py-2 rounded-xl hover:bg-white/10 transition-all duration-300 group` | `flex items-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl transition-all duration-300 group` |
| `Header.tsx:77` desktop-logout | `flex items-center space-x-2 glass-button px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` | `flex items-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` |
| `Header.tsx:87` desktop-login | `glass-button px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` | `border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white hover:text-primary transition-all duration-300` |
| `Header.tsx:104` mobile-toggle | `md:hidden glass-button p-2 rounded-lg text-white hover:text-primary transition-all duration-300` | `md:hidden border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 p-2 rounded-lg text-white hover:text-primary transition-all duration-300` |
| `Header.tsx:156` mobile-menu container | `glass-card mx-4 mb-4 rounded-xl border border-white/10` | `border border-white/10 bg-white/5 backdrop-blur-xl mx-4 mb-4 rounded-xl` (drop the duplicated `border border-white/10`; use `backdrop-blur-xl` because legacy `.glass-card` used `--glass-backdrop: blur(20px)` ≈ `xl`) |
| `Header.tsx:171` mobile-logout | `w-full flex items-center justify-center space-x-2 glass-button px-4 py-2 rounded-xl text-sm font-medium text-white` | `w-full flex items-center justify-center space-x-2 border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white` |
| `Header.tsx:181` mobile-login | `block w-full text-center glass-button px-4 py-2 rounded-xl text-sm font-medium text-white` | `block w-full text-center border border-white/10 bg-white/5 backdrop-blur-md hover:bg-white/10 px-4 py-2 rounded-xl text-sm font-medium text-white` |
| `Footer.tsx:121,129,137` social icons (× 3) | `w-10 h-10 glass rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300` | `w-10 h-10 border border-white/10 bg-white/5 backdrop-blur-md rounded-lg flex items-center justify-center text-muted-foreground hover:text-white hover:bg-white/10 transition-all duration-300` |

**Notes on the inline expression choice:**
- `glass-button` legacy used `backdrop-filter: blur(10px)` — closest tailwind utility is `backdrop-blur-md` (12px).
- `glass-card` legacy used `backdrop-filter: blur(20px)` — closest is `backdrop-blur-xl` (24px). Header line 156 (mobile-menu container) is the only `glass-card` site in this task.
- `bg-white/5` matches the M002 `Card variant="glass"` background; `border border-white/10` matches the variant border. Consistent with the 10+ existing `<Card variant="glass">` consumers (About, Pricing, Support, ContactUs, Checkout) the user has already accepted.

**Pitfalls:**
- Don't touch `btn-primary` on `Header.tsx` lines 93 and 188 — S04 territory.
- Don't touch any `animate-*` classes on Header — S04 territory.
- Header.tsx line 156: the duplicated `border border-white/10` MUST be reduced to a single occurrence in the new className.

**Verification (run before commit):** Both grep gates 1 and 2 (see T04) must return zero hits.

## Inputs

- ``frontend/src/components/layout/globalHeader/Header.tsx``
- ``frontend/src/components/layout/globalFooter/Footer.tsx``
- ``frontend/src/index.css``
- ``frontend/src/components/ui/card.tsx``

## Expected Output

- ``frontend/src/components/layout/globalHeader/Header.tsx``
- ``frontend/src/components/layout/globalFooter/Footer.tsx``

## Verification

Run `rg 'glass-(card|button)?' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `rg 'className=.*\bglass\b' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `npm run type-check` in `frontend/` — expect exit 0.

## Observability Impact

None — pure className text migration. Grep gates `rg 'glass-(card|button)?' ...` and `rg 'className=.*\bglass\b' ...` are the inspection surface.
