# Sidebar banner ads

Banner ads render in the left and right margins on every page. They are global (defined in `App.tsx`) and **refresh on every route change** so each page view can count as a new ad impression.

## Development (no slot IDs)

While `ADSENSE_SLOT_LEFT` or `ADSENSE_SLOT_RIGHT` in `adsenseConfig.ts` is empty, that side shows a placeholder box so layout is correct. The AdSense loader script still loads after cookie consent (needed for site verification), but no ads render there.

## Configuring Google AdSense

All three ids are public and live as constants in `adsenseConfig.ts`; none of them is read from the environment.

1. **Publisher ID** is `ADSENSE_CLIENT_ID`. Update that constant if the publisher changes.

2. **Create ad units** in the AdSense UI (e.g. "Display" → "Responsive" or "Fixed"). Note the **slot IDs** for left and right (e.g. `1234567890`).

3. **Slot IDs** go in `ADSENSE_SLOT_LEFT` and `ADSENSE_SLOT_RIGHT`.

4. Rebuild the frontend. Real ads will load in the sidebars; remounting on route change requests new ads as intended for SPAs.

5. **ads.txt** is served from `frontend/public/ads.txt` and must list the publisher ID.

## Policy note

Refreshing ads on every navigation is a common SPA pattern. Stay within [AdSense program policies](https://support.google.com/adsense/answer/48182) (e.g. no encouraging clicks, no excessive refresh in a short time). One new ad per genuine page view is generally fine.
