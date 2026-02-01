/**
 * Content script for scraping product information from web pages
 */

import type { ScrapedProductData } from "./types";
import {
  getCanonicalImageUrl,
  getHighResImageUrl,
} from "./utils/imageUrlUtils";

// Listen for messages from popup
chrome.runtime.onMessage.addListener(
  (
    request: { action: string },
    _sender,
    sendResponse: (response: {
      success: boolean;
      data: ScrapedProductData;
    }) => void
  ) => {
    if (request.action === "scrapePage") {
      const scrapedData = scrapeProductData();
      sendResponse({ success: true, data: scrapedData });
      return true; // Keep channel open for async response
    }
    return false;
  }
);

/**
 * Scrape product information from the current page
 * Uses multiple strategies to extract product data
 */
function scrapeProductData(): ScrapedProductData {
  const data: ScrapedProductData = {
    name: null,
    description: null,
    price: null,
    image_url: null,
    image_urls: [],
    product_url: window.location.href,
    brand: null,
    part_number: null,
  };

  // Extract product name
  data.name = extractProductName();

  // Extract description
  data.description = extractDescription();

  // Extract price
  data.price = extractPrice();

  // Extract images (multiple for gallery)
  const imageUrls = extractImageUrls();
  data.image_urls = imageUrls;
  data.image_url = imageUrls.length > 0 ? imageUrls[0] ?? null : null;

  // Extract brand
  data.brand = extractBrand();

  // Extract part number/SKU
  data.part_number = extractPartNumber();

  return data;
}

/**
 * Extract product name using multiple strategies
 */
function extractProductName(): string | null {
  // Strategy 1: Open Graph title
  const ogTitle = document.querySelector('meta[property="og:title"]');
  if (ogTitle && ogTitle instanceof HTMLMetaElement && ogTitle.content) {
    const title = ogTitle.content.trim();
    if (title && title.length > 5 && !isNavigationText(title)) {
      return cleanTitle(title);
    }
  }

  // Strategy 2: Find h1 that's not in header/nav
  const h1s = document.querySelectorAll("h1");
  for (const h1 of Array.from(h1s)) {
    const text = h1.textContent?.trim();
    if (
      text &&
      text.length >= 5 &&
      !isInHeaderNav(h1) &&
      !isNavigationText(text)
    ) {
      return cleanTitle(text);
    }
  }

  // Strategy 3: Title tag
  const titleTag = document.querySelector("title");
  if (titleTag?.textContent) {
    let title = titleTag.textContent.trim();
    // Remove site name suffixes
    if (title.includes(" | ")) {
      title = title.split(" | ")[0]?.trim() || title;
    }
    if (title.includes(" - ") && title.toLowerCase().includes("shop")) {
      const parts = title.split(" - ");
      if (parts.length > 1) {
        title = parts.slice(0, -1).join(" - ").trim();
      }
    }
    if (title && title.length >= 5 && !isNavigationText(title)) {
      return cleanTitle(title);
    }
  }

  return null;
}

/**
 * Extract product description
 */
function extractDescription(): string | null {
  // Try meta description first
  const metaDesc =
    document.querySelector('meta[property="og:description"]') ||
    document.querySelector('meta[name="description"]');
  if (metaDesc && metaDesc instanceof HTMLMetaElement && metaDesc.content) {
    const desc = metaDesc.content.trim();
    if (desc && desc.length > 10) {
      return desc;
    }
  }

  // Try common description selectors
  const descSelectors = [
    '[class*="product"][class*="description"]',
    '[class*="description"]',
    '[id*="description"]',
    '[itemprop="description"]',
  ];

  for (const selector of descSelectors) {
    const elem = document.querySelector(selector);
    if (elem) {
      const text = elem.textContent?.trim();
      if (text && text.length > 10) {
        return text.substring(0, 500); // Limit length
      }
    }
  }

  return null;
}

/** Check if element is inside a related/recommended/cross-sell products section */
function isInRelatedProductsSection(element: Element): boolean {
  let el: HTMLElement | null = element.parentElement;
  while (el && el.tagName !== "BODY") {
    const cls = (el.className?.toString?.() ?? "").toLowerCase();
    const id = (el.id ?? "").toLowerCase();
    const role = (el.getAttribute?.("role") ?? "").toLowerCase();
    const ariaLabel = (el.getAttribute?.("aria-label") ?? "").toLowerCase();
    const text = el.textContent?.toLowerCase().slice(0, 200) ?? "";
    if (
      /related|recommended|similar|cross-?sell|upsell|also-?bought|you-?may-?like|other-?products|other-?great-?products|check-?out-?these/.test(
        cls + id + role + ariaLabel + text
      )
    ) {
      return true;
    }
    el = el.parentElement;
  }
  return false;
}

/** Find the main product container (contains product h1, excludes header/nav) */
function getMainProductContainer(): Element | null {
  const h1 = document.querySelector("h1");
  if (!h1 || isInHeaderNav(h1)) return null;
  // Walk up to find a reasonable product block (main, product-detail, etc.)
  let el: HTMLElement | null = h1.parentElement;
  while (el && el.tagName !== "BODY") {
    const tag = el.tagName.toLowerCase();
    const cls = (el.className?.toString?.() ?? "").toLowerCase();
    const id = (el.id ?? "").toLowerCase();
    if (
      tag === "main" ||
      /product-detail|product-info|product-main|product-summary|product-single/.test(
        cls + id
      )
    ) {
      return el;
    }
    el = el.parentElement;
  }
  return h1.closest('[class*="product"], [id*="product"]') ?? h1.parentElement;
}

/**
 * Extract price from the page
 * Prioritizes: JSON-LD Product schema, main product area, then structured markup.
 * Avoids related products, cart subtotals ($0), and financing "per month" amounts.
 */
function extractPrice(): number | null {
  const pricePattern = /\$[\d,]+\.?\d*/g;
  const currentUrl = window.location.href;

  // 1. JSON-LD Product schema (most reliable - unambiguous product price)
  let jsonLdPriceMatch: number | null = null;
  const scripts = document.querySelectorAll(
    'script[type="application/ld+json"]'
  );
  for (const script of Array.from(scripts)) {
    try {
      const json = JSON.parse(script.textContent || "{}");
      const items = Array.isArray(json) ? json : [json];
      for (const item of items) {
        const type = item?.["@type"];
        if (
          type === "Product" ||
          (Array.isArray(type) && type.includes("Product"))
        ) {
          const price =
            item.offers?.price ?? item.offers?.[0]?.price ?? item.price;
          if (price != null) {
            const num =
              typeof price === "string" ? parseFloat(price) : Number(price);
            if (!isNaN(num) && num > 0) {
              const cents = Math.round(num * 100);
              const offerUrl =
                item.offers?.url ?? item.offers?.[0]?.url ?? item.url ?? "";
              const urlMatches =
                !offerUrl ||
                currentUrl.startsWith(offerUrl) ||
                offerUrl.includes(new URL(currentUrl).pathname);
              if (urlMatches) return cents;
              if (!jsonLdPriceMatch) jsonLdPriceMatch = cents;
            }
          }
        }
      }
    } catch {
      /* ignore parse errors */
    }
  }
  if (jsonLdPriceMatch) return jsonLdPriceMatch;

  // 2. Open Graph product price meta
  const ogPrice = document.querySelector(
    'meta[property="product:price:amount"], meta[property="og:price:amount"]'
  );
  if (ogPrice instanceof HTMLMetaElement && ogPrice.content) {
    const num = parseFloat(ogPrice.content);
    if (!isNaN(num) && num > 0) return Math.round(num * 100);
  }

  // 3. Scoped to main product container - avoid related products
  const mainContainer = getMainProductContainer();
  const searchRoot = mainContainer ?? document.body;

  const tryPriceFromElement = (elem: Element): number | null => {
    if (isInRelatedProductsSection(elem)) return null;
    const priceText =
      elem.textContent ||
      elem.getAttribute("content") ||
      elem.getAttribute("data-price") ||
      "";
    const price = extractPriceValue(priceText);
    if (price && price > 0) return price;
    return null;
  };

  const structuredSelectors = [
    '[itemprop="price"]',
    "[data-price]",
    '[class*="product"][class*="price"]',
    '[class*="price"][class*="product"]',
    '.product-price, .price-box, [class*="product-price"], [class*="price-box"]',
    '[class*="price"]',
  ];

  for (const selector of structuredSelectors) {
    const elems = searchRoot.querySelectorAll(selector);
    for (const elem of Array.from(elems)) {
      if (isInRelatedProductsSection(elem)) continue;
      const price = tryPriceFromElement(elem);
      if (price) return price;
    }
  }

  // 4. Fallback: first price-like text in main product area (exclude $0 and tiny amounts)
  const scopeText = searchRoot.textContent || "";
  const prices = scopeText.match(pricePattern) || [];
  for (const p of prices) {
    const val = extractPriceValue(p);
    if (val && val >= 100) return val; // Skip $0 and trivial amounts
  }

  return null;
}

/**
 * Extract price value in cents from price text
 */
function extractPriceValue(priceText: string): number | null {
  if (!priceText) return null;

  // Remove currency symbols and commas
  const cleaned = priceText.replace(/[$,\s]/g, "").trim();

  // Extract number
  const match = cleaned.match(/(\d+\.?\d*)/);
  if (match && match[1]) {
    const dollars = parseFloat(match[1]);
    if (!isNaN(dollars) && dollars >= 0) {
      return Math.round(dollars * 100); // Convert to cents
    }
  }

  return null;
}

const MAX_GALLERY_IMAGES = 10;
const MIN_IMAGE_SIZE = 150;
/** Min size for images inside thumbnail/carousel strips so we don't collect small thumbs */
const MIN_MAIN_IMAGE_SIZE = 300;

/** Resolve image src to absolute URL */
function toAbsoluteUrl(src: string): string {
  if (src.startsWith("http")) return src;
  if (src.startsWith("//")) return window.location.protocol + src;
  try {
    return new URL(src, window.location.href).href;
  } catch {
    return "";
  }
}

/** Check if URL looks like a product image (not icon/logo) */
function isProductImageLike(
  url: string,
  img?: HTMLImageElement,
  skipSizeCheck?: boolean,
  minSize: number = MIN_IMAGE_SIZE
): boolean {
  if (!url || url.length < 10) return false;
  const lower = url.toLowerCase();
  if (
    lower.includes("icon") ||
    lower.includes("logo") ||
    lower.includes("avatar") ||
    lower.includes("placeholder") ||
    lower.includes("1x1") ||
    lower.endsWith(".svg") ||
    lower.includes("pixel.")
  ) {
    return false;
  }
  // Skip size check for lazy-loaded images (naturalWidth may be 0) or when explicitly asked
  if (!skipSizeCheck && img) {
    const w = img.naturalWidth || img.width || 0;
    const h = img.naturalHeight || img.height || 0;
    if (w > 0 && h > 0 && (w < minSize || h < minSize)) {
      return false;
    }
  }
  return true;
}

/** True if the image is inside a thumbnail strip / carousel thumb container (small previews) */
function isInThumbnailStrip(img: HTMLImageElement): boolean {
  let el: HTMLElement | null = img.parentElement;
  while (el && el.tagName !== "BODY") {
    const tag = el.tagName.toLowerCase();
    const cls = (el.className?.toString?.() ?? "").toLowerCase();
    const id = (el.id ?? "").toLowerCase();
    if (
      tag === "picture" ||
      /thumbnail|thumb-nav|thumbstrip|carousel-thumb|gallery-thumb|slick-thumb|swiper-thumb|nav-thumb/.test(
        cls
      ) ||
      /thumbnail|thumbstrip|thumb-nav/.test(id)
    ) {
      return true;
    }
    el = el.parentElement;
  }
  return false;
}

/**
 * Extract multiple product image URLs for gallery.
 * Dedupes by canonical URL (same image at different sizes) and favors high-res.
 */
function extractImageUrls(): string[] {
  const byCanonical = new Map<string, string>();

  function add(
    url: string,
    img?: HTMLImageElement,
    skipSizeCheck?: boolean,
    minSize: number = MIN_IMAGE_SIZE
  ): void {
    const abs = toAbsoluteUrl(url);
    if (!abs || !isProductImageLike(abs, img, skipSizeCheck, minSize)) return;
    const canonical = getCanonicalImageUrl(abs);
    if (!canonical) return;
    // Keep high-res variant (we'll normalize output to high-res later)
    const existing = byCanonical.get(canonical);
    if (!existing || getWidthFromUrl(abs) > getWidthFromUrl(existing)) {
      byCanonical.set(canonical, abs);
    }
  }

  function getWidthFromUrl(u: string): number {
    try {
      const match =
        new URL(u).searchParams.get("width") ||
        new URL(u).searchParams.get("w");
      return match ? parseInt(match, 10) : 0;
    } catch {
      return 0;
    }
  }

  // 1. Open Graph images (can have multiple via og:image:url in JSON-LD)
  const ogImages = document.querySelectorAll('meta[property="og:image"]');
  for (const meta of Array.from(ogImages)) {
    if (meta instanceof HTMLMetaElement && meta.content) {
      add(meta.content.trim());
    }
  }

  // 2. JSON-LD product with image array
  const scripts = document.querySelectorAll(
    'script[type="application/ld+json"]'
  );
  for (const script of Array.from(scripts)) {
    try {
      const json = JSON.parse(script.textContent || "{}");
      const items = Array.isArray(json) ? json : [json];
      for (const item of items) {
        if (
          item?.["@type"] === "Product" ||
          item?.["@type"]?.includes?.("Product")
        ) {
          const imgs = item.image;
          if (Array.isArray(imgs)) {
            for (const img of imgs) {
              const url = typeof img === "string" ? img : img?.url;
              if (url) add(url);
            }
          } else if (typeof imgs === "string") {
            add(imgs);
          }
        }
      }
    } catch {
      /* ignore */
    }
  }

  // 3. Product gallery / carousel / thumbnail containers
  const gallerySelectors = [
    '[class*="product"][class*="gallery"] img',
    '[class*="product"][class*="carousel"] img',
    '[class*="product"][class*="slider"] img',
    '[class*="gallery"] img',
    '[class*="thumbnail"] img',
    '[class*="product-image"] img',
    '[class*="main"][class*="image"] img',
    '[id*="product"][id*="image"] img',
    "[data-gallery] img",
    "[data-product-images] img",
    "[data-gallery-role] img",
    '[itemprop="image"]',
    ".product-images img",
    ".product-gallery img",
    ".slick-slide img",
    ".swiper-slide img",
    ".carousel-item img",
    ".fotorama__img",
    ".product-image-photo",
    ".gallery-placeholder img",
    ".gallery__image img",
    '[class*="fotorama"] img',
    "picture.product img",
    'picture[class*="gallery"] img',
    '[class*="media-gallery"] img',
    '[class*="image-gallery"] img',
    ".zoomWindowContainer img",
    '[class*="cloudzoom"] img',
  ];

  for (const selector of gallerySelectors) {
    try {
      const imgs = document.querySelectorAll(selector);
      for (const img of Array.from(imgs)) {
        if (img instanceof HTMLImageElement) {
          // Prefer full-size zoom URL over thumbnail src when present
          const zoomUrl =
            img.getAttribute("data-zoom-image") ||
            img.getAttribute("data-zoom-src");
          const src =
            zoomUrl ||
            img.src ||
            img.getAttribute("data-src") ||
            img.getAttribute("data-lazy-src") ||
            img
              .getAttribute("data-srcset")
              ?.split(",")[0]
              ?.trim()
              .split(/\s+/)[0];
          if (!src) continue;
          // Images in thumbnail strips must meet min main size so we skip small carousel thumbs
          const inThumbStrip = isInThumbnailStrip(img);
          const skipSize = !inThumbStrip;
          const minSize = inThumbStrip ? MIN_MAIN_IMAGE_SIZE : MIN_IMAGE_SIZE;
          add(src, img, skipSize, minSize);
        }
      }
    } catch {
      /* selector may not be valid in some contexts */
    }
  }

  // 3b. Magento / Fotorama: images in nav or as data attributes on parent
  const galleryParents = document.querySelectorAll(
    '[class*="fotorama"], [data-gallery-role], .gallery-placeholder, [class*="media-gallery"]'
  );
  for (const parent of Array.from(galleryParents)) {
    const links = parent.querySelectorAll(
      'a[href*=".jpg"], a[href*=".jpeg"], a[href*=".png"], a[href*=".webp"]'
    );
    for (const a of Array.from(links)) {
      const href = a.getAttribute("href");
      if (href) add(href, undefined, true);
    }
    const imgs = parent.querySelectorAll("img");
    for (const img of Array.from(imgs)) {
      if (img instanceof HTMLImageElement) {
        const zoomUrl =
          img.getAttribute("data-zoom-image") ||
          img.getAttribute("data-zoom-src");
        const src =
          zoomUrl ||
          img.src ||
          img.getAttribute("data-src") ||
          img.getAttribute("data-lazy-src") ||
          img
            .getAttribute("data-srcset")
            ?.split(",")[0]
            ?.trim()
            .split(/\s+/)[0];
        if (!src) continue;
        const inThumbStrip = isInThumbnailStrip(img);
        add(
          src,
          img,
          !inThumbStrip,
          inThumbStrip ? MIN_MAIN_IMAGE_SIZE : MIN_IMAGE_SIZE
        );
      }
    }
  }

  // 3c. Elements with data attributes pointing to full-size images
  const imageDataEls = document.querySelectorAll(
    "[data-image], [data-zoom-image], [data-zoom-src]"
  );
  for (const el of Array.from(imageDataEls)) {
    const url =
      el.getAttribute("data-image") ||
      el.getAttribute("data-zoom-image") ||
      el.getAttribute("data-zoom-src");
    if (
      url &&
      (url.startsWith("http") || url.startsWith("//") || url.startsWith("/"))
    ) {
      add(url, undefined, true);
    }
  }

  // 3d. Parse srcset for additional image URLs (e.g. "url1 1x, url2 2x")
  const srcsetImgs = document.querySelectorAll("img[srcset]");
  for (const img of Array.from(srcsetImgs)) {
    if (!(img instanceof HTMLImageElement)) continue;
    const srcset = img.getAttribute("srcset");
    if (srcset) {
      const inThumbStrip = isInThumbnailStrip(img);
      for (const part of srcset.split(",")) {
        const trimmed = part.trim().split(/\s+/)[0];
        if (trimmed)
          add(
            trimmed,
            img,
            !inThumbStrip,
            inThumbStrip ? MIN_MAIN_IMAGE_SIZE : MIN_IMAGE_SIZE
          );
      }
    }
  }

  // 4. Any img with product-related parent (include lazy-loaded; skip strict size check)
  const productContainers = document.querySelectorAll(
    '[class*="product"], [id*="product"], [data-product], .product-info, .product-detail, main, [role="main"]'
  );
  for (const container of Array.from(productContainers)) {
    const imgs = container.querySelectorAll("img");
    for (const img of Array.from(imgs)) {
      if (img instanceof HTMLImageElement) {
        const zoomUrl =
          img.getAttribute("data-zoom-image") ||
          img.getAttribute("data-zoom-src");
        const src =
          zoomUrl ||
          img.src ||
          img.getAttribute("data-src") ||
          img.getAttribute("data-lazy-src");
        if (!src) continue;
        const inThumbStrip = isInThumbnailStrip(img);
        add(
          src,
          img,
          !inThumbStrip,
          inThumbStrip ? MIN_MAIN_IMAGE_SIZE : MIN_IMAGE_SIZE
        );
      }
    }
  }

  // 5. Fallback: first few large images on page (excluding header/nav)
  if (byCanonical.size === 0) {
    const allImgs = document.querySelectorAll("img");
    for (const img of Array.from(allImgs)) {
      if (img instanceof HTMLImageElement && !isInHeaderNav(img)) {
        const src = img.src || img.getAttribute("data-src");
        if (
          src &&
          (img.naturalWidth >= MIN_IMAGE_SIZE || img.width >= MIN_IMAGE_SIZE)
        ) {
          add(src, img);
        }
      }
    }
  }

  // Return high-res URLs (favors best quality when fetching)
  const result = Array.from(byCanonical.values()).map(getHighResImageUrl);
  return result.slice(0, MAX_GALLERY_IMAGES);
}

/**
 * Common car manufacturers to filter out from brand extraction
 * These should not be extracted as part brands
 */
const CAR_MANUFACTURERS = [
  "Porsche",
  "BMW",
  "Mercedes",
  "Mercedes-Benz",
  "Audi",
  "Toyota",
  "Honda",
  "Nissan",
  "Mazda",
  "Subaru",
  "Mitsubishi",
  "Lexus",
  "Acura",
  "Infiniti",
  "Ford",
  "Chevrolet",
  "Chevy",
  "Dodge",
  "Jeep",
  "Ram",
  "Chrysler",
  "Cadillac",
  "Lincoln",
  "Buick",
  "GMC",
  "Volkswagen",
  "VW",
  "Volvo",
  "Jaguar",
  "Land Rover",
  "Range Rover",
  "Mini",
  "Fiat",
  "Alfa Romeo",
  "Maserati",
  "Ferrari",
  "Lamborghini",
  "McLaren",
  "Aston Martin",
  "Bentley",
  "Rolls-Royce",
  "Tesla",
  "Lotus",
  "Genesis",
  "Hyundai",
  "Kia",
];

/**
 * Check if a string is a car manufacturer (to filter out)
 */
function isCarManufacturer(text: string): boolean {
  const normalized = normalizeBrand(text);
  return CAR_MANUFACTURERS.some(
    (manufacturer) => normalizeBrand(manufacturer) === normalized
  );
}

/**
 * Extract brand from domain name
 * e.g., "adro.com" -> "ADRO", "martiniworks.com" -> "MartiniWorks"
 */
function extractBrandFromDomain(): string | null {
  try {
    const hostname = window.location.hostname;
    // Remove www. and common TLDs
    let domain = hostname
      .replace(/^www\./, "")
      .replace(/\.(com|net|org|io|co|us|uk|ca|au)$/i, "");

    // Split by dots and take the main part
    const parts = domain.split(".");
    domain = parts[parts.length - 1] || domain;

    // Capitalize appropriately (handle camelCase domains)
    if (domain.length >= 2 && domain.length <= 30) {
      // Check if it's already a known brand
      const known = isKnownBrand(domain);
      if (known) {
        return known;
      }

      // Convert to proper case (ADRO, MartiniWorks, etc.)
      // If all uppercase or has mixed case, preserve it
      if (/^[A-Z]+$/.test(domain)) {
        return domain; // Already uppercase
      } else if (/^[A-Z][a-z]+[A-Z]/.test(domain)) {
        return domain; // CamelCase like "MartiniWorks"
      } else {
        // Convert to title case
        return domain.charAt(0).toUpperCase() + domain.slice(1).toLowerCase();
      }
    }
  } catch (error) {
    // Ignore errors
  }
  return null;
}

/**
 * Extract brand from site header/footer/branding
 */
function extractBrandFromSiteBranding(): string | null {
  // Look for brand in common locations
  const brandSelectors = [
    'header [class*="logo"]',
    'header [class*="brand"]',
    'footer [class*="logo"]',
    'footer [class*="brand"]',
    '[class*="site-brand"]',
    '[class*="company-name"]',
    'h1[class*="logo"]',
    ".logo",
    "#logo",
  ];

  for (const selector of brandSelectors) {
    const elems = document.querySelectorAll(selector);
    for (const elem of Array.from(elems)) {
      const text = elem.textContent?.trim();
      const alt = elem.getAttribute("alt");
      const title = elem.getAttribute("title");
      const ariaLabel = elem.getAttribute("aria-label");

      const candidates = [text, alt, title, ariaLabel].filter(Boolean);
      for (const candidate of candidates) {
        if (candidate && candidate.length >= 2 && candidate.length <= 30) {
          // Skip if it's a car manufacturer
          if (!isCarManufacturer(candidate)) {
            const known = isKnownBrand(candidate);
            if (known) {
              return known;
            }
            // If it looks like a brand name (capitalized, reasonable length)
            if (/^[A-Z][A-Za-z0-9]+$/.test(candidate)) {
              return candidate;
            }
          }
        }
      }
    }
  }

  // Look in page title for site name
  const pageTitle = document.querySelector("title");
  if (pageTitle) {
    const titleText = pageTitle.textContent || "";
    // Common patterns: "Brand Name - Product" or "Product | Brand Name"
    const patterns = [
      /^([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)\s*[-|–]\s*/,
      /\s*[-|–]\s*([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)$/,
    ];

    for (const pattern of patterns) {
      const match = titleText.match(pattern);
      if (match && match[1]) {
        const brand = match[1].trim();
        if (
          !isCarManufacturer(brand) &&
          brand.length >= 2 &&
          brand.length <= 30
        ) {
          const known = isKnownBrand(brand);
          if (known) {
            return known;
          }
          return brand;
        }
      }
    }
  }

  return null;
}

/**
 * Comprehensive list of known car part brands
 * Used for pattern matching and validation
 */
const KNOWN_CAR_PART_BRANDS = [
  // Exhaust
  "AWE",
  "Borla",
  "Akrapovic",
  "Milltek",
  "Remus",
  "Invidia",
  "Magnaflow",
  "Corsa",
  "Flowmaster",
  "Tanabe",
  "HKS",
  "Greddy",
  "Blitz",

  // Suspension
  "KW",
  "Ohlins",
  "Bilstein",
  "Koni",
  "Tein",
  "BC Racing",
  "Fortune Auto",
  "H&R",
  "Eibach",
  "Swift",
  "Ground Control",

  // Engine/Tuning
  "APR",
  "Cobb",
  "Unitronic",
  "Revo",
  "GIAC",
  "Burger Motorsports",
  "JB4",
  "Injen",
  "AEM",
  "K&N",
  "AFE Power",
  "Mishimoto",
  "CSF",
  "Garrett",
  "BorgWarner",
  "Precision Turbo",

  // Wheels
  "Volk",
  "Rays",
  "Work",
  "Enkei",
  "WedsSport",
  "Rota",
  "Konig",
  "XXR",
  "Rotiform",
  "Fifteen52",
  "OZ Racing",
  "BBS",
  "Forgeline",
  "HRE",
  "Motegi",
  "Advan",
  "Stage",
  "Fifteen52",

  // Brakes
  "Brembo",
  "StopTech",
  "Wilwood",
  "EBC",
  "Hawk",
  "Ferodo",
  "Carbotech",

  // Body/Aero
  "Seibon",
  "VIS",
  "Carbon Creations",
  "Verus",
  "Aeroflow",
  "APR Performance",
  "Anderson Composites",
  "MAD",
  "MST",
  "Armaspeed",
  "ADRO",

  // Interior
  "Recaro",
  "Bride",
  "Sparco",
  "Takata",
  "Schroth",
  "Crow",
  "Corbeau",

  // Lighting
  "Morimoto",
  "Diode Dynamics",
  "GTR Lighting",
  "Spyder",
  "Anzo",

  // Other
  "Active",
  "Autowerke",
  "ECS Tuning",
  "FCP Euro",
  "Turner Motorsport",
  "VRSF",
  "Evolution Racewerks",
  "Wagner Tuning",
];

/**
 * Normalize brand name for comparison
 */
function normalizeBrand(brand: string): string {
  return brand
    .trim()
    .replace(/\s+/g, " ") // Normalize whitespace
    .replace(/[™®©]/g, "") // Remove trademark symbols
    .replace(/\./g, "") // Remove periods
    .toUpperCase();
}

/**
 * Check if a string matches a known brand (case-insensitive, fuzzy)
 */
function isKnownBrand(text: string): string | null {
  const normalized = normalizeBrand(text);

  // Exact match
  for (const brand of KNOWN_CAR_PART_BRANDS) {
    if (normalizeBrand(brand) === normalized) {
      return brand; // Return original casing
    }
  }

  // Starts with match (handles "AWE Tuning" -> "AWE")
  for (const brand of KNOWN_CAR_PART_BRANDS) {
    const normalizedBrand = normalizeBrand(brand);
    if (
      normalized.startsWith(normalizedBrand) ||
      normalizedBrand.startsWith(normalized)
    ) {
      return brand;
    }
  }

  // Contains match (handles variations)
  for (const brand of KNOWN_CAR_PART_BRANDS) {
    const normalizedBrand = normalizeBrand(brand);
    if (
      normalized.includes(normalizedBrand) ||
      normalizedBrand.includes(normalized)
    ) {
      // Only return if the match is substantial (at least 3 chars)
      if (normalized.length >= 3 && normalizedBrand.length >= 3) {
        return brand;
      }
    }
  }

  return null;
}

/**
 * Extract brand name using multiple strategies
 * Returns the most confident match found
 */
function extractBrand(): string | null {
  const candidates: Array<{
    brand: string;
    confidence: number;
    source: string;
  }> = [];

  // Strategy 0: Extract from domain name (highest confidence for site-specific brands)
  // This catches cases like adro.com -> ADRO
  const domainBrand = extractBrandFromDomain();
  if (domainBrand) {
    const known = isKnownBrand(domainBrand);
    if (known) {
      candidates.push({
        brand: known,
        confidence: 0.9,
        source: "domain",
      });
    } else {
      // Even if not in known list, domain is a strong signal
      candidates.push({
        brand: domainBrand,
        confidence: 0.85,
        source: "domain",
      });
    }
  }

  // Strategy 0b: Extract from site branding (header/footer/logo)
  const siteBrand = extractBrandFromSiteBranding();
  if (siteBrand) {
    const known = isKnownBrand(siteBrand);
    if (known) {
      candidates.push({
        brand: known,
        confidence: 0.88,
        source: "site-branding",
      });
    } else {
      candidates.push({
        brand: siteBrand,
        confidence: 0.8,
        source: "site-branding",
      });
    }
  }

  // Strategy 1: Structured data (Schema.org, Open Graph, JSON-LD)
  // Highest confidence - these are explicitly marked as brand
  const structuredSelectors = [
    '[itemprop="brand"]',
    '[itemprop="manufacturer"]',
    'meta[property="product:brand"]',
    'meta[property="og:brand"]',
    "[data-brand]",
    "[data-manufacturer]",
  ];

  for (const selector of structuredSelectors) {
    const elem = document.querySelector(selector);
    if (elem) {
      const brand =
        elem.textContent?.trim() ||
        elem.getAttribute("content") ||
        elem.getAttribute("data-brand") ||
        elem.getAttribute("data-manufacturer");
      if (brand) {
        const normalized = brand.trim();
        const known = isKnownBrand(normalized);
        if (known) {
          candidates.push({
            brand: known,
            confidence: 0.95,
            source: "structured",
          });
        } else if (normalized.length > 1 && normalized.length < 50) {
          // Accept even if not in known list if from structured data
          candidates.push({
            brand: normalized,
            confidence: 0.85,
            source: "structured",
          });
        }
      }
    }
  }

  // Strategy 2: CSS class/id patterns (high confidence)
  const classPatternSelectors = [
    '[class*="brand"]',
    '[class*="vendor"]',
    '[class*="manufacturer"]',
    '[id*="brand"]',
    '[id*="vendor"]',
    '[id*="manufacturer"]',
    ".product-brand",
    ".vendor-name",
    ".manufacturer-name",
  ];

  for (const selector of classPatternSelectors) {
    const elems = document.querySelectorAll(selector);
    for (const elem of Array.from(elems)) {
      const text = elem.textContent?.trim();
      if (text && text.length > 1 && text.length < 50) {
        const known = isKnownBrand(text);
        if (known) {
          candidates.push({
            brand: known,
            confidence: 0.8,
            source: "css-selector",
          });
        }
      }
    }
  }

  // Strategy 3: Breadcrumb navigation
  // Often contains "Home > Brand > Category > Product"
  const breadcrumbSelectors = [
    '[class*="breadcrumb"]',
    '[class*="bread-crumb"]',
    'nav[aria-label*="breadcrumb" i]',
    'ol[class*="breadcrumb"]',
  ];

  for (const selector of breadcrumbSelectors) {
    const breadcrumb = document.querySelector(selector);
    if (breadcrumb) {
      const links = breadcrumb.querySelectorAll("a, span");
      for (const link of Array.from(links)) {
        const text = link.textContent?.trim();
        if (text) {
          const known = isKnownBrand(text);
          if (known) {
            candidates.push({
              brand: known,
              confidence: 0.75,
              source: "breadcrumb",
            });
          }
        }
      }
    }
  }

  // Strategy 4: URL patterns
  // Some sites use /brand/product-name or /brands/brand-name
  const url = window.location.href;
  const urlMatch = url.match(
    /\/(?:brand|brands|vendor|manufacturer)[\/-]([^\/\?&#]+)/i
  );
  if (urlMatch && urlMatch[1]) {
    const brandFromUrl = decodeURIComponent(urlMatch[1]).replace(/[-_]/g, " ");
    const known = isKnownBrand(brandFromUrl);
    if (known) {
      candidates.push({ brand: known, confidence: 0.7, source: "url" });
    }
  }

  // Strategy 5: Product name parsing (first word or known pattern)
  // IMPORTANT: Filter out car manufacturers from product names
  const productName = extractProductName();
  if (productName) {
    const words = productName.split(/\s+/);

    // Check first word (but skip if it's a car manufacturer)
    if (words[0] && !isCarManufacturer(words[0])) {
      const known = isKnownBrand(words[0]);
      if (known) {
        candidates.push({
          brand: known,
          confidence: 0.65,
          source: "product-name-first",
        });
      } else {
        // Even if not in known list, if first word is capitalized and reasonable length, it might be a brand
        const firstWord = words[0];
        if (
          firstWord.length >= 2 &&
          firstWord.length <= 20 &&
          /^[A-Z][a-z]+$/.test(firstWord) // Starts with capital, rest lowercase
        ) {
          candidates.push({
            brand: firstWord,
            confidence: 0.5,
            source: "product-name-first-fallback",
          });
        }
      }
    }

    // Check first two words (for "AWE Tuning" -> "AWE")
    // Skip if first word is a car manufacturer
    if (words.length >= 2 && words[0] && !isCarManufacturer(words[0])) {
      const firstTwo = words.slice(0, 2).join(" ");
      const known = isKnownBrand(firstTwo);
      if (known) {
        candidates.push({
          brand: known,
          confidence: 0.6,
          source: "product-name-prefix",
        });
      }
    }

    // Check second word if first is a car manufacturer (e.g., "Porsche 718 ADRO Diffuser")
    if (words.length >= 2 && words[0] && isCarManufacturer(words[0])) {
      if (words[1] && !isCarManufacturer(words[1])) {
        const known = isKnownBrand(words[1]);
        if (known) {
          candidates.push({
            brand: known,
            confidence: 0.55,
            source: "product-name-after-car",
          });
        }
      }
    }
  }

  // Strategy 5b: Look for "Shop all [Brand]" or similar patterns
  const shopAllPattern =
    /(?:shop\s+all|view\s+all|see\s+all|browse\s+all)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)/i;
  const allLinks = document.querySelectorAll("a");
  for (const link of Array.from(allLinks)) {
    const text = link.textContent?.trim();
    if (text) {
      const match = text.match(shopAllPattern);
      if (match && match[1]) {
        const known = isKnownBrand(match[1]);
        if (known) {
          candidates.push({
            brand: known,
            confidence: 0.72,
            source: "shop-all-link",
          });
        } else {
          // Even if not known, this is a strong signal
          const brandText = match[1].trim();
          if (brandText.length >= 2 && brandText.length <= 30) {
            candidates.push({
              brand: brandText,
              confidence: 0.65,
              source: "shop-all-link-fallback",
            });
          }
        }
      }
    }
  }

  // Strategy 5c: Look for standalone brand mentions near product title
  const productTitle = document.querySelector(
    'h1, [class*="product-title"], [class*="product-name"]'
  );
  if (productTitle) {
    const titleParent = productTitle.parentElement;
    if (titleParent) {
      // Look for brand mentions in siblings or nearby elements
      const nearbyElements = [
        ...Array.from(titleParent.querySelectorAll("*")),
        ...Array.from(
          productTitle.nextElementSibling
            ? [productTitle.nextElementSibling]
            : []
        ),
        ...Array.from(
          productTitle.previousElementSibling
            ? [productTitle.previousElementSibling]
            : []
        ),
      ];

      for (const elem of nearbyElements) {
        const text = elem.textContent?.trim();
        if (text && text.length >= 2 && text.length <= 30) {
          // Check if it's a standalone brand mention (not part of a sentence)
          if (/^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?$/.test(text)) {
            const known = isKnownBrand(text);
            if (known) {
              candidates.push({
                brand: known,
                confidence: 0.68,
                source: "nearby-element",
              });
            }
          }
        }
      }
    }
  }

  // Strategy 6: Description text (look for "by Brand" or "Brand product")
  const description = extractDescription();
  if (description) {
    // Look for patterns like "by Brand", "Brand's", "from Brand"
    const brandPatterns = [
      /\bby\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b/i,
      /\bfrom\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b/i,
      /\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)'s\b/,
    ];

    for (const pattern of brandPatterns) {
      const match = description.match(pattern);
      if (match && match[1]) {
        const known = isKnownBrand(match[1]);
        if (known) {
          candidates.push({
            brand: known,
            confidence: 0.55,
            source: "description",
          });
        }
      }
    }
  }

  // Strategy 7: Image alt text
  const images = document.querySelectorAll(
    'img[alt*="brand" i], img[alt*="logo" i]'
  );
  for (const img of Array.from(images)) {
    const alt = img.getAttribute("alt");
    if (alt) {
      const known = isKnownBrand(alt);
      if (known) {
        candidates.push({ brand: known, confidence: 0.5, source: "image-alt" });
      }
    }
  }

  // Strategy 8: Meta tags
  const metaTags = [
    'meta[name="brand"]',
    'meta[name="manufacturer"]',
    'meta[name="vendor"]',
  ];

  for (const selector of metaTags) {
    const meta = document.querySelector(selector);
    if (meta) {
      const content = meta.getAttribute("content");
      if (content) {
        const known = isKnownBrand(content);
        if (known) {
          candidates.push({
            brand: known,
            confidence: 0.75,
            source: "meta-tag",
          });
        }
      }
    }
  }

  // Filter out car manufacturers from candidates
  const filteredCandidates = candidates.filter(
    (c) => !isCarManufacturer(c.brand)
  );

  // Return the highest confidence candidate
  if (filteredCandidates.length > 0) {
    // Sort by confidence (highest first)
    filteredCandidates.sort((a, b) => b.confidence - a.confidence);

    // Prioritize domain/site-branding matches (they're most reliable for site-specific brands)
    const siteMatch = filteredCandidates.find(
      (c) =>
        (c.source === "domain" || c.source === "site-branding") &&
        c.confidence >= 0.8
    );
    if (siteMatch) {
      return siteMatch.brand;
    }

    // If we have a high-confidence structured data match, use it
    const structuredMatch = filteredCandidates.find(
      (c) => c.source === "structured" && c.confidence >= 0.85
    );
    if (structuredMatch) {
      return structuredMatch.brand;
    }

    // Prefer known brands over unknown ones if confidence is similar
    const knownBrandMatch = filteredCandidates.find((c) => {
      const normalized = normalizeBrand(c.brand);
      return KNOWN_CAR_PART_BRANDS.some(
        (b) => normalizeBrand(b) === normalized
      );
    });

    if (knownBrandMatch && knownBrandMatch.confidence >= 0.5) {
      return knownBrandMatch.brand;
    }

    // Otherwise, return the highest confidence match
    if (filteredCandidates.length > 0 && filteredCandidates[0]) {
      return filteredCandidates[0].brand;
    }
  }

  return null;
}

/**
 * Normalize part number / SKU by stripping common prefixes so we get the actual code.
 * E.g. "SKU: A18A20-2401" -> "A18A20-2401"
 */
function normalizePartNumber(raw: string): string {
  let s = raw.trim();
  const prefixes = [
    /^SKU\s*:\s*/i,
    /^Part\s*#\s*:\s*/i,
    /^Part\s*Number\s*:\s*/i,
    /^Item\s*#\s*:\s*/i,
    /^Product\s*Code\s*:\s*/i,
    /^Model\s*#?\s*:\s*/i,
    /^Code\s*:\s*/i,
  ];
  for (const re of prefixes) {
    s = s.replace(re, "");
  }
  return s.trim();
}

/**
 * Extract part number/SKU (returns normalized value without "SKU:" etc.)
 */
function extractPartNumber(): string | null {
  const skuSelectors = [
    '[class*="sku"]',
    '[id*="sku"]',
    '[itemprop="sku"]',
    '[class*="part-number"]',
    '[class*="product-code"]',
  ];

  for (const selector of skuSelectors) {
    const elem = document.querySelector(selector);
    if (elem) {
      const raw = elem.textContent?.trim() || elem.getAttribute("content");
      if (raw) return normalizePartNumber(raw) || null;
    }
  }

  return null;
}

/**
 * Check if text looks like navigation/promotional text
 */
function isNavigationText(text: string): boolean {
  if (!text || text.length <= 3) return true;

  const lower = text.toLowerCase();
  const navWords = [
    "about",
    "contact",
    "shop",
    "home",
    "cart",
    "account",
    "search",
    "menu",
    "close",
    "login",
    "sign in",
    "sign up",
    "register",
    "buy now",
    "pay later",
    "learn more",
    "promotion",
  ];

  return navWords.some((word) => lower.includes(word));
}

/**
 * Check if element is in header/nav
 */
function isInHeaderNav(element: Element): boolean {
  let parent = element.parentElement;
  while (parent && parent.tagName !== "BODY") {
    const tagName = parent.tagName.toLowerCase();
    const className = parent.className?.toString().toLowerCase() || "";
    const id = parent.id?.toLowerCase() || "";

    if (
      tagName === "header" ||
      tagName === "nav" ||
      className.includes("header") ||
      className.includes("nav") ||
      className.includes("promo") ||
      className.includes("banner") ||
      id.includes("header") ||
      id.includes("nav")
    ) {
      return true;
    }

    parent = parent.parentElement;
  }

  return false;
}

/**
 * Clean up title text
 */
function cleanTitle(title: string): string | null {
  if (!title) return null;

  // Remove site name suffixes
  if (title.includes(" | ")) {
    const splitTitle = title.split(" | ")[0];
    if (splitTitle) {
      title = splitTitle.trim();
    }
  }
  if (title.includes(" - ")) {
    const parts = title.split(" - ");
    if (
      parts.length > 1 &&
      parts[parts.length - 1]?.toLowerCase().includes("shop")
    ) {
      title = parts.slice(0, -1).join(" - ").trim();
    }
  }

  return title;
}
