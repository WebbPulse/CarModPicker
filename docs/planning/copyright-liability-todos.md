# Copyright Liability – Low-Hanging Fruit

Actionable todos to reduce copyright risk. Ordered by impact; all are low effort for "no users yet." Revisit and go deeper if the project gains traction.

---

## High impact

### 1. Description: show excerpt + "View full description at retailer"

**Why:** Using the _full_ description is the hardest to defend under fair use (amount factor). A short excerpt + link to the source is more clearly referential and reduces the amount copied.

**Do:**

- On ViewGlobalPart (and anywhere part description is shown), show only an excerpt (e.g. first ~160 characters or first 1–2 sentences).
- Add a line: e.g. "From product listing. [View full description at retailer →]" linking to the first listing's `product_url` (or "Price by retailer" section if no single canonical URL).
- Optionally store full description in DB for search/admin but only display excerpt + link in the UI.

---

### 2. Attribution near part images

**Why:** Makes it clear you're not claiming ownership of the images and that they originate from retailers.

**Do:**

- On ViewGlobalPart, add a small line near the image gallery: e.g. "Product images from retailer listings" with a link to the "Price by retailer" section or the first listing's product URL.
- Same idea on any other surface that shows part images (e.g. build list part cards if they show a thumbnail).

---

### 3. Attribution near part description

**Why:** Same as above—source and link-back support a "referential / transformative" story.

**Do:**

- When a description is shown, add a line like "From product listing" or "Source: [retailer name]" with a link to that listing's `product_url`. Use the first listing (or primary listing) when multiple exist.

---

## Medium impact (policy / process)

### 4. DMCA policy page

**Why:** Contact Us already has a DMCA callout; a short policy page shows you take it seriously and tells senders what to include. Helps you respond consistently.

**Do:**

- Add a page (e.g. `/dmca` or a "Legal" page with a DMCA section). Include:
  - What to send: identification of the copyrighted work, URL/location of the infringing material on your site, your contact info, good-faith statement, physical or electronic signature.
  - That you will remove or disable access to infringing content and may terminate repeat infringers.
  - Optional: brief counter-notice process (if you want to allow users to dispute).
- Link to this page from the Contact Us DMCA section ("in accordance with our [DMCA policy]").

---

### 5. Terms of Service

**Why:** Puts users on notice, reserves your right to remove content, and clarifies acceptable use (no scraping of your site, no uploading content they don't have rights to).

**Do:**

- Add a ToS page. At minimum include:
  - Users may only submit content they have rights to or that is lawfully available for such use.
  - You reserve the right to remove content that infringes or that you deem objectionable.
  - You respond to valid DMCA notices (link to DMCA policy).
  - No unauthorized scraping, bots, or bulk collection of product listings/data from your site.
- Link in footer alongside Privacy Policy.

---

### 6. Internal DMCA response checklist

**Why:** When a notice arrives, you act quickly and consistently (good for liability and for the "repeat infringer" safe harbor).

**Do:**

- Keep a short internal checklist (doc or Notion): (1) Log the notice (date, sender, URLs), (2) Remove or disable access to the identified content, (3) Document what was removed, (4) Reply to sender acknowledging receipt and action. Optionally (5) Notify the user who added the content if your policy allows.
- No code change—just a personal/team process.

---

### 7. Honor opt-out / takedown requests (beyond DMCA)

**Why:** Retailers may ask you to stop using their images/descriptions without sending a formal DMCA notice. Honoring those requests reduces escalation and shows good faith.

**Do:**

- In the Contact Us DMCA section (or on the DMCA policy page), add one sentence: e.g. "We also honor takedown requests from retailers and rights holders outside the formal DMCA process; contact us at the same address."
- When you get such a request: remove the content (or the affected part/listings) and document it the same way you would for a DMCA notice.

---

## Already in good shape

- **DMCA callout on Contact Us** – Done.
- **"View at retailer" on listings** – You already link each listing to `product_url`; keep that pattern and extend attribution to the main part content (description + images) as above.

---

## If you go deeper later

- Consider storing only one primary image per part (or thumbnails) and linking to retailer for full gallery.
- Add a simple "Report this content" flow that routes to your DMCA/contact path.
- If you monetize, add a designated DMCA agent and register with the U.S. Copyright Office (required for the DMCA safe harbor for monetary relief).
- Consider an LLC and keeping all app operations and revenue in the LLC (separate from personal) so that any liability stays at the entity level where possible; run this by a lawyer.
