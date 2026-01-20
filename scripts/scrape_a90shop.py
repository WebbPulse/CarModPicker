#!/usr/bin/env python3
"""
Web scraper for a90shop.com to import parts into the CarModPicker database.

This script:
- Respects robots.txt
- Scrapes product information from a90shop.com
- Maps data to GlobalPart schema
- Creates parts in the database with source='scraped'
- Supports test runs with limited page counts

Usage:
    cd backend
    python ../scripts/scrape_a90shop.py --max-pages 20 --dry-run
    python ../scripts/scrape_a90shop.py --max-pages 20  # Actually create parts
"""

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

# Add backend directory to path so we can import app modules
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Load .env file from backend directory before importing app modules
from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Loaded .env file from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

from sqlalchemy.orm import Session

from app.api.models.car import Car  # pyright: ignore[reportMissingImports]
from app.api.models.category import Category  # pyright: ignore[reportMissingImports]
from app.api.models.global_part import (  # pyright: ignore[reportMissingImports]
    GlobalPart,
)
from app.api.models.user import User  # pyright: ignore[reportMissingImports]
from app.db.session import SessionLocal  # pyright: ignore[reportMissingImports]


# Configuration
BASE_URL = "https://www.a90shop.com"
USER_AGENT = "CarModPicker-Scraper/1.0 (+https://github.com/yourusername/CarModPicker)"
REQUEST_DELAY = 2  # Seconds between requests to be respectful
MAX_RETRIES = 3

# Category mapping from a90shop.com to our category names
CATEGORY_MAPPING = {
    "exhaust": "exhaust",
    "exhausts": "exhaust",
    "downpipes": "exhaust",
    "suspension": "suspension",
    "coilovers": "suspension",
    "springs": "suspension",
    "air-intakes": "engine",
    "intakes": "engine",
    "turbos": "engine",
    "turbo-kits": "engine",
    "tuning": "engine",
    "cooling": "engine",
    "charge-pipes": "engine",
    "fuel": "engine",
    "brakes": "brakes",
    "wheels": "wheels",
    "carbon-fiber": "body",
    "exterior": "body",
    "aerodynamics": "body",
    "spoilers": "body",
    "interior": "interior",
    "lighting": "exterior",
    "mirrors": "exterior",
    "maintenance": "other",
    "accessories": "other",
}

# Car matching patterns - try to match product titles/descriptions to cars
CAR_MATCHING_PATTERNS = {
    "Toyota": {
        "Supra": [
            r"a90",
            r"mkv",
            r"mk5",
            r"supra",
            r"gr\s+supra",
        ],
        "GR86": [
            r"gr\s*86",
            r"gr86",
            r"zn8",
            r"zd8",
            r"gr\s*86",
        ],
        "BRZ": [
            r"brz",
            r"subaru\s+brz",
        ],
        "GR Corolla": [
            r"gr\s*corolla",
            r"grcorolla",
            r"gzea14",
        ],
    },
    "Subaru": {
        "BRZ": [
            r"brz",
            r"subaru\s+brz",
        ],
    },
}


class A90ShopScraper:
    """Scraper for a90shop.com that respects robots.txt and rate limits."""

    def __init__(self, dry_run: bool = False, max_pages: int = 20):
        self.dry_run = dry_run
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.robots_parser: Optional[RobotFileParser] = None
        self.scraped_count = 0
        self.created_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def check_robots_txt(self) -> bool:
        """Check robots.txt and return True if scraping is allowed."""
        try:
            robots_url = urljoin(BASE_URL, "/robots.txt")
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()

            # Check if we can fetch the robots.txt
            can_fetch = self.robots_parser.can_fetch(USER_AGENT, BASE_URL)
            if not can_fetch:
                print(f"WARNING: robots.txt disallows scraping for {USER_AGENT}")
                print("Proceeding anyway for proof of concept, but be aware of this.")
            else:
                print("✓ robots.txt allows scraping")
            return True  # Always return True for PoC, but log the warning
        except Exception as e:
            print(f"Could not fetch robots.txt: {e}")
            print("Proceeding with respectful scraping (2s delay between requests)")
            return True

    def can_fetch_url(self, url: str) -> bool:
        """Check if we can fetch a URL according to robots.txt."""
        if self.robots_parser:
            return self.robots_parser.can_fetch(USER_AGENT, url)
        return True  # If no robots parser, allow it

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return BeautifulSoup object."""
        if not self.can_fetch_url(url):
            print(f"Skipping {url} - disallowed by robots.txt")
            return None

        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(REQUEST_DELAY)  # Be respectful
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, "html.parser")
            except requests.RequestException as e:
                print(
                    f"Error fetching {url} (attempt {attempt + 1}/{MAX_RETRIES}): {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(REQUEST_DELAY * (attempt + 1))  # Exponential backoff
                else:
                    self.error_count += 1
                    return None
        return None

    def extract_price(self, price_text: str) -> Optional[int]:
        """Extract price in cents from price text like '$1,299.00' or 'From $1,299.00'."""
        if not price_text:
            return None

        # Remove currency symbols and "From" prefix
        price_text = price_text.replace("$", "").replace(",", "").strip()
        price_text = re.sub(r"^[Ff]rom\s+", "", price_text)

        # Extract number
        match = re.search(r"(\d+\.?\d*)", price_text)
        if match:
            try:
                price_dollars = float(match.group(1))
                return int(price_dollars * 100)  # Convert to cents
            except ValueError:
                pass
        return None

    def detect_category_from_product(
        self, product_name: str, description: str, db: Session
    ) -> Optional[int]:
        """Detect category from product name and description using keyword matching."""
        text_to_search = f"{product_name} {description}".lower()

        # Category keywords mapping (order matters - more specific first)
        category_keywords = {
            "suspension": [
                "coilover",
                "coil-over",
                "suspension",
                "shock",
                "strut",
                "spring",
                "damping",
                "dampers",
                "lowering",
                "ride height",
            ],
            "exhaust": [
                "exhaust",
                "muffler",
                "downpipe",
                "down-pipe",
                "cat-back",
                "catback",
                "header",
                "manifold",
            ],
            "engine": [
                "intake",
                "turbo",
                "supercharger",
                "intercooler",
                "charge pipe",
                "cooling",
                "radiator",
                "tuning",
                "ecu",
                "fuel",
                "injector",
            ],
            "brakes": [
                "brake",
                "rotor",
                "caliper",
                "pad",
            ],
            "wheels": [
                "wheel",
                "rim",
                "tire",
                "tyre",
            ],
            "body": [
                "splitter",
                "spoiler",
                "wing",
                "diffuser",
                "aero",
                "carbon fiber",
                "carbon fibre",
                "body kit",
                "bumper",
                "fender",
            ],
            "interior": [
                "seat",
                "steering",
                "shift",
                "knob",
                "interior",
                "dash",
            ],
        }

        # Check for category keywords
        for category_name, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in text_to_search:
                    category = (
                        db.query(Category)
                        .filter(Category.name == category_name)
                        .first()
                    )
                    if category:
                        return category.id

        return None

    def map_category(self, category_name: str, db: Session) -> Optional[int]:
        """Map a90shop category to our category ID."""
        category_name_lower = category_name.lower().strip()

        # Try direct mapping
        mapped_name = CATEGORY_MAPPING.get(category_name_lower)
        if not mapped_name:
            # Try partial matching
            for key, value in CATEGORY_MAPPING.items():
                if key in category_name_lower or category_name_lower in key:
                    mapped_name = value
                    break

        if mapped_name:
            category = db.query(Category).filter(Category.name == mapped_name).first()
            if category:
                return category.id

        # Default to "other" category if no match
        other_category = db.query(Category).filter(Category.name == "other").first()
        if other_category:
            return other_category.id

        return None

    def match_car(
        self, product_name: str, description: str, db: Session
    ) -> Optional[int]:
        """Try to match product to a car in our database."""
        text_to_search = f"{product_name} {description}".lower()

        for make, models in CAR_MATCHING_PATTERNS.items():
            for model, patterns in models.items():
                for pattern in patterns:
                    if re.search(pattern, text_to_search, re.IGNORECASE):
                        # Try to find the car in database
                        # For Supra, look for A90/MKV generation
                        if model == "Supra":
                            car = (
                                db.query(Car)
                                .filter(
                                    Car.make == make,
                                    Car.model == model,
                                    Car.generation_name.ilike("%A90%"),
                                )
                                .first()
                            )
                            if not car:
                                car = (
                                    db.query(Car)
                                    .filter(
                                        Car.make == make,
                                        Car.model == model,
                                        Car.generation_name.ilike("%MKV%"),
                                    )
                                    .first()
                                )
                            if not car:
                                car = (
                                    db.query(Car)
                                    .filter(
                                        Car.make == make,
                                        Car.model == model,
                                    )
                                    .first()
                                )
                        elif model == "GR86" or model == "BRZ":
                            # For GR86/BRZ, try to match generation names
                            # Check for ZN8/ZD8 (GR86) or ZC6/ZD6 (BRZ) generation
                            if "zn8" in text_to_search or "zd8" in text_to_search:
                                car = (
                                    db.query(Car)
                                    .filter(
                                        Car.make == make,
                                        Car.model == model,
                                        Car.generation_name.ilike("%ZN8%"),
                                    )
                                    .first()
                                )
                                if not car:
                                    car = (
                                        db.query(Car)
                                        .filter(
                                            Car.make == make,
                                            Car.model == model,
                                            Car.generation_name.ilike("%ZD8%"),
                                        )
                                        .first()
                                    )
                            if not car:
                                car = (
                                    db.query(Car)
                                    .filter(Car.make == make, Car.model == model)
                                    .first()
                                )
                        else:
                            car = (
                                db.query(Car)
                                .filter(Car.make == make, Car.model == model)
                                .first()
                            )

                        if car:
                            return car.id

        return None

    def extract_product_data(
        self, soup: BeautifulSoup, product_url: str
    ) -> Optional[dict]:
        """Extract product data from a product page."""
        try:
            # Skip if this doesn't look like a product page
            if not self.is_product_page(soup):
                return None

            # Extract product name (title)
            # Promotional text and navigation text to exclude
            promotional_patterns = [
                r"buy\s+now.*pay\s+later",
                r"starting\s+at\s+0%",
                r"learn\s+more",
                r"apr",
                r"financing",
                r"promotion",
                r"^buy\s+now",
            ]

            # Common navigation/header text that should be excluded
            navigation_text = [
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
                "blog",
                "forum",
                "privacy",
                "terms",
                "policy",
                "shipping",
                "returns",
                "gift cards",
                "loyalty program",
                "wholesale",
                "services",
                "brands",
                "members",
            ]

            def is_promotional_text(text: str) -> bool:
                """Check if text is promotional."""
                if not text:
                    return True
                text_lower = text.lower().strip()
                return any(
                    re.search(pattern, text_lower, re.I)
                    for pattern in promotional_patterns
                )

            def is_navigation_text(text: str) -> bool:
                """Check if text is navigation/header text."""
                if not text:
                    return True
                text_lower = text.lower().strip()
                # Single word navigation items
                if text_lower in navigation_text:
                    return True
                # Very short text (likely navigation)
                if len(text_lower) <= 3:
                    return True
                return False

            name = None

            # Strategy 1: Try meta tags first (most reliable, not affected by page structure)
            og_title = soup.find("meta", {"property": "og:title"})
            if og_title:
                name = og_title.get("content", "").strip()
                if (
                    name
                    and not is_promotional_text(name)
                    and not is_navigation_text(name)
                    and len(name) > 5
                ):
                    pass  # Use this name
                else:
                    name = None

            # Strategy 2: Find h1 that's NOT in header/nav (skip promotional banners)
            if not name:
                all_h1s = soup.find_all("h1")
                for h1 in all_h1s:
                    h1_text = h1.get_text(strip=True)
                    if not h1_text or len(h1_text) < 5:
                        continue

                    # Skip promotional text and navigation text
                    if is_promotional_text(h1_text) or is_navigation_text(h1_text):
                        continue

                    # Check if parent is in header/nav (likely navigation, not product title)
                    parent = h1.parent
                    is_in_header_nav = False
                    while parent and parent.name != "body":
                        parent_class = parent.get("class", [])
                        parent_id = parent.get("id", "")
                        parent_name = parent.name.lower() if parent.name else ""

                        # Check if it's in header, nav, or promotional section
                        if (
                            parent_name in ["header", "nav"]
                            or any(
                                "header" in str(cls).lower()
                                or "nav" in str(cls).lower()
                                or "promo" in str(cls).lower()
                                or "banner" in str(cls).lower()
                                or "top-promotion" in str(cls).lower()
                                for cls in parent_class
                            )
                            or "header" in parent_id.lower()
                            or "nav" in parent_id.lower()
                            or "promo" in parent_id.lower()
                            or "banner" in parent_id.lower()
                        ):
                            is_in_header_nav = True
                            break
                        parent = parent.parent

                    if not is_in_header_nav:
                        name = h1_text
                        break

            # Strategy 3: Try title tag (but clean it up)
            if not name:
                title_tag = soup.find("title")
                if title_tag:
                    name = title_tag.get_text(strip=True)
                    # Clean up title tag if it contains site name
                    if " | " in name:
                        name = name.split(" | ")[0].strip()
                    if " - " in name and "a90shop" in name.lower():
                        parts = name.split(" - ")
                        if len(parts) > 1 and "a90shop" in parts[-1].lower():
                            name = " - ".join(parts[:-1]).strip()

                    if is_promotional_text(name) or len(name) < 5:
                        name = None

            if not name or len(name) < 5:
                return None

            # Clean up title - remove site name suffixes but keep product info
            if " | " in name:
                name = name.split(" | ")[0].strip()
            # Don't split on " - " if it's part of the product name (e.g., "Kit - Toyota GR86/BRZ")
            # Only remove if it's clearly a site suffix
            if " - " in name:
                parts = name.split(" - ")
                if len(parts) > 1 and "a90shop" in parts[-1].lower():
                    name = " - ".join(parts[:-1]).strip()

            # Final check - reject if it still looks like promotional or navigation text
            if is_promotional_text(name) or is_navigation_text(name):
                return None

            # Extract price - prioritize sale price over regular price
            price = None
            sale_price = None
            regular_price = None

            # Strategy: Look for all price elements and identify sale vs regular
            # a90shop.com structure: "Regular Price $X.XX" and "Sale Price $Y.YY"
            all_text = soup.get_text()

            # Find all price patterns in the page
            price_pattern = re.compile(r"\$[\d,]+\.?\d*")
            prices_found = price_pattern.findall(all_text)

            if prices_found:
                # Look for "Sale Price" text and get the price near it
                sale_idx = all_text.lower().find("sale price")
                if sale_idx != -1:
                    # Get text around "sale price" to find the associated price
                    nearby_text = all_text[max(0, sale_idx - 20) : sale_idx + 100]
                    sale_prices = price_pattern.findall(nearby_text)
                    if sale_prices:
                        sale_price = self.extract_price(sale_prices[0])

                # Look for "Regular Price" text
                regular_idx = all_text.lower().find("regular price")
                if regular_idx != -1:
                    nearby_text = all_text[max(0, regular_idx - 20) : regular_idx + 100]
                    regular_prices = price_pattern.findall(nearby_text)
                    if regular_prices:
                        regular_price = self.extract_price(regular_prices[0])

                # Use sale price if available, otherwise regular price, otherwise first price found
                if sale_price:
                    price = sale_price
                elif regular_price:
                    price = regular_price
                else:
                    # Fallback: use first price found (might be the only price)
                    price = self.extract_price(prices_found[0])

            # Also try structured selectors as backup
            if not price:
                price_selectors = [
                    {"class": re.compile(r"price", re.I)},
                    {"class": re.compile(r"product.*price", re.I)},
                    {"class": re.compile(r"amount", re.I)},
                    {"itemprop": "price"},
                    {"data-price": True},
                ]

                for selector in price_selectors:
                    price_elems = (
                        soup.find_all(class_=selector.get("class"))
                        if "class" in selector
                        else soup.find_all(attrs=selector)
                    )
                    for price_elem in price_elems:
                        price_text = (
                            price_elem.get_text(strip=True)
                            or price_elem.get("content", "")
                            or price_elem.get("data-price", "")
                        )
                        if price_text:
                            extracted = self.extract_price(price_text)
                            if extracted:
                                price = extracted
                                break
                    if price:
                        break

            # Extract description
            description = None
            desc_selectors = [
                ("div", {"class": re.compile(r"product.*description", re.I)}),
                ("div", {"class": re.compile(r"description", re.I)}),
                ("div", {"id": re.compile(r"description", re.I)}),
                ("meta", {"property": "og:description"}),
                ("meta", {"name": "description"}),
            ]

            for tag, attrs in desc_selectors:
                desc_elem = soup.find(tag, attrs)
                if desc_elem:
                    if tag == "meta":
                        description = desc_elem.get("content", "").strip()
                    else:
                        description = desc_elem.get_text(strip=True)
                    if description and len(description) > 10:
                        break

            # Extract image URL
            image_url = None
            img_selectors = [
                ("img", {"class": re.compile(r"product.*image|main.*image", re.I)}),
                ("img", {"id": re.compile(r"product.*image", re.I)}),
                ("meta", {"property": "og:image"}),
                ("img", {"itemprop": "image"}),
            ]

            for tag, attrs in img_selectors:
                img_elem = soup.find(tag, attrs)
                if img_elem:
                    if tag == "meta":
                        image_url = img_elem.get("content", "")
                    else:
                        image_url = (
                            img_elem.get("src")
                            or img_elem.get("data-src")
                            or img_elem.get("data-lazy-src")
                        )
                    if image_url:
                        if not image_url.startswith("http"):
                            image_url = urljoin(BASE_URL, image_url)
                        break

            # Extract brand (often in product name or breadcrumbs)
            brand = None
            brand_elem = soup.find(class_=re.compile(r"brand|vendor", re.I))
            if brand_elem:
                brand = brand_elem.get_text(strip=True)
            else:
                # Try to extract from product name (first word often)
                name_parts = name.split()
                if name_parts:
                    potential_brand = name_parts[0]
                    # Common brands on a90shop
                    known_brands = [
                        "AWE",
                        "HKS",
                        "KW",
                        "APR",
                        "Brembo",
                        "Injen",
                        "MST",
                        "Armaspeed",
                        "Seibon",
                        "Active",
                        "Autowerke",
                        "Garrett",
                        "Ohlins",
                        "Recaro",
                        "Volk",
                        "Rays",
                        "Work",
                        "Enkei",
                        "CSF",
                        "Borla",
                        "Akrapovic",
                        "Milltek",
                        "Remus",
                    ]
                    if potential_brand in known_brands:
                        brand = potential_brand

            # Extract part number/SKU
            part_number = None
            sku_selectors = [
                {"class": re.compile(r"sku|product.*sku", re.I)},
                {"itemprop": "sku"},
                {"id": re.compile(r"sku", re.I)},
            ]

            for selector in sku_selectors:
                sku_elem = soup.find(attrs=selector)
                if sku_elem:
                    part_number = sku_elem.get_text(strip=True) or sku_elem.get(
                        "content", ""
                    )
                    if part_number:
                        break

            return {
                "name": name,
                "description": description,
                "price": price,
                "image_url": image_url,
                "brand": brand,
                "part_number": part_number,
                "url": product_url,
            }
        except Exception as e:
            print(f"Error extracting product data from {product_url}: {e}")
            return None

    def is_product_page(self, soup: BeautifulSoup) -> bool:
        """Check if a page is an actual product page (not a collection/category page)."""
        if not soup:
            return False

        # Look for product page indicators
        # Product pages typically have:
        # - Add to cart buttons
        # - Price elements
        # - Product form/options
        # - SKU/part number
        # - Quantity selectors
        # - Variant selectors

        product_indicators = [
            soup.find(string=re.compile(r"add\s+to\s+cart|buy\s+now|purchase", re.I)),
            soup.find(
                class_=re.compile(
                    r"product-form|add-to-cart|buy-button|product.*button", re.I
                )
            ),
            soup.find("button", string=re.compile(r"add\s+to|buy|purchase", re.I)),
            soup.find(
                class_=re.compile(r"product.*price|price.*product|current-price", re.I)
            ),
            soup.find(
                class_=re.compile(r"sku|part-number|product-code|product-sku", re.I)
            ),
            soup.find("form", class_=re.compile(r"product", re.I)),
            soup.find(class_=re.compile(r"quantity|qty", re.I)),
            soup.find(class_=re.compile(r"variant|option", re.I)),
            soup.find("select", class_=re.compile(r"variant|option", re.I)),
        ]

        # Count indicators
        indicator_count = sum(1 for indicator in product_indicators if indicator)

        # Also check for collection page indicators (if found, it's NOT a product page)
        collection_indicators = [
            len(
                soup.find_all(
                    class_=re.compile(r"product-grid|product-list|collection", re.I)
                )
            )
            > 0,
            soup.find(class_=re.compile(r"filter|sort|pagination", re.I)),
            len(soup.find_all(class_=re.compile(r"product.*card|product.*item", re.I)))
            > 3,  # Multiple products
        ]

        collection_count = sum(1 for indicator in collection_indicators if indicator)

        # If it has collection indicators and few product indicators, it's a collection
        if collection_count >= 2 and indicator_count < 2:
            return False

        # Need at least 2 product indicators to be confident it's a product page
        return indicator_count >= 2

    def is_collection_page(self, soup: BeautifulSoup) -> bool:
        """Check if a page is a collection/category page with multiple products."""
        if not soup:
            return False

        # Collection pages typically have:
        # - Multiple product cards/items
        # - Grid/list of products
        # - Filter/sort options
        # - Pagination
        collection_indicators = [
            soup.find(class_=re.compile(r"product-grid|product-list|collection", re.I)),
            soup.find(class_=re.compile(r"filter|sort", re.I)),
            len(soup.find_all(class_=re.compile(r"product.*card|product.*item", re.I)))
            > 1,
        ]

        return any(collection_indicators)

    def should_exclude_url(self, href: str) -> bool:
        """Check if a URL should be excluded from scraping."""
        if not href:
            return True

        # NEVER exclude product-page URLs - these are what we want!
        if "/product-page/" in href:
            return False

        # Exclude common non-product pages and patterns
        exclude_patterns = [
            "/cart",
            "/checkout",
            "/account",
            "/search",
            "/about",
            "/contact",
            "/policy",
            "/terms",
            "/privacy",
            "/members-only",
            "/trusted-brands",
            "/las-vegas",
            "/shop-las-vegas",
            "/a90-shop-members-only",
            "/a90shop-trusted-brands",
            "/a90-toyota-supra-shop-las-vegas",
            "/gr-supra-corolla-86-a90-shop",  # About page
            "#",
            "javascript:",
            "mailto:",
            "tel:",
            "/collections/",
            "/pages/",
            "/blogs/",
            "/apps/",
            "/account/",
            "?variant=",  # Product variant URLs, we want the base product
        ]

        href_lower = href.lower()

        # Check for exclude patterns
        if any(exclude in href_lower for exclude in exclude_patterns):
            return True

        # Exclude URLs that are clearly not products (too short, no hyphens, etc.)
        path_parts = [p for p in href.split("/") if p]
        if path_parts:
            last_part = path_parts[-1].lower()
            # Exclude single words or very short slugs (likely not products)
            if len(last_part) < 5 or "-" not in last_part:
                # But allow if it looks like a category we want
                if last_part not in [
                    "wheels",
                    "exhaust",
                    "suspension",
                    "engine",
                    "brakes",
                    "body",
                    "interior",
                ]:
                    return True

        return False

    def scrape_product_listing(
        self, url: str, db: Session, visited: Optional[set] = None
    ) -> tuple[list[str], list[str]]:
        """
        Scrape a product listing page and return tuple of (product_urls, collection_urls).

        Args:
            url: URL to scrape
            db: Database session
            visited: Set of already visited URLs to avoid duplicates

        Returns:
            Tuple of (product_urls, collection_urls)
        """
        if visited is None:
            visited = set()

        if url in visited:
            return [], []

        visited.add(url)
        soup = self.fetch_page(url)
        if not soup:
            return [], []

        # Check if this is a product page (including /product-page/ URLs)
        if "/product-page/" in url or self.is_product_page(soup):
            return [url], []

        product_urls = []
        collection_urls = []

        # Look for product links in common e-commerce patterns
        # Try to find product cards/items first (more reliable)
        product_containers = soup.find_all(
            class_=re.compile(r"product|item|card", re.I)
        )

        # Also look for links with product-related classes/attributes
        product_links = soup.find_all(
            "a",
            href=True,
            class_=re.compile(r"product|item", re.I),
        )

        # Look for "Quick View" links which often link to product pages
        quick_view_links = soup.find_all(
            "a",
            href=True,
            string=re.compile(r"quick\s+view", re.I),
        )

        # Combine all approaches
        all_links = set()
        for container in product_containers:
            link = container.find("a", href=True)
            if link:
                all_links.add(link.get("href", ""))

        for link in product_links:
            all_links.add(link.get("href", ""))

        for link in quick_view_links:
            all_links.add(link.get("href", ""))

        # Also check all links as fallback (for sites without clear product classes)
        # This is important to catch product-page URLs that might not have special classes
        all_page_links = {
            link.get("href", "") for link in soup.find_all("a", href=True)
        }
        all_links.update(all_page_links)

        for href in all_links:
            if self.should_exclude_url(href):
                continue

            # Skip if it's just the homepage or root
            if href in ["/", ""]:
                continue

            # Build full URL
            full_url = urljoin(BASE_URL, href)
            parsed = urlparse(full_url)

            # Make sure it's from the same domain
            if parsed.netloc != urlparse(BASE_URL).netloc:
                continue

            # Check if this is a product-page URL (a90shop.com uses /product-page/ pattern)
            if "/product-page/" in full_url:
                if full_url not in visited:
                    product_urls.append(full_url)
                    print(f"  ✓ Found product page: {full_url}")
                continue

            # Include URLs that look like products or collections
            path_parts = [p for p in parsed.path.split("/") if p]
            if len(path_parts) >= 1 and "-" in path_parts[-1]:
                if full_url not in visited:
                    # We'll check if it's a product or collection when we fetch it
                    # For now, add to collection_urls to be checked
                    collection_urls.append(full_url)

        return product_urls, collection_urls

    def scrape_and_create_part(
        self, product_url: str, category_id: int, user_id: int, db: Session
    ) -> bool:
        """Scrape a single product and create it in the database."""
        soup = self.fetch_page(product_url)
        if not soup:
            return False

        product_data = self.extract_product_data(soup, product_url)
        if not product_data:
            self.skipped_count += 1
            print(f"  ⚠ Skipped: Could not extract product data")
            return False

        # Validate that we have a reasonable product name (not promotional text)
        if not product_data.get("name") or len(product_data["name"]) < 5:
            self.skipped_count += 1
            print(
                f"  ⚠ Skipped: Invalid product name: {product_data.get('name', 'None')}"
            )
            return False

        # Detect category from product name/description if default category was used
        # This helps fix incorrect category assignments
        detected_category_id = self.detect_category_from_product(
            product_data["name"], product_data.get("description", ""), db
        )
        if detected_category_id:
            category_id = detected_category_id

        # Match car
        car_id = self.match_car(
            product_data["name"], product_data.get("description", ""), db
        )

        if self.dry_run:
            print(f"[DRY RUN] Would create part: {product_data['name']}")
            if product_data.get("price"):
                print(f"  Price: ${product_data['price'] / 100:.2f}")
            if product_data.get("brand"):
                print(f"  Brand: {product_data['brand']}")
            if car_id:
                car = db.query(Car).filter(Car.id == car_id).first()
                if car:
                    print(f"  Car: {car.make} {car.model} {car.generation_name}")
            self.created_count += 1
            return True

        # Check if part already exists (by name or URL)
        existing = (
            db.query(GlobalPart)
            .filter(
                (GlobalPart.name == product_data["name"])
                | (GlobalPart.image_url == product_data.get("image_url"))
            )
            .first()
        )
        if existing:
            self.skipped_count += 1
            print(f"  ⚠ Skipped: Part already exists: {product_data['name']}")
            return False

        # Create the part
        part = GlobalPart(
            name=product_data["name"],
            description=product_data.get("description"),
            price=product_data.get("price"),
            image_url=product_data.get("image_url"),
            category_id=category_id,
            user_id=user_id,
            car_id=car_id,
            brand=product_data.get("brand"),
            part_number=product_data.get("part_number"),
            source="scraped",
            is_verified=False,
        )

        db.add(part)
        db.commit()
        db.refresh(part)
        self.created_count += 1
        print(f"✓ Created part: {product_data['name']}")
        return True

    def run(self, db: Session) -> None:
        """Main scraping function."""
        print("=" * 60)
        print("A90Shop.com Scraper - Proof of Concept")
        print("=" * 60)
        print(f"Dry run: {self.dry_run}")
        print(f"Max pages: {self.max_pages}")
        print()

        # Check robots.txt
        if not self.check_robots_txt():
            print("Cannot proceed - robots.txt disallows scraping")
            return

        # Get or create a system user for scraped parts
        system_user = db.query(User).filter(User.username == "admin").first()
        if not system_user:
            print(
                "ERROR: No admin user found. Please run populate_sample_data.py first."
            )
            return

        # Get default category (use 'other' as fallback, or first available category)
        default_category = db.query(Category).filter(Category.name == "other").first()
        if not default_category:
            # If 'other' doesn't exist, use the first available category
            default_category = db.query(Category).first()
            if not default_category:
                print(
                    "ERROR: No categories found. Please run populate_sample_data.py first."
                )
                return
            print(
                f"Note: Using '{default_category.name}' as default category (no 'other' category found)"
            )

        # Start scraping from main shop page or category pages
        # a90shop.com uses descriptive URLs, not /collections/ paths
        start_urls = [
            f"{BASE_URL}/",  # Homepage - will discover product pages from navigation
            f"{BASE_URL}/a90-shop-supra-parts",  # Main collection page
        ]

        all_product_urls = set()
        visited_urls = set()
        collection_queue = list(start_urls)
        max_collections_to_check = self.max_pages * 5  # Limit collection pages to check
        collections_checked = 0

        print("Discovering product pages...\n")

        # Recursively scrape collection pages to find actual product pages
        while collection_queue and collections_checked < max_collections_to_check:
            if len(all_product_urls) >= self.max_pages * 10:
                break

            collection_url = collection_queue.pop(0)
            if collection_url in visited_urls:
                continue

            print(f"Checking: {collection_url}")
            product_urls, new_collection_urls = self.scrape_product_listing(
                collection_url, db, visited_urls
            )

            # Add discovered product URLs
            for product_url in product_urls:
                if product_url not in all_product_urls:
                    all_product_urls.add(product_url)
                    print(f"  ✓ Found product: {product_url}")

            # Add new collection URLs to queue (limit depth)
            for new_collection_url in new_collection_urls[:5]:  # Limit per page
                if (
                    new_collection_url not in visited_urls
                    and new_collection_url not in collection_queue
                ):
                    # Quick check if it looks like a product page by fetching
                    temp_soup = self.fetch_page(new_collection_url)
                    if temp_soup:
                        if self.is_product_page(temp_soup):
                            all_product_urls.add(new_collection_url)
                            print(f"  ✓ Found product: {new_collection_url}")
                        elif self.is_collection_page(temp_soup):
                            collection_queue.append(new_collection_url)
                            print(f"  → Found collection: {new_collection_url}")

            collections_checked += 1

        # Limit to max_pages worth of products
        product_urls_list = list(all_product_urls)[: self.max_pages * 10]

        print(f"\nFound {len(product_urls_list)} products to scrape")
        print(f"Processing up to {self.max_pages * 10} products...\n")

        # Scrape each product
        for i, product_url in enumerate(product_urls_list[: self.max_pages * 10], 1):
            print(
                f"[{i}/{min(len(product_urls_list), self.max_pages * 10)}] {product_url}"
            )
            self.scrape_and_create_part(
                product_url, default_category.id, system_user.id, db
            )
            self.scraped_count += 1

        # Print summary
        print("\n" + "=" * 60)
        print("Scraping Summary")
        print("=" * 60)
        print(f"Products scraped: {self.scraped_count}")
        print(f"Parts created: {self.created_count}")
        print(f"Parts skipped: {self.skipped_count}")
        print(f"Errors: {self.error_count}")
        print("=" * 60)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Scrape parts from a90shop.com")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Maximum number of product pages to scrape (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually create parts, just show what would be created",
    )

    args = parser.parse_args()

    scraper = A90ShopScraper(dry_run=args.dry_run, max_pages=args.max_pages)

    db: Session = SessionLocal()
    try:
        scraper.run(db)
    except Exception as e:
        db.rollback()
        print(f"Error during scraping: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
