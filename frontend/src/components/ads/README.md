# Sidebar banner ads

Banner ads render in the left and right margins on every page. They are global (defined in `App.tsx`) and **refresh on every route change** so each page view can count as a new ad impression.

## Development (no AdSense)

Without any env vars, placeholder boxes are shown so layout is correct. No script or account needed.

## Enabling Google AdSense

1. **Sign up**: [Google AdSense](https://www.google.com/adsense/) and get your **publisher ID** (e.g. `ca-pub-1234567890123456`).

2. **Create ad units** in the AdSense UI (e.g. “Display” → “Responsive” or “Fixed”). Note the **slot IDs** for left and right (e.g. `1234567890`).

3. **Load the script** in `frontend/index.html`: uncomment the AdSense script and replace `ca-pub-XXXXXXXXXXXXXXXX` with your publisher ID.

4. **Env vars** (in `frontend/.env` or your deploy env):

   - `VITE_ADSENSE_CLIENT_ID` = your publisher ID (e.g. `ca-pub-1234567890123456`)
   - `VITE_ADSENSE_SLOT_LEFT` = slot ID for the left sidebar
   - `VITE_ADSENSE_SLOT_RIGHT` = slot ID for the right sidebar

5. Rebuild/restart the frontend. Real ads will load in the sidebars; remounting on route change requests new ads as intended for SPAs.

## Policy note

Refreshing ads on every navigation is a common SPA pattern. Stay within [AdSense program policies](https://support.google.com/adsense/answer/48182) (e.g. no encouraging clicks, no excessive refresh in a short time). One new ad per genuine page view is generally fine.
