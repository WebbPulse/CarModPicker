---
estimated_steps: 17
estimated_files: 7
skills_used: []
---

# T01: Migrate `glass-card` consumers (7 files) to `Card variant="glass"` or inline tokenized equivalent

Replace every `glass-card` class string in the 7 consumer files with either the M002/S08 `Card variant="glass"` primitive (only at `frontend/src/pages/Home.tsx` line 385, which is already a `<Card>`) or the inline tokenized equivalent `border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5` for the 6 raw-`<div>` consumers (Login, Register, ExtensionAuth, NotFound, PrivacyPolicy, TermsOfService). The inline form is preferred over a `<Card>` conversion for the raw-div consumers because they wrap padding shapes (`p-12`, `p-8 md:p-12`) that the `Card` `padding` prop doesn't model cleanly, and they sit inside outer `animate-*` chrome that the inline form preserves verbatim.

**Per-file mapping table** (apply mechanically — no judgment per site):

| File | Old | New |
|------|-----|-----|
| `frontend/src/pages/Home.tsx:385` | `<Card className="glass-card">` | `<Card variant="glass">` |
| `frontend/src/pages/authentication/Login.tsx:169` | `<div className="glass-card rounded-2xl p-8 animate-slideInUp">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">` |
| `frontend/src/pages/authentication/Register.tsx:81` | `<div className="glass-card rounded-2xl p-8 animate-slideInUp">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">` |
| `frontend/src/pages/authentication/ExtensionAuth.tsx:157` | `<div className="glass-card rounded-2xl p-8 animate-slideInUp">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 animate-slideInUp">` |
| `frontend/src/pages/NotFound.tsx:16` | `<div className="glass-card rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-12 max-w-md mx-auto animate-fadeInScale">` |
| `frontend/src/pages/PrivacyPolicy.tsx:17` | `<div className="glass-card rounded-2xl p-8 md:p-12">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 md:p-12">` |
| `frontend/src/pages/TermsOfService.tsx:18` | `<div className="glass-card rounded-2xl p-8 md:p-12">` | `<div className="border border-white/10 bg-white/5 backdrop-blur-xl supports-[backdrop-filter]:bg-white/5 rounded-2xl p-8 md:p-12">` |

**Pitfalls:**
- Do NOT touch `btn-primary` (Header / NotFound), `text-gradient` (NotFound), or `animate-slideInUp/fadeInScale` (multiple files) — all S04 territory.
- Do NOT add a `Card` import to the 6 div-based consumers — keep the `<div>` shape so the diff is `className`-only.
- Do NOT touch the surrounding decorative `<div className="absolute inset-0 overflow-hidden">` background-blob containers above the glass panels.

**Verification (run before commit):** `rg 'glass-card' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` must return zero hits.

**Failure modes to watch:** None of the 6 div-based files import `Card` today; if a typo accidentally introduces `<Card>`-style markup, vite build will fail with an undefined-component error. Type-check after the edits.

## Inputs

- ``frontend/src/components/ui/card.tsx``
- ``frontend/src/pages/Home.tsx``
- ``frontend/src/pages/authentication/Login.tsx``
- ``frontend/src/pages/authentication/Register.tsx``
- ``frontend/src/pages/authentication/ExtensionAuth.tsx``
- ``frontend/src/pages/NotFound.tsx``
- ``frontend/src/pages/PrivacyPolicy.tsx``
- ``frontend/src/pages/TermsOfService.tsx``

## Expected Output

- ``frontend/src/pages/Home.tsx``
- ``frontend/src/pages/authentication/Login.tsx``
- ``frontend/src/pages/authentication/Register.tsx``
- ``frontend/src/pages/authentication/ExtensionAuth.tsx``
- ``frontend/src/pages/NotFound.tsx``
- ``frontend/src/pages/PrivacyPolicy.tsx``
- ``frontend/src/pages/TermsOfService.tsx``

## Verification

Run `rg 'glass-card' frontend/src/components/ frontend/src/pages/ frontend/src/contexts/ frontend/src/hooks/ frontend/src/api/ frontend/src/lib/ frontend/src/__tests__/` — expect zero hits. Run `npm run type-check` in `frontend/` — expect exit 0. Run `npm run build` in `frontend/` — expect exit 0.

## Observability Impact

None — pure className text migration. Grep gate `rg 'glass-card' frontend/src/...` is the inspection surface.
