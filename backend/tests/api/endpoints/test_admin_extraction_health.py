"""Tests for the admin extraction-health endpoint (M002/S04 T02)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.part import Part as DBPart
from app.core.config import settings
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.adapters.base import UNIVERSAL_FIELD_NAMES
from app.crawlers.compliance_audit import classify_tier
from tests.api.endpoints.test_admin import create_and_login_admin_user, create_and_login_user

# Endpoint path resolved against the API prefix; the registry registers it under
# ``/admin/extraction-health`` and the route is ``/`` so the trailing slash is
# part of the request URL.
EXTRACTION_HEALTH_PATH = f"{settings.API_STR}/admin/extraction-health/"


def _pick_adapter_slug(tier: str) -> str:
    """Return any registered adapter slug whose FETCHER_TIER matches ``tier``.

    Tests should not hard-code adapter names — the canonical 108-entry
    registry is the source of truth, and a future adapter rename should not
    break this suite.
    """
    for slug, cls in ADAPTER_REGISTRY.items():
        if classify_tier(cls) == tier:
            return slug
    raise AssertionError(f"No registered adapter found with tier={tier!r}")


class TestExtractionHealthAuth:
    def test_extraction_health_unauthorized(self, client: TestClient) -> None:
        response = client.get(EXTRACTION_HEALTH_PATH)
        assert response.status_code == 401

    def test_extraction_health_forbidden_non_admin(
        self, client: TestClient, db_session: Session
    ) -> None:
        token = create_and_login_user(client, db_session, "extraction_health_non_admin")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 403


class TestExtractionHealthCompliance:
    def test_extraction_health_returns_compliance_block(
        self, client: TestClient, db_session: Session
    ) -> None:
        token = create_and_login_admin_user(client, db_session, "extraction_health_compliance")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()

        compliance = data["compliance"]
        # Per MEM037: 108 canonical adapters, 100% compliant after S03 retrofit.
        assert compliance["compliant"] == compliance["total"]
        assert compliance["compliant"] == len(ADAPTER_REGISTRY)

        per_tier = compliance["per_tier"]
        for tier in ("http", "tls", "browser"):
            assert tier in per_tier
            value = per_tier[tier]
            assert "/" in value
            n_compliant_str, n_total_str = value.split("/", 1)
            n_compliant = int(n_compliant_str)
            n_total = int(n_total_str)
            assert n_compliant == n_total


class TestExtractionHealthCoverage:
    def test_extraction_health_coverage_counts_specifications_field(
        self,
        client: TestClient,
        db_session: Session,
        test_category,
        test_user,
    ) -> None:
        # Seed a Part whose specifications contain weight_grams + a CrawledPage
        # row that links it to a registered http-tier adapter.
        adapter_slug = _pick_adapter_slug("http")
        part = DBPart(
            name="extraction_health_coverage_part",
            description="seed for coverage test",
            category_id=test_category.id,
            user_id=test_user.id,
            specifications={"weight_grams": 1.0, "weight_grams_confidence": "high"},
        )
        db_session.add(part)
        db_session.commit()
        db_session.refresh(part)

        crawled = DBCrawledPage(
            url="https://extraction-health-coverage.example.com/p1",
            source=adapter_slug,
            parse_status="parsed",
            last_parsed_at=datetime.now(timezone.utc),
            part_id=part.id,
        )
        db_session.add(crawled)
        db_session.commit()

        token = create_and_login_admin_user(client, db_session, "extraction_health_coverage")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()

        http_block = data["coverage"]["per_tier"]["http"]
        assert http_block["parts_with_specs"] >= 1
        assert http_block["parts_total"] >= 1

        per_field = http_block["per_field"]
        # Every universal field key is present in the coverage payload.
        for field in UNIVERSAL_FIELD_NAMES:
            assert field in per_field

        # Our seed contributes at least 1/parts_total to weight_grams presence.
        assert http_block["per_field"]["weight_grams"] >= 1 / http_block["parts_total"]


class TestExtractionHealthFailureRate:
    def test_extraction_health_failure_rate_window(
        self, client: TestClient, db_session: Session
    ) -> None:
        adapter_slug = _pick_adapter_slug("http")
        now = datetime.now(timezone.utc)
        # One failed + one parsed crawled_page inside the 7-day window.
        db_session.add_all(
            [
                DBCrawledPage(
                    url=f"https://failure-window-failed.example.com/{adapter_slug}",
                    source=adapter_slug,
                    parse_status="failed",
                    last_parsed_at=now,
                ),
                DBCrawledPage(
                    url=f"https://failure-window-parsed.example.com/{adapter_slug}",
                    source=adapter_slug,
                    parse_status="parsed",
                    last_parsed_at=now,
                ),
            ]
        )
        db_session.commit()

        token = create_and_login_admin_user(client, db_session, "extraction_health_fail_rate")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()

        rows = [r for r in data["failure_rate_7d"] if r["adapter"] == adapter_slug]
        assert len(rows) == 1, f"expected exactly one failure_rate_7d row for {adapter_slug}, got {rows}"
        row = rows[0]
        assert row["failed"] == 1
        assert row["parsed"] == 1
        assert abs(row["rate"] - 0.5) < 1e-9
        # Tier annotation must come from ADAPTER_REGISTRY.
        assert row["tier"] == classify_tier(ADAPTER_REGISTRY[adapter_slug])

    def test_extraction_health_excludes_old_failures(
        self, client: TestClient, db_session: Session
    ) -> None:
        adapter_slug = _pick_adapter_slug("http")
        old = datetime.now(timezone.utc) - timedelta(days=30)
        db_session.add(
            DBCrawledPage(
                url=f"https://old-failure.example.com/{adapter_slug}",
                source=adapter_slug,
                parse_status="failed",
                last_parsed_at=old,
            )
        )
        db_session.commit()

        token = create_and_login_admin_user(client, db_session, "extraction_health_old_failures")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()

        rows = [r for r in data["failure_rate_7d"] if r["adapter"] == adapter_slug]
        # Either the row is absent entirely (no other rows seeded) or it
        # exists with failed=0 from unrelated test seeds. The 30-day-old
        # failure must NOT appear in the count.
        if rows:
            assert rows[0]["failed"] == 0

    def test_extraction_health_skips_unknown_sources(
        self, client: TestClient, db_session: Session
    ) -> None:
        unknown_source = "not_a_real_adapter"
        # Sanity-check the precondition.
        assert unknown_source not in ADAPTER_REGISTRY

        db_session.add(
            DBCrawledPage(
                url=f"https://unknown-source.example.com/{unknown_source}",
                source=unknown_source,
                parse_status="failed",
                last_parsed_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()

        token = create_and_login_admin_user(client, db_session, "extraction_health_unknown_src")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()

        adapters_in_response = {r["adapter"] for r in data["failure_rate_7d"]}
        assert unknown_source not in adapters_in_response


class TestExtractionHealthWindow:
    def test_extraction_health_returns_window_metadata(
        self, client: TestClient, db_session: Session
    ) -> None:
        token = create_and_login_admin_user(client, db_session, "extraction_health_window_meta")
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get(EXTRACTION_HEALTH_PATH, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["window"]["days"] == 7
        since = data["window"]["since"]
        # ISO-8601 round trip — empirically validates the format.
        parsed = datetime.fromisoformat(since)
        assert parsed.tzinfo is not None
