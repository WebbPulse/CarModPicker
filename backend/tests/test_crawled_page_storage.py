"""
Tests for the crawler HTML archival pipeline:
- save_crawl_page_html() writing to S3 (moto) and local filesystem fallback
- POST /crawled-pages/html  — extension HTML upload endpoint
- GET  /crawled-pages/      — admin list endpoint
- POST /crawled-pages/{id}/re-parse — admin re-parse endpoint
"""

import hashlib
import os
import tempfile
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crawlers.base import CRAWL_HTML_HASH_BYTES
from tests.conftest import INVALID_UUID_STR, login_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:CRAWL_HTML_HASH_BYTES]


def _auth(client: TestClient, username: str) -> Dict[str, str]:
    token = login_user(client, username)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# save_crawl_page_html — unit tests
# ---------------------------------------------------------------------------


class TestSaveCrawlPageHtml:
    def test_writes_html_to_s3_and_returns_key(self, mock_s3: Dict[str, Any]) -> None:
        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/turbo-kit"
        html = "<html><body>Turbo kit listing</body></html>"

        key = save_crawl_page_html("test_adapter", url, html, "")

        assert key is not None
        assert not key.startswith("/"), "Expected S3 key, got local path"
        assert "by_url" in key
        assert key.endswith(".html")
        assert _url_hash(url) in key

    def test_html_content_readable_from_s3(self, mock_s3: Dict[str, Any]) -> None:
        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/coilovers"
        html = "<html><body>Coilover listing</body></html>"

        key = save_crawl_page_html("test_adapter", url, html, "")
        assert key is not None

        obj = mock_s3["client"].get_object(Bucket=mock_s3["crawl_bucket"], Key=key)
        stored = obj["Body"].read().decode("utf-8")
        assert stored == html

    def test_url_sidecar_written(self, mock_s3: Dict[str, Any]) -> None:
        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/exhaust"
        html = "<html><body>Exhaust</body></html>"

        key = save_crawl_page_html("test_adapter", url, html, "")
        assert key is not None

        url_key = key.replace(".html", ".url")
        obj = mock_s3["client"].get_object(Bucket=mock_s3["crawl_bucket"], Key=url_key)
        assert obj["Body"].read().decode() == url

    def test_same_url_overwrites_same_key(self, mock_s3: Dict[str, Any]) -> None:
        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/intake"

        key1 = save_crawl_page_html("test_adapter", url, "<html>v1</html>", "")
        key2 = save_crawl_page_html("test_adapter", url, "<html>v2</html>", "")

        assert key1 == key2, "Re-crawl of same URL should produce same key"
        obj = mock_s3["client"].get_object(Bucket=mock_s3["crawl_bucket"], Key=key2)
        assert obj["Body"].read().decode() == "<html>v2</html>"

    def test_same_url_same_key_across_different_adapter_names(self, mock_s3: Dict[str, Any]) -> None:
        """HTML archive path is URL-canonical; adapter label must not fork storage."""
        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/shared-key"
        key_a = save_crawl_page_html("a90shop", url, "<html>a</html>", "")
        key_b = save_crawl_page_html("studiorsr", url, "<html>b</html>", "")
        assert key_a == key_b
        obj = mock_s3["client"].get_object(Bucket=mock_s3["crawl_bucket"], Key=key_b)
        assert obj["Body"].read().decode() == "<html>b</html>"

    def test_returns_none_on_s3_failure(self, mock_s3: Dict[str, Any]) -> None:
        """If put_object raises, the function returns None without propagating."""
        from app.crawlers.base import save_crawl_page_html

        mock_s3["client"].put_object = MagicMock(side_effect=Exception("S3 outage"))

        key = save_crawl_page_html("test_adapter", "https://example.com/boom", "<html/>", "")
        assert key is None

    def test_local_filesystem_fallback_when_no_bucket(self, tmp_path: Any) -> None:
        """Without mock_s3, falls back to writing HTML to local filesystem."""
        from unittest.mock import patch

        import app.crawlers.base as base_module
        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/wheels"
        html = "<html><body>Wheels</body></html>"

        # Patch the S3 client factory to simulate no bucket configured, bypassing
        # any CRAWL_BUCKET env var that may be set in the local .env file.
        with patch.object(base_module, "get_crawl_s3_client", return_value=(None, None)):
            key = save_crawl_page_html("test_adapter", url, html, str(tmp_path))

            assert key is not None
            assert key.startswith("/"), "Expected absolute local path"
            assert os.path.exists(key)
            with open(key) as f:
                assert f.read() == html


# ---------------------------------------------------------------------------
# POST /crawled-pages/html — extension HTML upload
# ---------------------------------------------------------------------------


class TestHtmlUploadEndpoint:
    def test_stores_html_to_s3_and_creates_db_record(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        db_session: Session,
    ) -> None:
        from app.api.models.crawled_page import CrawledPage

        headers = _auth(client, test_user.username)
        resp = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": "https://shop.example.com/product/1", "html": "<html>part</html>"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["html_s3_key"] is not None
        assert data["html_local_path"] is None
        assert data["html_size_bytes"] > 0
        assert len(data["html_sha256"]) == 64
        assert data["archive_skipped_duplicate"] is False

        # Verify object is in S3
        s3_key = data["html_s3_key"]
        obj = mock_s3["client"].get_object(Bucket=mock_s3["crawl_bucket"], Key=s3_key)
        assert b"part" in obj["Body"].read()

        # Verify DB record
        page = db_session.query(CrawledPage).filter(CrawledPage.url == "https://shop.example.com/product/1").first()
        assert page is not None
        assert page.source == "chrome_extension"
        assert page.parse_status == "pending"
        assert page.html_s3_key == s3_key
        assert page.html_sha256 == data["html_sha256"]

    def test_second_upload_same_url_is_idempotent(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        db_session: Session,
    ) -> None:
        from app.api.models.crawled_page import CrawledPage

        headers = _auth(client, test_user.username)
        url = "https://shop.example.com/product/idempotent"

        resp1 = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": url, "html": "<html>v1</html>"},
        )
        resp2 = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": url, "html": "<html>v2</html>"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["id"] == resp2.json()["id"], "Should update same row, not create duplicate"

        count = db_session.query(CrawledPage).filter(CrawledPage.url == url).count()
        assert count == 1

    def test_requires_authentication(self, mock_s3: Dict[str, Any], client: TestClient) -> None:
        resp = client.post(
            "/api/crawled-pages/html",
            json={"url": "https://example.com/x", "html": "<html/>"},
        )
        assert resp.status_code == 401

    def test_rejects_empty_url(self, mock_s3: Dict[str, Any], client: TestClient, test_user: Any) -> None:
        headers = _auth(client, test_user.username)
        resp = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": "   ", "html": "<html/>"},
        )
        assert resp.status_code == 400

    def test_rejects_empty_html(self, mock_s3: Dict[str, Any], client: TestClient, test_user: Any) -> None:
        headers = _auth(client, test_user.username)
        resp = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": "https://shop.example.com/product/empty-html", "html": ""},
        )
        assert resp.status_code == 400

    def test_identical_second_upload_skips_s3_put_object(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
    ) -> None:
        from app.crawlers.base import crawl_html_fingerprint

        headers = _auth(client, test_user.username)
        url = "https://shop.example.com/product/dedupe-s3"
        html = "<html>unchanged</html>"
        _, _, sha = crawl_html_fingerprint(html)

        put_calls = 0
        orig_put = mock_s3["client"].put_object

        def counting_put(*args: Any, **kwargs: Any) -> Any:
            nonlocal put_calls
            put_calls += 1
            return orig_put(*args, **kwargs)

        mock_s3["client"].put_object = counting_put  # type: ignore[method-assign]

        r1 = client.post("/api/crawled-pages/html", headers=headers, json={"url": url, "html": html})
        assert r1.status_code == 200
        after_first = put_calls
        assert after_first >= 1

        r2 = client.post("/api/crawled-pages/html", headers=headers, json={"url": url, "html": html})
        assert r2.status_code == 200
        assert put_calls == after_first, "Duplicate identical HTML should not call put_object again"
        assert r2.json()["archive_skipped_duplicate"] is True
        assert r2.json()["html_sha256"] == sha


# ---------------------------------------------------------------------------
# Payload size limits (413)
# ---------------------------------------------------------------------------


class TestCrawlUploadPayloadLimits:
    def test_scrape_413_when_html_exceeds_max_utf8_bytes(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.core import config

        monkeypatch.setattr(config.settings, "CRAWLED_PAGE_MAX_HTML_BYTES", 80)
        monkeypatch.setattr(config.settings, "CRAWLED_PAGE_UPLOAD_CONTENT_LENGTH_SLACK_BYTES", 10_000_000)

        headers = _auth(client, test_user.username)
        html = "x" * 100
        resp = client.post(
            "/api/crawled-pages/scrape",
            headers=headers,
            json={"url": "https://shop.example.com/product/too-big", "html": html},
        )
        assert resp.status_code == 413
        assert "maximum" in resp.json()["message"].lower()

    def test_middleware_413_when_content_length_exceeds_limit(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.core import config

        monkeypatch.setattr(config.settings, "CRAWLED_PAGE_MAX_HTML_BYTES", 40)
        monkeypatch.setattr(config.settings, "CRAWLED_PAGE_UPLOAD_CONTENT_LENGTH_SLACK_BYTES", 0)

        headers = _auth(client, test_user.username)
        html = "y" * 200
        resp = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": "https://shop.example.com/product/cl-too-big", "html": html},
        )
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# GET /crawled-pages/ — admin list
# ---------------------------------------------------------------------------


class TestListCrawledPages:
    def _seed_page(self, db_session: Session, url: str, source: str = "chrome_extension") -> Any:
        from datetime import datetime, timezone

        from app.api.models.crawled_page import CrawledPage

        page = CrawledPage(url=url, source=source, crawled_at=datetime.now(timezone.utc), parse_status="pending")
        db_session.add(page)
        db_session.commit()
        db_session.refresh(page)
        return page

    def test_admin_can_list_pages(self, client: TestClient, test_admin_user: Any, db_session: Session) -> None:
        self._seed_page(db_session, "https://a.com/1")
        self._seed_page(db_session, "https://a.com/2")
        headers = _auth(client, test_admin_user.username)
        resp = client.get("/api/crawled-pages/", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_non_admin_is_forbidden(self, client: TestClient, test_user: Any, db_session: Session) -> None:
        self._seed_page(db_session, "https://b.com/1")
        headers = _auth(client, test_user.username)
        resp = client.get("/api/crawled-pages/", headers=headers)
        assert resp.status_code == 403

    def test_filter_by_source(self, client: TestClient, test_admin_user: Any, db_session: Session) -> None:
        self._seed_page(db_session, "https://c.com/crawler", source="a90shop")
        self._seed_page(db_session, "https://c.com/ext", source="chrome_extension")
        headers = _auth(client, test_admin_user.username)

        resp = client.get("/api/crawled-pages/?source=a90shop", headers=headers)
        assert resp.status_code == 200
        for item in resp.json():
            assert item["source"] == "a90shop"

    def test_filter_by_parse_status(self, client: TestClient, test_admin_user: Any, db_session: Session) -> None:
        from datetime import datetime, timezone

        from app.api.models.crawled_page import CrawledPage

        page = CrawledPage(
            url="https://d.com/parsed", source="a90shop", crawled_at=datetime.now(timezone.utc), parse_status="parsed"
        )
        db_session.add(page)
        db_session.commit()

        headers = _auth(client, test_admin_user.username)
        resp = client.get("/api/crawled-pages/?parse_status=parsed", headers=headers)
        assert resp.status_code == 200
        for item in resp.json():
            assert item["parse_status"] == "parsed"


# ---------------------------------------------------------------------------
# POST /crawled-pages/{id}/re-parse — admin re-parse
# ---------------------------------------------------------------------------


class TestReparseCrawledPage:
    def _seed_page_with_html(
        self, mock_s3: Dict[str, Any], db_session: Session, url: str, html: str, source: str = "a90shop"
    ) -> Any:
        from datetime import datetime, timezone

        from app.api.models.crawled_page import CrawledPage
        from app.crawlers.base import save_crawl_page_html

        s3_key = save_crawl_page_html(source, url, html, "")
        page = CrawledPage(
            url=url, source=source, html_s3_key=s3_key, crawled_at=datetime.now(timezone.utc), parse_status="pending"
        )
        db_session.add(page)
        db_session.commit()
        db_session.refresh(page)
        return page

    def test_reparse_chrome_extension_unknown_host_uses_generic(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
        db_session: Session,
    ) -> None:
        # Unknown hosts now fall through to the generic adapter instead of returning 422.
        # The generic adapter returns None for a bare <html/> stub, so re-parse status is "failed".
        from tests.conftest import get_default_category_id

        page = self._seed_page_with_html(
            mock_s3, db_session, "https://unknown-retailer.example/p/1", "<html/>", source="chrome_extension"
        )
        cat_id = get_default_category_id(db_session)

        mock_adapter = MagicMock()
        mock_adapter.parse_product_page.return_value = None

        with (
            patch("app.crawlers.archive_rescrape.get_adapter", return_value=mock_adapter),
            patch("app.crawlers.runner.resolve_crawler_user", return_value=test_admin_user),
            patch("app.crawlers.runner.resolve_default_category_id", return_value=cat_id),
        ):
            headers = _auth(client, test_admin_user.username)
            resp = client.post(f"/api/crawled-pages/{page.id}/re-parse", headers=headers)

        # 200 parse_failed (adapter ran but returned no payload) rather than 422 no-adapter
        assert resp.status_code == 200
        body = resp.json()
        assert body["parse_status"] == "failed"

    def test_reparse_missing_page_returns_404(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
    ) -> None:
        headers = _auth(client, test_admin_user.username)
        resp = client.post(f"/api/crawled-pages/{INVALID_UUID_STR}/re-parse", headers=headers)
        assert resp.status_code == 404

    def test_reparse_no_html_returns_404(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
        db_session: Session,
    ) -> None:
        from datetime import datetime, timezone

        from app.api.models.crawled_page import CrawledPage

        page = CrawledPage(
            url="https://f.com/no-html", source="a90shop", crawled_at=datetime.now(timezone.utc), parse_status="pending"
        )
        db_session.add(page)
        db_session.commit()
        db_session.refresh(page)

        headers = _auth(client, test_admin_user.username)
        resp = client.post(f"/api/crawled-pages/{page.id}/re-parse", headers=headers)
        assert resp.status_code == 404

    def test_reparse_non_admin_is_forbidden(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        db_session: Session,
    ) -> None:
        page = self._seed_page_with_html(mock_s3, db_session, "https://g.com/1", "<html/>")
        headers = _auth(client, test_user.username)
        resp = client.post(f"/api/crawled-pages/{page.id}/re-parse", headers=headers)
        assert resp.status_code == 403

    def test_reparse_updates_parse_status_on_adapter_none(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
        db_session: Session,
    ) -> None:
        """When the adapter returns None (not a product page), status → 'failed'."""
        from tests.conftest import get_default_category_id

        page = self._seed_page_with_html(mock_s3, db_session, "https://h.com/not-product", "<html>blog post</html>")

        mock_adapter = MagicMock()
        mock_adapter.parse_product_page.return_value = None

        cat_id = get_default_category_id(db_session)

        with (
            patch("app.crawlers.archive_rescrape.get_adapter", return_value=mock_adapter),
            patch(
                "app.crawlers.runner.resolve_crawler_user",
                return_value=test_admin_user,
            ),
            patch(
                "app.crawlers.runner.resolve_default_category_id",
                return_value=cat_id,
            ),
        ):
            headers = _auth(client, test_admin_user.username)
            resp = client.post(f"/api/crawled-pages/{page.id}/re-parse", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["parse_status"] == "failed"

        db_session.refresh(page)
        assert page.parse_status == "failed"
        assert page.last_parsed_at is not None


# ---------------------------------------------------------------------------
# canonicalize_url — unit tests
# ---------------------------------------------------------------------------


class TestCanonicalizeUrl:
    def test_strips_utm_params(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "https://shop.example.com/product/turbo?utm_source=email&utm_campaign=spring"
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "utm_campaign" not in result
        assert "product/turbo" in result

    def test_strips_fbclid_and_gclid(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "https://shop.example.com/p/1?fbclid=abc&gclid=xyz&color=red"
        result = canonicalize_url(url)
        assert "fbclid" not in result
        assert "gclid" not in result
        assert "color=red" in result

    def test_removes_fragment(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "https://shop.example.com/product/intake#specs"
        assert "#" not in canonicalize_url(url)

    def test_lowercases_scheme_and_host(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "HTTPS://Shop.Example.Com/product/intake"
        result = canonicalize_url(url)
        assert result.startswith("https://shop.example.com/")

    def test_strips_root_trailing_slash(self) -> None:
        from app.crawlers.base import canonicalize_url

        assert canonicalize_url("https://shop.example.com/") == "https://shop.example.com"

    def test_preserves_non_root_trailing_slash(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "https://shop.example.com/category/intake/"
        assert canonicalize_url(url) == url

    def test_preserves_non_tracking_query_params(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "https://shop.example.com/search?q=turbo&page=2"
        result = canonicalize_url(url)
        assert "q=turbo" in result
        assert "page=2" in result

    def test_idempotent(self) -> None:
        from app.crawlers.base import canonicalize_url

        url = "https://shop.example.com/product/exhaust?color=black"
        assert canonicalize_url(canonicalize_url(url)) == canonicalize_url(url)

    def test_same_url_same_s3_key_after_canonicalization(self, mock_s3: Dict[str, Any]) -> None:
        """Tracking params should not fork the S3 key."""
        from app.crawlers.base import save_crawl_page_html

        base = "https://shop.example.com/product/coilover"
        url_with_tracking = f"{base}?utm_source=ig&fbclid=zzz"
        url_clean = base

        key_a = save_crawl_page_html("adapter", url_with_tracking, "<html>a</html>", "")
        key_b = save_crawl_page_html("adapter", url_clean, "<html>b</html>", "")
        assert key_a == key_b, "Same product URL with/without tracking params must produce the same S3 key"


# ---------------------------------------------------------------------------
# crawled_at refresh and pg_insert upsert — extension endpoints
# ---------------------------------------------------------------------------


class TestExtensionEndpointUpsert:
    def test_html_upload_refreshes_crawled_at_on_re_upload(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        db_session: Session,
    ) -> None:
        """Second upload of the same URL should update crawled_at, not leave stale timestamp."""
        from datetime import timedelta

        from app.api.models.crawled_page import CrawledPage

        headers = _auth(client, test_user.username)
        url = "https://shop.example.com/product/crawled-at-refresh"

        resp1 = client.post("/api/crawled-pages/html", headers=headers, json={"url": url, "html": "<html>v1</html>"})
        assert resp1.status_code == 200

        page_before = db_session.query(CrawledPage).filter(CrawledPage.url == url).one()
        ts_before = page_before.crawled_at

        resp2 = client.post("/api/crawled-pages/html", headers=headers, json={"url": url, "html": "<html>v2</html>"})
        assert resp2.status_code == 200

        db_session.refresh(page_before)
        ts_after = page_before.crawled_at

        assert ts_after >= ts_before, "crawled_at must be refreshed on re-upload"

    def test_scrape_returns_archived_true_when_s3_succeeds(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
    ) -> None:
        headers = _auth(client, test_user.username)
        resp = client.post(
            "/api/crawled-pages/scrape",
            headers=headers,
            json={"url": "https://shop.example.com/product/exhaust", "html": "<html>part</html>"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["archived"] is True
        assert body["html_size_bytes"] > 0
        assert len(body["html_sha256"]) == 64
        assert body["archive_skipped_duplicate"] is False

    def test_scrape_returns_archived_false_when_s3_fails(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        db_session: Session,
    ) -> None:
        """When the S3 write fails, archived=False and no phantom DB row is created."""
        from unittest.mock import patch

        from app.api.models.crawled_page import CrawledPage

        headers = _auth(client, test_user.username)
        url = "https://shop.example.com/product/s3-fail"

        with patch("app.api.endpoints.crawled_pages.save_crawl_page_html", return_value=None):
            resp = client.post(
                "/api/crawled-pages/scrape",
                headers=headers,
                json={"url": url, "html": "<html>part</html>"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["archived"] is False
        assert body["html_size_bytes"] > 0
        assert len(body["html_sha256"]) == 64

        count = db_session.query(CrawledPage).filter(CrawledPage.url == url).count()
        assert count == 0, "No phantom row should be created when S3 write fails"

    def test_html_upload_returns_503_when_s3_fails_and_no_existing_row(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
    ) -> None:
        """Legacy /html endpoint: 503 when storage fails for a brand-new URL."""
        from unittest.mock import patch

        headers = _auth(client, test_user.username)
        url = "https://shop.example.com/product/html-s3-fail"

        with patch("app.api.endpoints.crawled_pages.save_crawl_page_html", return_value=None):
            resp = client.post(
                "/api/crawled-pages/html",
                headers=headers,
                json={"url": url, "html": "<html>part</html>"},
            )

        assert resp.status_code == 503

    def test_scrape_canonicalizes_url_before_db_lookup(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_user: Any,
        db_session: Session,
    ) -> None:
        """Tracking params in the submitted URL must not fork a second DB row."""
        from app.api.models.crawled_page import CrawledPage

        headers = _auth(client, test_user.username)
        base_url = "https://shop.example.com/product/canon-test"

        resp1 = client.post(
            "/api/crawled-pages/scrape",
            headers=headers,
            json={"url": f"{base_url}?utm_source=ig", "html": "<html>v1</html>"},
        )
        resp2 = client.post(
            "/api/crawled-pages/scrape",
            headers=headers,
            json={"url": f"{base_url}?utm_source=email", "html": "<html>v2</html>"},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200

        count = db_session.query(CrawledPage).filter(CrawledPage.url == base_url).count()
        assert count == 1, "Canonicalized URLs must map to a single DB row"
