---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T04: Polish builder/build-list/search/standalone-form pages + consume Textarea in BugReport + ViewBuildLog

Polish-pass batch covering builder/build-list/search/standalone-form pages (research Batches 5+6 merged — both touch user-content rendering and forms, file-disjoint from T02/T03/T05): Builder, ViewCar, BuildListsCatalog, ViewBuildLog, Search, BugReport. Tokenize ViewCar's category switcher off-palette colors → semantic tokens; tokenize BuildListsCatalog's filter sidebar off-palette accents; migrate ViewBuildLog's ~25 markdown-renderer color overrides to semantic tokens (do NOT introduce Tailwind Typography prose plugin — high-impact dependency decision deferred to S06 UAT, document in slice summary); replace hand-rolled <input>/<button> in Search.tsx with Input/Button primitives; replace 5 hand-rolled <textarea> sites (BugReport.tsx has 5; ViewBuildLog.tsx has 1 if present per probe) with the new Textarea primitive from T01. Do NOT collapse Search's 3-section result blocks (medium-impact IA — defer); do NOT redesign BuildListsCatalog sidebar at narrow widths (high-impact IA — defer to S06 UAT, document in slice summary). Migrate text-gray-300/400 survivors in these 6 pages. Quality gate (Q3 Threat Surface): BugReport.tsx accepts user-supplied bug-report text and submits to /api/bug-reports; ViewBuildLog renders user-authored markdown content. Textarea swap in BugReport preserves existing form-submit handler — no change to input validation, length limits, or sanitization. ViewBuildLog markdown renderer unchanged; only the color overrides in its consumed renderer styles are migrated. No new abuse surface introduced. Quality gate (Q5): BugReport submit must continue to work; ViewBuildLog markdown render must continue to render content correctly. Negative test: existing BugReport.test.tsx and ViewBuildLog.test.tsx vitest specs must pass. Quality gate (Q7): Existing vitest specs cover form submit and content render — no new negative tests required for visual-only edits.

## Inputs

- ``frontend/src/components/ui/textarea.tsx``
- ``frontend/src/pages/builder/Builder.tsx``
- ``frontend/src/pages/builder/ViewCar.tsx``
- ``frontend/src/pages/buildLists/BuildListsCatalog.tsx``
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx``
- ``frontend/src/pages/Search.tsx``
- ``frontend/src/pages/BugReport.tsx``

## Expected Output

- ``frontend/src/pages/builder/Builder.tsx``
- ``frontend/src/pages/builder/ViewCar.tsx``
- ``frontend/src/pages/buildLists/BuildListsCatalog.tsx``
- ``frontend/src/pages/buildLists/ViewBuildLog.tsx``
- ``frontend/src/pages/Search.tsx``
- ``frontend/src/pages/BugReport.tsx``

## Verification

1. rg '<textarea\b' frontend/src/pages/BugReport.tsx frontend/src/pages/buildLists/ViewBuildLog.tsx returns 0 (5 sites swapped to Textarea primitive); the import 'from .../components/ui/textarea' is present in both files. 2. rg 'text-gray-(300|400)' frontend/src/pages/Search.tsx frontend/src/pages/BugReport.tsx frontend/src/pages/builder/{Builder,ViewCar}.tsx frontend/src/pages/buildLists/{BuildListsCatalog,ViewBuildLog}.tsx returns 0. 3. The 12 S04 grep gates remain green. 4. cd frontend && npm run type-check && npm run lint && npm test -- --run all exit 0; specifically BugReport.test.tsx, ViewBuildLog.test.tsx, BuildListsCatalog.test.tsx, ViewCar.test.tsx, Builder.test.tsx, Search.test.tsx all pass. 5. Visual smoke (manual): rendering the BugReport page in dev does not crash and the textarea fields accept input + submit normally (verified in T06 cascade refresh).
