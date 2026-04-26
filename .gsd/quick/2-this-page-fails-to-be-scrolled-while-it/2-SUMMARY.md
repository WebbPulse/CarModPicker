# Quick Task: this page fails to be scrolled while it is still pending its initial data load in http://localhost:4000/admin/crawler

**Date:** 2026-04-26
**Branch:** gsd/quick/2-this-page-fails-to-be-scrolled-while-it

## What Changed
- `CrawlerAdmin` now distinguishes auth-loading from logged-out: while `useAuth().isLoading` is true, the page renders a centered Spinner inside the same `container mx-auto px-3 py-4` wrapper used by the main render, instead of falling through to the misleading "Please log in" early-return.
- The auth-deny early-return branches now share the same `container` wrapper as the main render, so the page-level layout (and scroll context) is consistent across loading → unauthorized → main states.

## Files Modified
- frontend/src/pages/admin/CrawlerAdmin.tsx

## Verification
- Type-check: `npx tsc --noEmit` exits 0.
- Lint: `npx eslint src/pages/admin/CrawlerAdmin.tsx` exits 0.
- Tests: `npx vitest run src/pages/admin/CrawlerAdmin.test.tsx` — 13/13 pass (existing "please log in" and "no permission" assertions still hold because `unauthenticated` test scenario sets `isLoading: false`).
- Browser repro: with admin auth and 60s API throttling on `/api/admin/*`, the page enters its pending-data state with body height 1259px / viewport 800px. Mouse-wheel scrolling and `window.scrollTo` both succeed (scrollY reaches the correct max of 459). After the fix, the early-return states wrap their content in the same `container mx-auto px-3 py-4` shell as the main render, eliminating the layout/wrapper swap that occurs when auth resolves and content swaps in.
