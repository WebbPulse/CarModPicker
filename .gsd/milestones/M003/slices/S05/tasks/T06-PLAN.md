---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T06: Add polish-coverage.spec.ts + cascade-refresh all touched baselines + write S05-SUMMARY.md per-page verdict list

Wave C close: (1) Author frontend/e2e/polish-coverage.spec.ts that imports the route list from frontend/src/App.coverage.test.tsx (re-export ROUTES if needed) — for each route × each Playwright project (mobile=375, tablet=768, desktop=1280), page.goto(route) and await expect(page).toHaveScreenshot() with sensible options (fullPage: true, maxDiffPixelRatio: 0.01 to absorb sub-pixel font/AA noise). Skip auth-guarded routes that require login (or pre-authenticate via the existing test-helper pattern from price-alerts.spec.ts MEM098 — set cookie_consent_v1=accepted via page.addInitScript). (2) Run the full Playwright suite with --update-snapshots (default =changed mode per MEM156/MEM160) once at end-of-slice — refreshes only baselines that actually drifted from T02-T05 polish edits; per MEM176 cascade-refresh expectation is broad (admin + build-list + parts + price-alerts + price-history + smoke specs may all see geometry drift from T02-T05's collapsed animations and tokenized colors). Visually review every refreshed PNG against expected token-swap deltas before commit (per MEM148). (3) Author .gsd/milestones/M003/slices/S05/S05-SUMMARY.md with the slice's required deliverables: per-page verdict table (one row per route × viewport, verdict ∈ {pass, fixed, acceptable-as-scroll, deferred-to-S06}), explicit list of high-impact IA decisions deferred to S06 UAT (auth-shell unification, ContactUs 3-card collapse, BuildListsCatalog sidebar drawer, ViewBuildLog markdown-prose, UserManagement 11-col table, SystemAdmin DangerActionPanel extraction), files touched, observability surfaces produced. CRITICAL: Per MEM170/MEM179, polish-coverage.spec.ts must use the mobile=375 Playwright project (do NOT override to 360) — 360 is documented in the verdict table as the manual UAT signal only. Skill: verify-before-complete (run gauntlet before claiming done). Quality gate (Q5 Failure Modes): Playwright test authoring risks: (a) auth-guarded routes that crash on goto without login — mitigate by either skipping them in the spec (and noting in summary) or using existing test-helper auth pattern; (b) routes with dynamic UUIDs that 404 (e.g. /parts/some-part, /build-lists/00000000-...) — these will render NotFound or an error boundary; baselines for the error state are still useful and lock the rendered behavior; (c) cookie-consent banner intercepting screenshots at mobile viewport — mitigate via MEM098 addInitScript pattern; (d) ResizeObserver/AdBanner timing flake — mitigate by waiting for networkidle or a stable selector before screenshot. Quality gate (Q7): The new spec IS the negative test for visual regression across all 40 routes. After it runs green once, future PRs that mutate any covered route's rendered output without updating snapshots will fail this spec.

## Inputs

- ``frontend/src/App.coverage.test.tsx``
- ``frontend/playwright.config.ts``
- ``frontend/e2e/admin.spec.ts``
- ``frontend/e2e/price-alerts.spec.ts``
- ``frontend/src/pages/Home.tsx``
- ``frontend/src/pages/About.tsx``
- ``frontend/src/pages/Pricing.tsx``
- ``frontend/src/pages/Support.tsx``
- ``frontend/src/pages/Checkout.tsx``
- ``frontend/src/pages/ContactUs.tsx``
- ``frontend/src/pages/PrivacyPolicy.tsx``
- ``frontend/src/pages/TermsOfService.tsx``
- ``frontend/src/pages/authentication/Login.tsx``
- ``frontend/src/pages/authentication/Register.tsx``
- ``frontend/src/pages/authentication/ForgotPassword.tsx``
- ``frontend/src/pages/authentication/ForgotPasswordConfirm.tsx``
- ``frontend/src/pages/authentication/VerifyEmail.tsx``
- ``frontend/src/pages/authentication/ExtensionAuth.tsx``
- ``frontend/src/pages/Profile.tsx``
- ``frontend/src/pages/ViewUser.tsx``
- ``frontend/src/pages/account/AccountAlerts.tsx``
- ``frontend/src/pages/builder/Builder.tsx``
- ``frontend/src/pages/builder/ViewCar.tsx``
- ``frontend/src/pages/buildLists/BuildListsCatalog.tsx``
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx``
- ``frontend/src/pages/Search.tsx``
- ``frontend/src/pages/BugReport.tsx``
- ``frontend/src/pages/admin/ReportReview.tsx``
- ``frontend/src/pages/admin/BugReportReview.tsx``
- ``frontend/src/pages/admin/UserManagement.tsx``
- ``frontend/src/pages/admin/CrawlerAdmin.tsx``
- ``frontend/src/pages/admin/SystemAdmin.tsx``
- ``frontend/src/pages/admin/SystemStatistics.tsx``
- ``frontend/src/pages/admin/PartsCuration.tsx``

## Expected Output

- ``frontend/e2e/polish-coverage.spec.ts``
- ``.gsd/milestones/M003/slices/S05/S05-SUMMARY.md``
- ``frontend/src/App.coverage.test.tsx``

## Verification

1. frontend/e2e/polish-coverage.spec.ts exists; cd frontend && npx playwright test polish-coverage.spec.ts exits 0; frontend/e2e/polish-coverage.spec.ts-snapshots/ directory contains PNG baselines for every covered route × 3 viewports (committed via --update-snapshots initial run). 2. cd frontend && npx playwright test (full suite, no --update-snapshots) exits 0 — proves cascade-refresh review is complete and baselines match. 3. .gsd/milestones/M003/slices/S05/S05-SUMMARY.md exists, contains: (a) per-route × per-viewport verdict table with 38+ rows × 3 viewport columns; (b) explicit Deferrals section listing 6+ IA decisions punted to S06 UAT (with file:line refs); (c) files touched; (d) the 12 S04 grep gates' verified-zero-hits status; (e) cascade-refresh review note per MEM148. 4. Final standing gauntlet: cd frontend && npm run type-check && npm run lint && npm test -- --run && npm run build && npx playwright test all exit 0; lint ≤ 108 errors (MEM062 baseline). 5. The 12 S04 grep gates remain green at slice end.
