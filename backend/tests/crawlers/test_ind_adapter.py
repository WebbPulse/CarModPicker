"""Tests for ind-distribution.com adapter: JSON-LD passthrough for third-party
brands, car-make rejection in the title heuristic fallback."""

from app.crawlers.adapters.tier0_http.ind import INDAdapter, _normalize_part_manufacturer


class TestNormalizePartManufacturer:
    """IND is multi-brand: JSON-LD brand is the real manufacturer, so pass it
    through unchanged. Only reject car-make values that sneak in via the
    title-first-token fallback."""

    def test_third_party_brands_pass_through(self) -> None:
        assert _normalize_part_manufacturer("LCK") == "LCK"
        assert _normalize_part_manufacturer("Dinan") == "Dinan"
        assert _normalize_part_manufacturer("Akrapovic") == "Akrapovic"
        assert _normalize_part_manufacturer("KW Suspensions") == "KW Suspensions"

    def test_car_makes_are_dropped(self) -> None:
        # Title heuristic sometimes returns the lead token when the title opens
        # with the target vehicle. For makes without an OEM-promotion mapping,
        # returning None is the honest answer.
        assert _normalize_part_manufacturer("Porsche") is None
        assert _normalize_part_manufacturer("Toyota") is None

    def test_bmw_is_promoted_to_genuine_bmw(self) -> None:
        # IND publishes BMW M Performance / Motorsport / OEM parts under
        # JSON-LD ``brand: BMW``; those are genuinely BMW-manufactured, so
        # promote to the canonical "Genuine BMW" mfr row that other BMW
        # adapters (Bimmerworld, Turner) already use.
        assert _normalize_part_manufacturer("BMW") == "Genuine BMW"
        assert _normalize_part_manufacturer("bmw") == "Genuine BMW"
        assert _normalize_part_manufacturer("  BMW  ") == "Genuine BMW"

    def test_empty_is_passed_through(self) -> None:
        assert _normalize_part_manufacturer("") == ""
        assert _normalize_part_manufacturer(None) is None

    def test_whitespace_is_trimmed(self) -> None:
        assert _normalize_part_manufacturer("  LCK  ") == "LCK"


class TestParseProductPage:
    """End-to-end parse of a Shopify + Booster Apps SEO style JSON-LD product page."""

    def _ind_html(
        self,
        *,
        name: str = "LCK BMW M Carbon Bucket Seat Bolster Protector Set",
        brand: str = "LCK",
        sku: str = "LCK-G8X-BP-BLK",
        price: str = "295.00",
        # JSON-LD offer URL — defaults to the real product URL so the extractor
        # keeps the block. Tests that intentionally want a mismatched URL can
        # override this.
        offer_url: str = "https://ind-distribution.com/products/lck-bmw-m-carbon-bucket-seat-bolster-protector-set",
    ) -> str:
        # Mirrors IND's Booster Apps SEO JSON-LD block: a Product with brand,
        # sku, mpn, description, and an offers array.
        return f"""
        <html><head>
          <meta property="og:title" content="{name}">
          <script type="application/ld+json">
          {{"@context":"https://schema.org","@type":"Product",
            "name":"{name}",
            "brand":{{"@type":"Brand","name":"{brand}"}},
            "sku":"{sku}","mpn":"{sku}",
            "description":"Extend the life of your premium interior with the LCK BMW M Carbon Bucket Seat Bolster Protector Set designed for BMW M carbon bucket seats.",
            "offers":[{{"@type":"Offer","price":"{price}","priceCurrency":"USD",
              "sku":"{sku}","url":"{offer_url}"}}],
            "image":"https://ind-distribution.com/cdn/shop/files/sample_1024x.jpg?v=1"}}
          </script>
        </head><body><media-gallery></media-gallery></body></html>
        """

    def test_json_ld_happy_path(self) -> None:
        result = INDAdapter().parse_product_page(
            self._ind_html(),
            "https://ind-distribution.com/products/lck-bmw-m-carbon-bucket-seat-bolster-protector-set?variant=41468398600388",
        )
        assert result is not None
        assert result.name == "LCK BMW M Carbon Bucket Seat Bolster Protector Set"
        assert result.part_manufacturer == "LCK"
        assert result.part_number == "LCK-G8X-BP-BLK"
        assert result.price_cents == 29500

    def test_brand_passthrough_preserves_third_party_manufacturer(self) -> None:
        # Regression: we must not rewrite brand to "IND" or "IND Distribution".
        page_url = "https://ind-distribution.com/products/akrapovic-evolution-exhaust-bmw-m3"
        result = INDAdapter().parse_product_page(
            self._ind_html(
                name="Akrapovic Evolution Exhaust BMW M3",
                brand="Akrapovic",
                sku="S-BM/T/1H",
                offer_url=page_url,
            ),
            page_url,
        )
        assert result is not None
        assert result.part_manufacturer == "Akrapovic"
