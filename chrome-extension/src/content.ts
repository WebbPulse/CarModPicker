/**
 * Content script: loads only on CarModPicker domains to set an install marker
 * the web app can detect (`data-carmodpicker-extension="installed"`).
 *
 * Scraping third-party pages is done via on-demand `chrome.scripting.executeScript`
 * from the popup, so this script does NOT need broad host access.
 */

const CARMODPICKER_HOST_PATTERN = /(^|\.)carmodpicker\.com$|^localhost$/i;
if (CARMODPICKER_HOST_PATTERN.test(window.location.hostname)) {
  document.documentElement.dataset["carmodpickerExtension"] = "installed";
}
