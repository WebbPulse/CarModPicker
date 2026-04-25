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

Bridge wiring (M002/S02/T03)
---------------------------
The production ingest path resolves a registry slug by feeding
``infer_category(name, description)`` (which returns DB category names like
``"suspension"``/``"engine"``/``"wheels"``) into
``app.crawlers.specs.category_bridge.category_to_subslug`` first, and only
then calls ``default_registry.resolve()`` with the bridged sub-slug. The
``coilover_under_suspension`` fixture is retained as a no-op safety net for
older tests that pre-date the bridge; the fixture is harmless because the
registry already knows ``CoiloverSpec`` under the native ``"coilover"`` slug
(populated in ``app.crawlers.specs.__init__``).
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
        # the WARN must mention the adapter name, the inferred DB category,
        # and the bridged sub-slug (coilover) so S04's admin endpoint can
        # show per-sub-category failure rates.
        warn_records = [
            r for r in caplog_with_context.records if r.levelno == logging.WARNING
        ]
        assert any(
            "spec validation failed" in r.getMessage()
            and "bad_adapter" in r.getMessage()
            and "suspension" in r.getMessage()
            and "coilover" in r.getMessage()
            for r in warn_records
        ), f"Expected WARN with adapter+category+subslug, got: {[r.getMessage() for r in warn_records]}"

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

    def test_unmapped_category_validates_against_universal_spec(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        default_category_id: UUID,
        make_scraped_payload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        After the M002/S02/T03 bridge, every non-None inferred category falls
        through to the ``"universal"`` sub-slug when no concrete sub-slug
        applies. UniversalSpec uses ``extra='forbid'`` and only declares the
        five universal fields, so an adapter-supplied free-form dict on a
        wheels-categorized part now triggers fail-soft drop + metric emission
        — that's the change that makes the validation hook fire across the
        catalog.

        Replaces the old "unregistered slug pass-through" contract: with the
        bridge in place, true pass-through only happens when category_name is
        None (i.e. infer_category itself returned None).
        """
        mock_emitter = MagicMock()
        monkeypatch.setattr(
            "app.crawlers.base.emit_extraction_failure", mock_emitter
        )

        # Seed a "wheels" category — infer_category returns "wheels" for the
        # text below, the bridge maps it to "universal", and UniversalSpec
        # rejects unknown keys.
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
        # Bridge → universal → UniversalSpec rejects unknown fields → drop.
        assert part is not None
        assert part.specifications is None
        mock_emitter.assert_called_once_with(adapter_name="legacy_adapter")

    def test_universal_spec_accepts_universal_field_payload(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        default_category_id: UUID,
        make_scraped_payload,
    ) -> None:
        """
        A wheels-categorized part with a payload composed of only the five
        universal fields must validate against UniversalSpec — proving the
        bridge → universal → validate path is the supported way for the long
        tail of categories without a dedicated spec to still flow validated
        specs through.
        """
        existing = (
            db_session.query(Category).filter(Category.name == "wheels").first()
        )
        if existing is None:
            db_session.add(
                Category(
                    name="wheels",
                    display_name="Wheels",
                    description="Wheels.",
                    is_active=True,
                    sort_order=4,
                )
            )
            db_session.commit()

        universal_specs: dict[str, Any] = {
            "weight_grams": 8500.0,
            "weight_grams_confidence": "medium",
            "material": "aluminum",
            "material_confidence": "high",
        }
        payload = make_scraped_payload(
            name="Forged Wheel Set",
            description="Lightweight forged wheels.",
            product_url=f"https://example.com/p/wheel-univ-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=universal_specs,
        )
        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="universal_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )
        assert part.specifications == universal_specs


class TestIngestUsesBridgeToResolveSubslug:
    """
    Lock in the production wiring: the validation hook must use the
    ``category_to_subslug`` bridge to translate ``"suspension"`` →
    ``"coilover"`` before calling ``default_registry.resolve``. Without the
    bridge, no production payload would ever resolve a concrete sub-spec
    (MEM010/MEM016/MEM020).
    """

    def test_coilover_payload_validates_against_coilover_spec(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        suspension_category: Category,
        default_category_id: UUID,
        make_scraped_payload,
    ) -> None:
        # Coilover-specific fields that UniversalSpec would reject (extra='forbid').
        # If validation succeeds, we know CoiloverSpec — not UniversalSpec —
        # was selected.
        coilover_specs = {
            "spring_rate_front": 800.0,
            "spring_rate_front_confidence": "high",
            "damper_adjustability": "rebound-only",
        }
        payload = make_scraped_payload(
            name="Premium Coilover Suspension Kit",
            description="Adjustable coilover suspension with rebound damping.",
            product_url=f"https://example.com/p/bridge-coilover-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications=coilover_specs,
        )
        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="bridge_test_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )
        assert part.category_id == suspension_category.id
        # Validation accepted CoiloverSpec-specific fields → bridge fired.
        assert part.specifications == coilover_specs

    def test_coilover_field_on_wheels_payload_drops_to_none_via_universal(
        self,
        db_session: Session,
        test_user: User,
        test_part_manufacturer: PartManufacturer,
        default_category_id: UUID,
        make_scraped_payload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A coilover-shaped payload on a wheels-categorized part lands on
        UniversalSpec via the bridge and gets rejected — proving the bridge
        sends non-suspension/engine/brakes parents to universal, where
        CoiloverSpec-specific keys aren't accepted."""
        wheels = (
            db_session.query(Category).filter(Category.name == "wheels").first()
        )
        if wheels is None:
            db_session.add(
                Category(
                    name="wheels",
                    display_name="Wheels",
                    description="Wheels.",
                    is_active=True,
                    sort_order=4,
                )
            )
            db_session.commit()

        mock_emitter = MagicMock()
        monkeypatch.setattr(
            "app.crawlers.base.emit_extraction_failure", mock_emitter
        )

        # spring_rate_front is a CoiloverSpec field; UniversalSpec rejects it.
        # Name + description hit only wheels keywords — bridge → universal.
        payload = make_scraped_payload(
            name="Forged Wheel Set",
            description="Lightweight forged wheels for the track.",
            product_url=f"https://example.com/p/bridge-univ-reject-{os.getpid()}",
            part_manufacturer=test_part_manufacturer.name,
            specifications={"spring_rate_front": 800.0},
        )
        part = crawler_base.ingest_payload(
            db_session,
            payload,
            adapter_name="bridge_reject_adapter",
            **_ingest_kwargs(
                current_user=test_user, default_category_id=default_category_id
            ),
        )
        assert part.specifications is None
        mock_emitter.assert_called_once_with(adapter_name="bridge_reject_adapter")
