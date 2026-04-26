# Quick Task: my crawlers and jobs endpoints are 401ing even for a superuser

**Date:** 2026-04-26
**Branch:** gsd/quick/1-my-crawlers-and-jobs-endpoints-are-401in

## Root cause

The frontend admin client called `/admin/jobs` and `/admin/crawlers` without
trailing slashes, but the backend mounts those routes at `/api/admin/jobs/`
and `/api/admin/crawlers/` (the `@router.get("/")` form). FastAPI's default
`redirect_slashes=True` issued a `307 Temporary Redirect` to the slashed URL.

Reproduction with TestClient (follow_redirects=False):

```
GET /api/admin/jobs       -> 307 Location: http://testserver/api/admin/jobs/
GET /api/admin/crawlers   -> 307 Location: http://testserver/api/admin/crawlers/
```

In production the redirect Location is an absolute URL. When the browser
(or axios) follows a redirect that crosses origin/scheme — the typical case
behind App Runner / a CDN where the redirected absolute URL doesn't match
the current origin — the `Authorization` header is dropped, and the
follow-up request lands at the route with no token, so `oauth2_scheme`
rejects it with a 401. The user sees "401 even as superuser" because the
token never reaches the handler that would do the admin/superuser check.

`/users/me` and most other endpoints worked because their callers already
included the trailing slash (or didn't go through a redirect).

## What changed

- `frontend/src/api/admin.ts`
  - `getCrawlers`: `/admin/crawlers` → `/admin/crawlers/`
  - `listJobs`:    `/admin/jobs`     → `/admin/jobs/`
- `frontend/src/api/admin.test.ts` — updated the two assertions that pinned
  the old no-slash URLs.
- `frontend/src/pages/admin/CrawlerAdmin.test.tsx` — updated the mount-time
  `/admin/jobs` assertion to `/admin/jobs/`.

Scoped to the two endpoints the user reported. `/admin/extraction-health`
has the same shape (no-slash → 307) but the user did not report it as
failing, so it was left alone — the file's existing comment notes the
redirect behavior was known to the original author.

## Files Modified

- frontend/src/api/admin.ts
- frontend/src/api/admin.test.ts
- frontend/src/pages/admin/CrawlerAdmin.test.tsx

## Verification

- Reproduced 401 with TestClient: a request to `/api/admin/jobs/` without
  the `Authorization` header (the state after a header-stripping redirect)
  returns `401 Unauthorized`. With the slash and a valid superuser token,
  it returns `200`.
- `npm test -- --run` (frontend): 594/594 tests pass.
- `npm run type-check` (frontend): clean.
- `pytest -n auto tests/test_admin_auth_coverage.py tests/api/endpoints/test_admin.py`
  (backend): 83/83 pass — the auth coverage matrix still expects `401` for
  unauthenticated and `403` for non-admin users on every `/api/admin/*`
  route, which is unchanged.
