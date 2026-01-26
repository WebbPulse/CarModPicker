/**
 * Content script for scraping product information from web pages
 */

import type { ScrapedProductData } from "./types";

// Listen for messages from popup
chrome.runtime.onMessage.addListener(
  (
    request: { action: string },
    _sender,
    sendResponse: (response: {
      success: boolean;
      data: ScrapedProductData;
    }) => void,
  ) => {
    if (request.action === "scrapePage") {
      const scrapedData = scrapeProductData();
      sendResponse({ success: true, data: scrapedData });
      return true; // Keep channel open for async response
    }
    return false;
  },
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

  // Extract image URL
  data.image_url = extractImageUrl();

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

/**
 * Extract price from the page
 */
function extractPrice(): number | null {
  // Find all price-like text
  const pricePattern = /\$[\d,]+\.?\d*/g;
  const pageText = document.body.textContent || "";
  const prices = pageText.match(pricePattern) || [];

  if (prices.length === 0) return null;

  // Try structured data first
  const priceElem =
    document.querySelector('[itemprop="price"]') ||
    document.querySelector("[data-price]") ||
    document.querySelector('[class*="price"]');

  if (priceElem) {
    const priceText =
      priceElem.textContent ||
      priceElem.getAttribute("content") ||
      priceElem.getAttribute("data-price") ||
      "";
    const price = extractPriceValue(priceText);
    if (price) return price;
  }

  // Fallback to first price found
  if (prices.length > 0 && prices[0]) {
    return extractPriceValue(prices[0]);
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

/**
 * Extract product image URL
 */
function extractImageUrl(): string | null {
  // Try Open Graph image first
  const ogImage = document.querySelector('meta[property="og:image"]');
  if (ogImage && ogImage instanceof HTMLMetaElement && ogImage.content) {
    const url = ogImage.content.trim();
    if (url && url.startsWith("http")) {
      return url;
    }
  }

  // Try common product image selectors
  const imgSelectors = [
    '[class*="product"][class*="image"] img',
    '[class*="main"][class*="image"] img',
    '[id*="product"][id*="image"] img',
    '[itemprop="image"]',
    'img[class*="product"]',
  ];

  for (const selector of imgSelectors) {
    const img = document.querySelector(selector);
    if (img && img instanceof HTMLImageElement) {
      const src =
        img.src ||
        img.getAttribute("data-src") ||
        img.getAttribute("data-lazy-src");
      if (src) {
        // Convert relative URLs to absolute
        if (src.startsWith("http")) {
          return src;
        } else if (src.startsWith("//")) {
          return window.location.protocol + src;
        } else {
          return new URL(src, window.location.href).href;
        }
      }
    }
  }

  // Fallback to first large image
  const images = document.querySelectorAll("img");
  for (const img of Array.from(images)) {
    if (img instanceof HTMLImageElement) {
      const src = img.src;
      if (src && (img.naturalWidth > 200 || img.width > 200)) {
        if (src.startsWith("http")) {
          return src;
        } else if (src.startsWith("//")) {
          return window.location.protocol + src;
        } else {
          return new URL(src, window.location.href).href;
        }
      }
    }
  }

  return null;
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
    (manufacturer) => normalizeBrand(manufacturer) === normalized,
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
    '.logo',
    '#logo',
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
        if (!isCarManufacturer(brand) && brand.length >= 2 && brand.length <= 30) {
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
        confidence: 0.90,
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
        confidence: 0.80,
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
    /\/(?:brand|brands|vendor|manufacturer)[\/-]([^\/\?&#]+)/i,
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
    'h1, [class*="product-title"], [class*="product-name"]',
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
            : [],
        ),
        ...Array.from(
          productTitle.previousElementSibling
            ? [productTitle.previousElementSibling]
            : [],
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
    'img[alt*="brand" i], img[alt*="logo" i]',
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
    (c) => !isCarManufacturer(c.brand),
  );

  // Return the highest confidence candidate
  if (filteredCandidates.length > 0) {
    // Sort by confidence (highest first)
    filteredCandidates.sort((a, b) => b.confidence - a.confidence);

    // Prioritize domain/site-branding matches (they're most reliable for site-specific brands)
    const siteMatch = filteredCandidates.find(
      (c) => (c.source === "domain" || c.source === "site-branding") && c.confidence >= 0.80,
    );
    if (siteMatch) {
      return siteMatch.brand;
    }

    // If we have a high-confidence structured data match, use it
    const structuredMatch = filteredCandidates.find(
      (c) => c.source === "structured" && c.confidence >= 0.85,
    );
    if (structuredMatch) {
      return structuredMatch.brand;
    }

    // Prefer known brands over unknown ones if confidence is similar
    const knownBrandMatch = filteredCandidates.find((c) => {
      const normalized = normalizeBrand(c.brand);
      return KNOWN_CAR_PART_BRANDS.some(
        (b) => normalizeBrand(b) === normalized,
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
 * Extract part number/SKU
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
      const sku = elem.textContent?.trim() || elem.getAttribute("content");
      if (sku) return sku;
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
