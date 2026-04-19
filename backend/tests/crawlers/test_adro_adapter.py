"""Tests for adro.com adapter: manufacturer normalization + bundle/zero-price rejection."""

from app.crawlers.adapters.adro import AdroAdapter, _normalize_part_manufacturer


class TestNormalizePartManufacturer:
    """ADRO's Shopify vendor field is inconsistent (ADRO vs ADRO USA vs car make);
    _normalize_part_manufacturer collapses variants without losing real third-party brands."""

    def test_empty_brand_defaults_to_adro(self) -> None:
        assert _normalize_part_manufacturer("", "BMW G87 M2 FRONT LIP") == "ADRO"
        assert _normalize_part_manufacturer(None, "BMW G87 M2 FRONT LIP") == "ADRO"

    def test_adro_variants_all_collapse_to_adro(self) -> None:
        for variant in ("ADRO", "ADRO USA", "ADRO US", "adro", "ADRO-USA"):
            assert _normalize_part_manufacturer(variant, "ADRO HOODIE") == "ADRO", variant

    def test_not_for_everybody_no_longer_splits_out(self) -> None:
        # Regression for the NFE whitelist: all NFE decals are ADRO-branded collabs.
        assert _normalize_part_manufacturer("ADRO USA", "NOT FOR EVERYBODY DOOR DECAL") == "ADRO"
        # Even if the vendor field itself said "Not For Everybody", it still maps to ADRO
        # because NFE is not a separate third-party manufacturer.
        assert _normalize_part_manufacturer("", "NOT FOR EVERYBODY DECAL") == "ADRO"

    def test_car_make_as_brand_maps_to_adro(self) -> None:
        # ADRO's JSON-LD sometimes lists the target vehicle (e.g. "BMW") as the brand.
        assert _normalize_part_manufacturer("BMW", "BMW G87 M2 FRONT LIP") == "ADRO"
        assert _normalize_part_manufacturer("Toyota", "GR SUPRA REAR DIFFUSER") == "ADRO"

    def test_reject_tokens_map_to_adro(self) -> None:
        assert _normalize_part_manufacturer("NOT", "NOT FOR EVERYBODY DECAL") == "ADRO"
        assert _normalize_part_manufacturer("The", "The Hoodie") == "ADRO"

    def test_third_party_brands_pass_through(self) -> None:
        # CSF radiators / JQ Werks steering wheels are legitimately third-party.
        assert _normalize_part_manufacturer("CSF", "CSF BMW F8X OIL COOLER") == "CSF"
        assert _normalize_part_manufacturer("GoldenWrench", "TOYOTA GR SUPRA COOLANT CAP") == "GoldenWrench"
        assert _normalize_part_manufacturer("JQ Werks", "JQ WERKS MADTRACE® …") == "JQ Werks"


class TestZeroPriceBundleRejection:
    """JSON-LD price=0.00 indicates a Shopify picker/bundle landing page, not a real product."""

    def _shopify_html(self, *, price: str, title: str = "GR86 WIDEBODY V2") -> str:
        # Minimal Shopify-looking HTML with a JSON-LD Product block.
        return f"""
        <html><head>
          <meta property="og:title" content="{title}">
          <script type="application/ld+json">
          {{"@context":"https://schema.org","@type":"Product",
            "name":"{title}",
            "description":"ADRO widebody kit. Picker page with multiple sub-products.",
            "brand":{{"@type":"Brand","name":"ADRO USA"}},
            "offers":{{"@type":"Offer","price":"{price}","priceCurrency":"USD"}}
          }}
          </script>
        </head><body><media-gallery></media-gallery></body></html>
        """

    def test_zero_price_is_rejected(self) -> None:
        html = self._shopify_html(price="0.00")
        result = AdroAdapter().parse_product_page(html, "https://adro.com/products/toyota-gr86-widebody-v2")
        assert result is None

    def test_nonzero_price_is_accepted(self) -> None:
        html = self._shopify_html(price="129.00", title="BMW F8X CARBON AIR DUCTS")
        result = AdroAdapter().parse_product_page(
            html, "https://adro.com/products/bmw-f8x-m3-m4-carbon-fiber-air-ducts"
        )
        assert result is not None
        assert result.name == "BMW F8X CARBON AIR DUCTS"
        assert result.price_cents == 12900
        assert result.part_manufacturer == "ADRO"
