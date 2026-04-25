"""
Integration tests for the SpecRegistry validation hook inside ``ingest_payload``.

Three scenarios cover the spec-validation contract end-to-end:

  1. Valid spec block → ``Part.specifications`` equals the validated dict
     (model_dump(exclude_none=True)).
  2. Malformed spec block → ``Part.specifications`` is None AND the part still
     ingests (fail-soft, never block ingest on schema drift).
  3. Malformed spec block → ``emit_extraction_failure`` is called once with
     ``adapter_name=...`` so CloudWatch ExtractionFailureRate stays accurate.

Plus a structured WARN log assertion (caplog) that locks in the
failure-visibility contract for downstream slices (S04 admin endpoint).

Why a custom ``suspension``-keyed registry binding for these tests:
the production ingest path resolves a registry slug from
``infer_category(name, description)``, which returns ``"suspension"`` (the
DB-backed category name) for coilover-keyword text — not the registry-native
``"coilover"`` slug. M002/S01/T03 wires inferred-name → ``default_registry``;
S02 narrows that to a category-aware extractor. Until then, registering
``CoiloverSpec`` under ``"suspension"`` for the duration of these tests is
the supported path that exercises the real validation branch (rather than
mocking ``default_registry.resolve`` and skipping the actual ingest pipeline).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Generator
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.api.models.category import Category
from app.api.models.part_manufacturer import PartManufacturer
from app.api.models.user import User
from app.crawlers import base as crawler_base
from app.crawlers.specs import CoiloverSpec, default_registry


@pytest.fixture
def suspension_category(db_session: Session) -> Category:
    """The seeded ``suspension`` category — match it on slug only.

    Uses a unique-per-worker slug to avoid colliding across xdist workers when
    the engine is shared at session scope. The exact slug doesn't matter; what
    matters is that ``infer_category`` returns this slug for coilover-keyword
    text and that we register ``CoiloverSpec`` under the same slug.
    """
    name = "suspension"
    existing = db_session.query(Category).filter(Category.name == name).first()
    if existing:
        return existing
    cat = Category(
        name=name,
        display_name="Suspension",
        description="Coilovers, springs, struts.",
        is_active=True,
        sort_order=2,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def default_category_id(db_session: Session) -> UUID:
    """A non-matching default category id used as the ingest fallback."""
    name = f"other_default_{os.getpid()}_{id(db_session)}"
    cat = Category(
        name=name,
        display_name="Other Default",
        description="Fallback for tests.",
        is_active=True,
        sort_order=999,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat.id


@pytest.fixture
def coilover_under_suspension(
    suspension_category: Category,
) -> Generator[None, None, None]:
    """
    Bind ``CoiloverSpec`` to slug ``"suspension"`` in the global ``default_registry``
    for the duration of one test, then restore the previous binding (if any).

    Required because ``ingest_payload`` resolves the registry by
    ``infer_category(...)`` output (currently ``"suspension"`` for coilover text),
    not by the registry-native ``"coilover"`` slug. The default_registry is a
    process-global mutable object — monkeypatch alone can't roll back a dict
    mutation, so we manage save/restore explicitly.
    """
    sentinel = object()
    previous: Any = default_registry._specs.get("suspension", sentinel)
    default_registry.register("suspension", CoiloverSpec)
    try:
        yield
    finally:
        if previous is sentinel:
            default_registry._specs.pop("suspension", None)
        else:
            default_registry._specs["suspension"] = previous  # type: ignore[assignment]


def _ingest_kwargs(
    *, current_user: User, default_category_id: UUID
) -> dict[str, Any]:
    return {
        "current_user": current_user,
        "default_category_id": default_category_id,
        "logger": logging.getLogger("test_ingest_spec_validation"),
    }


class TestIngestAcceptsValidSpecifications:
    """Path 1: registered slug + valid payload → Part.specifications populated."""

    def test_ingest_persists_validated_specifications(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        suspension_category: Category,
        default_category_id: UUID,
        coilover_under_suspension: None,
        make_scraped_payload,
    ) -> None:
        valid_specs = {
            "spring_rate_front": 600.0,
            "spring_rate_front_confidence": "high",
            "damper_adjustability": "rebound-and-compression",
            "height_adjustable": True,
        }
        payload = make_scraped_payload(
            name="Sample Coilover Kit",
            description="High-performance coilover suspension.",
            product_url=f"https://example.com/p/coil-valid-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=valid_specs,
        )

        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="test_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )

        # Inferred slug landed on the suspension category, not the default.
        assert part.category_id == suspension_category.id
        # Validated dict round-trips back to JSON-serializable specs.
        assert part.specifications == valid_specs


class TestIngestDropsInvalidSpecifications:
    """Path 2: registered slug + invalid payload → specifications=None, part still created."""

    def test_invalid_specs_drop_to_none_and_part_persists(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        suspension_category: Category,
        default_category_id: UUID,
        coilover_under_suspension: None,
        caplog_with_context: pytest.LogCaptureFixture,
        make_scraped_payload,
    ) -> None:
        # Triggers extra='forbid' rejection.
        bad_specs = {"unknown_field": 1, "another_extra": "x"}
        payload = make_scraped_payload(
            name="Bad Coilover Kit",
            description="Coilover suspension with malformed spec block.",
            product_url=f"https://example.com/p/coil-bad-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=bad_specs,
        )

        with caplog_with_context.at_level(
            logging.WARNING, logger="app.crawlers.base"
        ):
            part = crawler_base.ingest_payload(
                db_session,
                payload,
                adapter_name="bad_adapter",
                **_ingest_kwargs(
                    current_user=test_user, default_category_id=default_category_id
                ),
            )

        # Drop-to-None contract: part still ingests, specifications cleared.
        assert part is not None
        assert part.id is not None
        assert part.specifications is None

        # Locks in the failure-visibility contract for downstream slices:
        # the WARN must mention the adapter name and the inferred category slug.
        warn_records = [
            r for r in caplog_with_context.records if r.levelno == logging.WARNING
        ]
        assert any(
            "spec validation failed" in r.getMessage()
            and "bad_adapter" in r.getMessage()
            and "suspension" in r.getMessage()
            for r in warn_records
        ), f"Expected WARN with adapter+slug, got: {[r.getMessage() for r in warn_records]}"

    def test_type_coercion_failure_drops_to_none(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        suspension_category: Category,
        default_category_id: UUID,
        coilover_under_suspension: None,
        make_scraped_payload,
    ) -> None:
        # spring_rate_front is Optional[float]; non-coercible str → ValidationError.
        bad_specs = {"spring_rate_front": "not-a-number"}
        payload = make_scraped_payload(
            name="Coercion Coilover",
            description="Coilover with a non-numeric spring rate.",
            product_url=f"https://example.com/p/coil-coerce-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=bad_specs,
        )
        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="coerce_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )
        assert part.specifications is None


class TestIngestEmitsExtractionFailureMetric:
    """Path 3: emit_extraction_failure mock is called once with adapter_name kwarg."""

    def test_emit_extraction_failure_called_once_on_invalid_specs(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        suspension_category: Category,
        default_category_id: UUID,
        coilover_under_suspension: None,
        make_scraped_payload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Patch at the IMPORT SITE in app.crawlers.base — Python looks up the
        # name at the call site, so patching app.core.cloudwatch_emf wouldn't
        # intercept the imported reference.
        mock_emitter = MagicMock()
        monkeypatch.setattr(
            "app.crawlers.base.emit_extraction_failure", mock_emitter
        )

        payload = make_scraped_payload(
            name="Metric Test Coilover",
            description="Coilover used to assert metric emission.",
            product_url=f"https://example.com/p/coil-metric-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications={"unknown_field": 1},  # forbidden extra → fail
        )

        crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="metric_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )

        mock_emitter.assert_called_once_with(adapter_name="metric_adapter")


class TestIngestPassThroughCases:
    """Boundary scenarios that must NOT trigger validation."""

    def test_no_spec_block_passes_through_as_none(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        suspension_category: Category,
        default_category_id: UUID,
        coilover_under_suspension: None,
        make_scraped_payload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # specifications=None → validation hook skipped; emitter must not fire.
        mock_emitter = MagicMock()
        monkeypatch.setattr(
            "app.crawlers.base.emit_extraction_failure", mock_emitter
        )

        payload = make_scraped_payload(
            name="No-Specs Coilover",
            description="Coilover with no spec block.",
            product_url=f"https://example.com/p/coil-nospecs-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=None,
        )
        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="passthrough_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )
        assert part.specifications is None
        mock_emitter.assert_not_called()

    def test_unregistered_slug_passes_through_unchanged(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        default_category_id: UUID,
        make_scraped_payload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the inferred category has no spec model, the dict is kept as-is."""
        # No coilover_under_suspension fixture here → registry has nothing
        # for the inferred slug, so the dict passes straight through.
        mock_emitter = MagicMock()
        monkeypatch.setattr(
            "app.crawlers.base.emit_extraction_failure", mock_emitter
        )

        # Seed a "wheels" category — infer_category returns "wheels" for the
        # text below, and the registry has no spec for "wheels".
        wheels_cat = Category(
            name="wheels",
            display_name="Wheels",
            description="Wheels.",
            is_active=True,
            sort_order=4,
        )
        db_session.add(wheels_cat)
        db_session.commit()

        free_form_specs = {"diameter_inches": 19, "color": "matte black"}
        payload = make_scraped_payload(
            name="Forged Wheel Set",
            description="Lightweight forged wheels.",
            product_url=f"https://example.com/p/wheel-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=free_form_specs,
        )
        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="legacy_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )
        # Pass-through: unchanged dict, no emitter, no validation.
        assert part.specifications == free_form_specs
        mock_emitter.assert_not_called()
