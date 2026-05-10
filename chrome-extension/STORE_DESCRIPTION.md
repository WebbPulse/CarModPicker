# Chrome Web Store Listing — CarModPicker Part Scraper

Ready-to-paste content for every field in the Web Store submission form.
Keep this file in sync with `manifest.json` and the privacy policy at
`frontend/src/pages/PrivacyPolicy.tsx` — if any of the three drift, a reviewer
will reject the next update.

---

## 1. Extension name (45 char max)

Already set in `manifest.json`:

> CarModPicker Part Scraper

---

## 2. Short summary (132 char max)

> Capture product info from any retailer page and save it as a part in your CarModPicker build list — on click, never in the background.

(130 chars)

---

## 3. Detailed description (listing body)

> **Turn any retailer's product page into a CarModPicker part in one click.**
>
> CarModPicker is a free platform for tracking your car builds — your cars, your build lists, the parts that go on them, and the forum-style logs of what you changed and when. The Part Scraper extension lets you capture parts from anywhere on the web, not just the retailers we've built native crawlers for.
>
> **How it works**
>
> 1. Open a product page on any retailer you like.
> 2. Click the CarModPicker extension icon in your toolbar.
> 3. The extension captures that tab's URL and rendered HTML and sends it to CarModPicker's servers.
> 4. Our parser extracts the name, price, part number, manufacturer, images, and description, then shows you a pre-filled form to review.
> 5. Confirm, pick the build list, and the part is saved.
>
> **Built to respect your privacy**
>
> - The extension only runs when you click it. No background monitoring, no passive page tracking, no analytics.
> - Before the captured HTML is stored or parsed, the server strips scripts (other than product structured data), styles, iframes, and form-field values — so autofilled inputs and inline user-state blobs never hit our database.
> - The extension does not read your cookies, browser storage, or request headers.
> - Data captured by the extension is used only to parse product info for your account. We don't sell it, transfer it, use it for advertising, or let humans read it except for security, legal compliance, or with your consent.
>
> **Requires a free CarModPicker account.** Sign up at https://carmodpicker.com.
>
> Full privacy policy: https://carmodpicker.com/privacy-policy

---

## 4. Category

> Shopping

Alternative: "Productivity" is less crowded. Pick based on which discovery surface you care about more.

---

## 5. Single purpose (required field)

> Capture product information from the retailer page the user is currently viewing and save it as a part in the user's CarModPicker account.

---

## 6. Permission justifications

### `activeTab`

> Used to read the URL and rendered HTML of the tab the user is currently viewing, and only when the user explicitly clicks the extension's toolbar action. This is how the extension knows which page to scrape. The extension never accesses tabs the user has not explicitly invoked it on.

### `scripting`

> Used together with activeTab to inject a single inline function into the active tab — on user click — that returns `document.documentElement.outerHTML`. This is the capture step for the product page the user chose. No code is loaded from any remote source; the injected function is defined inline in the extension bundle and consists of one expression.

### `storage`

> Used to store the user's CarModPicker authentication token locally via `chrome.storage` so the user does not have to re-enter credentials every time they open the popup. Also stores minor UI preferences (selected environment, last-used build list). No analytics, telemetry, or third-party data is stored.

---

## 7. Host permissions justification

The extension requests **no** `host_permissions`. The content script is scoped to `carmodpicker.com` and `localhost` only (used to set an "extension installed" marker on the web app). All scraping is performed via `activeTab` + `chrome.scripting.executeScript`, which only grants access to the tab the user has explicitly invoked the extension on.

If the reviewer asks anyway:

> The extension intentionally does not request host permissions. Access to third-party pages is obtained only through the activeTab permission, which requires explicit user invocation per tab.

---

## 8. Remote code use

> **No.** The extension does not load or execute any code from remote sources. The content security policy in `manifest.json` is `script-src 'self'; object-src 'self'`. All JavaScript is bundled into the extension at build time.

---

## 9. Data collection disclosure

Check **yes** on:

- **Personally identifiable information** — the extension transmits the user's CarModPicker auth token with each request.
- **Authentication information** — same reason (auth token stored in `chrome.storage`).
- **Website content** — the extension transmits the rendered HTML of product pages the user chooses to scrape.

Leave **unchecked**:

- Health information
- Financial / payment information
- Personal communications
- Location
- Web history *(the extension only captures pages the user explicitly clicks, which is not browsing history)*
- User activity *(no click or scroll logging)*

---

## 10. Limited Use certifications

Check all three:

- I do not sell or transfer user data to third parties, apart from the approved use cases.
- I do not use or transfer user data for purposes that are unrelated to my item's single purpose.
- I do not use or transfer user data to determine creditworthiness or for lending purposes.

---

## 11. Privacy policy URL

> https://carmodpicker.com/privacy-policy

---

## 12. Support / homepage URLs

- **Homepage:** `https://carmodpicker.com`
- **Support email:** `tyler@webbpulse.com` (matches the contact email in the privacy policy — reviewers check for continuity)

---

## 13. Language

English (United States)

---

## Screenshots and assets (not drafted here — you have to produce them)

Required before submission:

- **Screenshots** at 1280×800 or 640×400. Minimum one; five is the recommended sweet spot for conversion. Suggested set:
  1. The popup before scrape (logged-in main screen).
  2. The "Analyzing page…" state on a real retailer product page.
  3. The pre-filled part review dialog with scraped fields populated.
  4. A saved part visible in a build list on carmodpicker.com.
  5. The options page.
- **Promo tile** at 440×280 (optional, helps with ranking on the category page).
- **Icon** at 128×128 is already in `chrome-extension/icons/icon128.png`.

---

## Keeping this doc honest

Every claim in this document has to survive a reviewer re-reading it next to your code. If any of these change, update this doc in the same PR:

- `chrome-extension/manifest.json` — permissions, host_permissions, content_scripts.matches, CSP.
- `chrome-extension/src/pages/popup.tsx` — the `handleScrape` flow and what data leaves the browser.
- `chrome-extension/src/content.ts` — what runs on which domains.
- `backend/app/crawlers/sanitize.py` — what gets stripped before storage.
- `backend/app/api/endpoints/crawled_pages.py` — the `/scrape` and `/html` endpoints.
- `frontend/src/pages/PrivacyPolicy.tsx` — sections 1, 4, and 5 in particular.
