/**
 * Content script: captures full page HTML and sends it to the popup.
 *
 * All parsing/inference is done server-side via POST /crawled-pages/scrape.
 * This script is intentionally minimal — it only snapshots the live DOM so
 * that server-side adapters have the full rendered HTML to work with.
 */

// Mark CarModPicker hosts so the web app can detect this extension is installed.
// Scoped to our own domains to avoid mutating arbitrary pages.
const CARMODPICKER_HOST_PATTERN = /(^|\.)carmodpicker\.com$|^localhost$/i;
if (CARMODPICKER_HOST_PATTERN.test(window.location.hostname)) {
  document.documentElement.dataset["carmodpickerExtension"] = "installed";
}

chrome.runtime.onMessage.addListener(
  (
    request: { action: string },
    _sender,
    sendResponse: (response: { success: boolean; html: string }) => void
  ) => {
    if (request.action === "scrapePage") {
      try {
        const pageHtml = document.documentElement.outerHTML;
        sendResponse({ success: true, html: pageHtml });
      } catch {
        // Always respond so the popup doesn't receive chrome.runtime.lastError
        sendResponse({ success: false, html: "" });
      }
      return true; // Keep channel open for async response
    }
    return false;
  }
);
