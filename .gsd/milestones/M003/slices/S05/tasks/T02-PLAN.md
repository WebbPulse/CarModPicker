---
estimated_steps: 1
estimated_files: 9
skills_used: []
---

# T02: Polish marketing/static pages: Home, About, Pricing, Support, Checkout, ContactUs, PrivacyPolicy, TermsOfService

Polish-pass batch covering the 8 marketing/static pages (research Batches 1+2 merged — both are static-content pages with similar tokenization patterns and they share the text-gradient/animation surface). Tokenize off-palette content: replace from-warning via-orange-500 to-red-500 3-stop gradients in Pricing, replace raw shadow-[0_0_40px_rgba(251,191,36,0.15)] with a tokenized shadow utility (add --shadow-warning-glow to tokens.css if needed — atomic add per MEM149), collapse animation cascades where multiple animate-* classes stack with no visual distinction, and migrate any text-gray-300/400 survivors in these pages to text-muted-foreground. Do NOT collapse ContactUs's 3 identical email cards — high-impact IA change deferred to S06 UAT (document in slice summary). PrivacyPolicy/TermsOfService inline Card variant=glass shells already use the new primitive correctly — just verify token compliance. File-disjoint from T03/T04/T05. Quality gate (Q5 Failure Modes): None new — these pages have no external dependencies, no async flows beyond existing route loaders, no shared resources. Risk is purely visual; mitigated by cascade-refresh review in T06. Quality gate (Q7 Negative Tests): None new — visual regression via T06's polish-coverage.spec.ts is the negative test surface. No functional behavior changes.

## Inputs

- ``frontend/src/pages/Home.tsx``
- ``frontend/src/pages/About.tsx``
- ``frontend/src/pages/Pricing.tsx``
- ``frontend/src/pages/Support.tsx``
- ``frontend/src/pages/Checkout.tsx``
- ``frontend/src/pages/ContactUs.tsx``
- ``frontend/src/pages/PrivacyPolicy.tsx``
- ``frontend/src/pages/TermsOfService.tsx``
- ``frontend/src/styles/tokens.css``

## Expected Output

- ``frontend/src/pages/Home.tsx``
- ``frontend/src/pages/About.tsx``
- ``frontend/src/pages/Pricing.tsx``
- ``frontend/src/pages/Support.tsx``
- ``frontend/src/pages/Checkout.tsx``
- ``frontend/src/pages/ContactUs.tsx``
- ``frontend/src/pages/PrivacyPolicy.tsx``
- ``frontend/src/pages/TermsOfService.tsx``
- ``frontend/src/styles/tokens.css``

## Verification

1. rg 'from-warning via-orange-500 to-red-500|from-amber-[0-9]|via-orange-[0-9]|to-red-[0-9]' frontend/src/pages/Pricing.tsx returns 0 (3-stop gradient retokenized). 2. rg 'shadow-\[0_0_40px_rgba' frontend/src/pages/{Home,About,Pricing,Support,Checkout,ContactUs,PrivacyPolicy,TermsOfService}.tsx returns 0 (raw rgba shadow values replaced with tokenized utility OR a new --shadow-warning-glow token in tokens.css consumed via shadow-warning-glow arbitrary class). 3. rg 'text-gray-(300|400)' frontend/src/pages/{Home,About,Pricing,Support,Checkout,ContactUs,PrivacyPolicy,TermsOfService}.tsx returns 0. 4. The 12 S04 grep gates remain green. 5. cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build all exit 0.
