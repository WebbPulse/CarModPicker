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
from tests.conftest import login_user


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
        assert "test_adapter" in key
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

    def test_returns_none_on_s3_failure(self, mock_s3: Dict[str, Any]) -> None:
        """If put_object raises, the function returns None without propagating."""
        from app.crawlers.base import save_crawl_page_html

        mock_s3["client"].put_object = MagicMock(side_effect=Exception("S3 outage"))

        key = save_crawl_page_html("test_adapter", "https://example.com/boom", "<html/>", "")
        assert key is None

    def test_local_filesystem_fallback_when_no_bucket(self, tmp_path: Any) -> None:
        """Without mock_s3, falls back to writing HTML to local filesystem."""
        import app.crawlers.base as base_module

        # Ensure crawl client globals are None (no S3 configured)
        original_client = base_module._crawl_s3_client
        original_bucket = base_module._crawl_bucket_name
        base_module._crawl_s3_client = None
        base_module._crawl_bucket_name = None

        from app.crawlers.base import save_crawl_page_html

        url = "https://example.com/product/wheels"
        html = "<html><body>Wheels</body></html>"

        try:
            key = save_crawl_page_html("test_adapter", url, html, str(tmp_path))

            assert key is not None
            assert key.startswith("/"), "Expected absolute local path"
            assert os.path.exists(key)
            assert open(key).read() == html
        finally:
            base_module._crawl_s3_client = original_client
            base_module._crawl_bucket_name = original_bucket


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

    def test_rejects_empty_url(
        self, mock_s3: Dict[str, Any], client: TestClient, test_user: Any
    ) -> None:
        headers = _auth(client, test_user.username)
        resp = client.post(
            "/api/crawled-pages/html",
            headers=headers,
            json={"url": "   ", "html": "<html/>"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /crawled-pages/ — admin list
# ---------------------------------------------------------------------------


class TestListCrawledPages:
    def _seed_page(self, db_session: Session, url: str, source: str = "chrome_extension") -> Any:
        from app.api.models.crawled_page import CrawledPage
        from datetime import datetime, timezone

        page = CrawledPage(url=url, source=source, crawled_at=datetime.now(timezone.utc), parse_status="pending")
        db_session.add(page)
        db_session.commit()
        db_session.refresh(page)
        return page

    def test_admin_can_list_pages(
        self, client: TestClient, test_admin_user: Any, db_session: Session
    ) -> None:
        self._seed_page(db_session, "https://a.com/1")
        self._seed_page(db_session, "https://a.com/2")
        headers = _auth(client, test_admin_user.username)
        resp = client.get("/api/crawled-pages/", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_non_admin_is_forbidden(
        self, client: TestClient, test_user: Any, db_session: Session
    ) -> None:
        self._seed_page(db_session, "https://b.com/1")
        headers = _auth(client, test_user.username)
        resp = client.get("/api/crawled-pages/", headers=headers)
        assert resp.status_code == 403

    def test_filter_by_source(
        self, client: TestClient, test_admin_user: Any, db_session: Session
    ) -> None:
        self._seed_page(db_session, "https://c.com/crawler", source="a90shop")
        self._seed_page(db_session, "https://c.com/ext", source="chrome_extension")
        headers = _auth(client, test_admin_user.username)

        resp = client.get("/api/crawled-pages/?source=a90shop", headers=headers)
        assert resp.status_code == 200
        for item in resp.json():
            assert item["source"] == "a90shop"

    def test_filter_by_parse_status(
        self, client: TestClient, test_admin_user: Any, db_session: Session
    ) -> None:
        from app.api.models.crawled_page import CrawledPage
        from datetime import datetime, timezone

        page = CrawledPage(url="https://d.com/parsed", source="a90shop",
                           crawled_at=datetime.now(timezone.utc), parse_status="parsed")
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
        from app.crawlers.base import save_crawl_page_html
        from app.api.models.crawled_page import CrawledPage
        from datetime import datetime, timezone

        s3_key = save_crawl_page_html(source, url, html, "")
        page = CrawledPage(url=url, source=source, html_s3_key=s3_key,
                           crawled_at=datetime.now(timezone.utc), parse_status="pending")
        db_session.add(page)
        db_session.commit()
        db_session.refresh(page)
        return page

    def test_reparse_chrome_extension_returns_422(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
        db_session: Session,
    ) -> None:
        page = self._seed_page_with_html(
            mock_s3, db_session, "https://e.com/ext", "<html/>", source="chrome_extension"
        )
        headers = _auth(client, test_admin_user.username)
        resp = client.post(f"/api/crawled-pages/{page.id}/re-parse", headers=headers)
        assert resp.status_code == 422

    def test_reparse_missing_page_returns_404(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
    ) -> None:
        headers = _auth(client, test_admin_user.username)
        resp = client.post("/api/crawled-pages/999999/re-parse", headers=headers)
        assert resp.status_code == 404

    def test_reparse_no_html_returns_404(
        self,
        mock_s3: Dict[str, Any],
        client: TestClient,
        test_admin_user: Any,
        db_session: Session,
    ) -> None:
        from app.api.models.crawled_page import CrawledPage
        from datetime import datetime, timezone

        page = CrawledPage(url="https://f.com/no-html", source="a90shop",
                           crawled_at=datetime.now(timezone.utc), parse_status="pending")
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
        from app.api.models.crawled_page import CrawledPage

        page = self._seed_page_with_html(mock_s3, db_session, "https://h.com/not-product", "<html>blog post</html>")

        mock_adapter = MagicMock()
        mock_adapter.parse_product_page.return_value = None

        os.environ["CRAWLER_USER_ID"] = "1"  # won't be reached but avoid KeyError

        with patch("app.crawlers.adapters.ADAPTER_REGISTRY", {"a90shop": mock_adapter}), \
             patch("app.crawlers.adapters.get_adapter", return_value=mock_adapter):
            headers = _auth(client, test_admin_user.username)
            resp = client.post(f"/api/crawled-pages/{page.id}/re-parse", headers=headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["parse_status"] == "failed"

        db_session.refresh(page)
        assert page.parse_status == "failed"
        assert page.last_parsed_at is not None
