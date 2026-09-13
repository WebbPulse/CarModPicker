# CarModPicker Browser Companion

Chrome MV3 extension. It reads part information off a retailer product page and creates the part in the user's CarModPicker account, getting or creating the retailer by domain so the part listing and its price history come along. If the product URL is already in the catalog it shows a read-only view and offers to record the current price instead.

Built with React 19, TypeScript and Vite. `manifest.json`, `popup.html`, `options.html` and the `icons/` directory sit at the extension root; sources are under `src/`; every build output lands in `dist/`.

## Build

```bash
npm install
npm run build       # production build into dist/
npm run watch       # rebuild on change
npm run type-check  # tsc --noEmit
npm test            # vitest run
```

`npm run build` is `vite build` followed by `scripts/inline-content.js`, which folds any shared chunk back into `dist/content.js`, because a content script cannot be an ES module and so cannot carry a top-level import. `npm run watch` is `vite build --watch` and **does not run that step**, so the moment the content script gains an import, a watch build produces a content script Chrome cannot load. Run a full `npm run build` before testing scraping. `npm run build:dev` is the same chain as `build` without `NODE_ENV=production`, so it keeps sourcemaps and skips minification.

The Vite config also copies `manifest.json` into `dist/` and strips the `dist/` prefix off the service worker and content script paths as it goes, so the built manifest is correct relative to `dist/`. Load the built extension from `dist/`, never from the repository root.

## Load the unpacked extension

1. `npm run build`.
2. Open `chrome://extensions/`.
3. Turn on **Developer mode** (top right).
4. **Load unpacked**, and select `chrome-extension/dist`.

You never need to remove and re-add the extension after a change. Use the reload button (the circular arrow) on the extension's card in `chrome://extensions/`.

### What needs a reload

| Changed | What to do |
| --- | --- |
| `manifest.json` | Reload the extension. Always. |
| `src/background.ts` (the service worker) | Reload the extension. Service workers persist in memory. |
| `popup.html`, `options.html`, `auth-callback.html` | Reload the extension. |
| `src/content.ts` and anything it imports | No reload; the new script is injected on the next page navigation. Refresh the page you are testing on. |
| Popup React sources | No reload; close and reopen the popup. |
| Options page sources | No reload; reopen the options page. |

Chrome extensions cannot reload themselves, so watch mode gets you the rebuild and you still click reload.

## Authentication

The extension holds a bearer token in `chrome.storage.local` and sends it as `Authorization: Bearer <token>` on every API call. It never uses cookies, which is why the API allows its origin by explicit extension id rather than by a wildcard.

Sign-in has two modes, stored in `chrome.storage.sync` under `authMode` and selectable on the options page. The default is `identity`: the service worker opens `<web origin>/auth/extension-handoff` in a tab with a `state` nonce and a `redirect_uri` pointing at the extension's own `auth-callback.html`, that page reads the sign-in code out of the URL fragment and hands it to the service worker, and the service worker exchanges it for a token. `legacy` opens `<web origin>/extension-auth` instead and receives a token handed off by the page. The web origin is derived from the configured API URL by dropping the leading `api.` label.

The options page also stores an optional **Ingestion API Key**, sent as the `X-API-Key` header. Only the batch price-history route requires it, and it is kept in `chrome.storage.local` so it stays on one device rather than syncing across Chrome profiles.

## Configuration

The options page picks an API environment (Production, Staging or Localhost) and writes the matching API URL to `chrome.storage.sync`. Production is the default. Every host the extension can be pointed at must also appear in `host_permissions` in `manifest.json`; `scripts/check-host-permissions.js` fails CI when one does not. Host access is what lets the MV3 service worker call the API at all: the HTTP API's `cors_configuration` cannot name a `chrome-extension://` origin, so there is no backend change that would grant the extension a credentialed cross-origin fetch.

`API_CONTRACT.md` is the generated record of the backend endpoints the extension calls. Do not edit it by hand; the regeneration command is at the top of the file.

## CI

The `chrome-extension` job in `.github/workflows/ci.yml` runs on any pull request touching `chrome-extension/**`: `npm ci`, `npm run type-check`, `npm test`, `npm audit --audit-level=moderate`, `npm run build`, then it asserts `dist/manifest.json` exists and runs `scripts/check-host-permissions.js`. It uploads the built `dist/` as an artifact. It feeds `all-checks-passed`, which both branch rulesets require.

## Publishing

`.github/workflows/chrome-extension-deploy.yml` publishes to the Chrome Web Store. It is **`main`-only**: it triggers on a push to `main` touching `chrome-extension/**` or the workflow file itself, and on `workflow_dispatch`. There is no staging store listing, so there is no staging equivalent.

Two gates sit in front of a release:

- **`gate`** releases only when the event is a `workflow_dispatch`, or when the `production` GitHub Environment variable `CHROME_EXTENSION_AUTO_RELEASE` is exactly the string `true`. Any other value, including unset, holds the release and writes the reason to the run summary. A manual **Run workflow** is never gated.
- **`changes`** then skips the release when nothing but `manifest.json` changed under `chrome-extension/` since the newest `chrome-extension-v*` tag.

You do not bump `manifest.json` by hand. The release job reads the newest `chrome-extension-v*` tag, increments the patch, and refuses to continue if the result is not strictly greater than the last release or if the target tag already exists. With no tag at all it falls back to the committed manifest version. It patches the version into the build tree only, builds, verifies the built manifest carries it, zips `dist/`, uploads and publishes through the Chrome Web Store API, pushes the annotated tag `chrome-extension-v<version>`, cuts a GitHub Release with the zip attached, and opens a bookkeeping pull request against `staging` recording the published version in the committed manifest.

The tag is the version of record, not the committed manifest. It is pushed only after the Web Store publish succeeds, so a failed publish leaves the version number free for the next attempt, and the committed manifest trails the newest tag until the bookkeeping PR merges.

Credentials come from the `production` environment: variables `CWS_CLIENT_ID` and `CWS_EXTENSION_ID`, secrets `CWS_CLIENT_SECRET` and `CWS_REFRESH_TOKEN`. If any of the four is empty the job skips the publish step and still tags and releases.

To republish or release without a code change:

```bash
gh workflow run chrome-extension-deploy.yml --repo WebbPulse/CarModPicker --ref main
```

## Permissions

`activeTab` to read the current page, `storage` for the token and settings, `scripting` to inject the content script, and `host_permissions` for the API hosts.
