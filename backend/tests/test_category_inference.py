"""Tests for category inference from part name and description."""

import pytest

from app.core.category_inference import infer_category


class TestInferCategory:
    """Test infer_category returns expected category names."""

    def test_wheels_from_name(self) -> None:
        assert infer_category("Rays Gram Lights 57CR A90 Supra Wheels Bronze", None) == "wheels"
        assert infer_category("Enkei RPF1 18x9.5", "Lightweight wheel.") == "wheels"

    def test_exhaust_from_name_and_description(self) -> None:
        assert infer_category("HKS Hi-Power Exhaust", "Cat-back exhaust system.") == "exhaust"
        assert infer_category("Muffler", "Axle-back muffler.") == "exhaust"

    def test_brakes(self) -> None:
        assert infer_category("Brembo Brake Pads", "Front brake pads.") == "brakes"
        assert infer_category("Slotted Rotors", None) == "brakes"

    def test_suspension(self) -> None:
        assert infer_category("BC Racing Coilovers", "Coilover kit.") == "suspension"
        assert infer_category("Sway Bar", "Rear sway bar.") == "suspension"

    def test_engine(self) -> None:
        assert infer_category("Cold Air Intake", "Intake system.") == "engine"
        assert infer_category("Turbo Kit", "Turbocharger kit.") == "engine"

    def test_body(self) -> None:
        assert infer_category("Carbon Fiber Lip", "Front lip spoiler.") == "body"
        assert infer_category("Widebody Kit", None) == "body"

    def test_interior(self) -> None:
        assert infer_category("Recaro Seat", "Bucket seat.") == "interior"
        assert infer_category("Shift Knob", "Weighted shift knob.") == "interior"

    def test_steering_wheels_interior_not_wheels(self) -> None:
        # "Steering Wheels" / "steering wheel" = interior (shift paddles, etc.), not Wheels & Tires
        assert (
            infer_category(
                "Rexpeed Forged Carbon Steering Wheels Shift Paddles Extension Supra GR 2020+",
                None,
            )
            == "interior"
        )
        assert infer_category("Steering Wheel Cover", None) == "interior"

    def test_lighting(self) -> None:
        assert infer_category("Oracle RGB DRL Headlight Upgrade", None) == "lighting"
        assert infer_category("Fog Light Kit", "LED fog lights.") == "lighting"

    def test_drivetrain(self) -> None:
        assert infer_category("LSD Differential", "Limited slip differential.") == "drivetrain"
        assert infer_category("Clutch Kit", "Stage 2 clutch.") == "drivetrain"

    def test_other_when_no_match(self) -> None:
        assert infer_category("Random Part XYZ", "Some generic description.") == "other"

    def test_none_when_empty(self) -> None:
        assert infer_category("", "") is None
        assert infer_category(None, None) is None
        assert infer_category("  ", None) is None

    def test_name_weighted_higher(self) -> None:
        # "wheel" in name should win over "exhaust" in description
        assert infer_category("Gram Lights Wheel", "Exhaust tip included.") == "wheels"

    def test_chassis_and_power_brace_suspension(self) -> None:
        # Chassis / power braces → suspension (not exhaust or other)
        assert (
            infer_category(
                "Cusco Rear Chassis Power Brace MKV Supra GR A90 / A91",
                "Cusco Rear Chassis Power Brace for the 2020 GR Supra A90 connects multiple mounting points under the car to maximize stability and rigidity.",
            )
            == "suspension"
        )
        assert infer_category("Cusco Front Power Brace MKV Supra GR A90 / A91", None) == "suspension"
        assert (
            infer_category("HKS - Full Carbon Strut Brace, MKV A90 Supra", "Carbon strut brace.")
            == "suspension"
        )

    def test_fuel_pressure_gauge_engine(self) -> None:
        # Fuel pressure gauge → engine (not interior)
        assert (
            infer_category(
                "Radium Engineering 0-100 PSI Fuel Pressure Gauge",
                "This high-accuracy fuel pressure gauge is suitable for all fueling applications.",
            )
            == "engine"
        )

    def test_tubing_kit_engine(self) -> None:
        # Boost/vacuum tubing kit → engine
        assert (
            infer_category(
                "P3 - Tubing Kit MKV Supra A90",
                "Tubing Kit for N54 engines. Does NOT include boost tap.",
            )
            == "engine"
        )

    def test_door_garnish_and_tow_hook_body(self) -> None:
        # Door garnish, tow hook → body
        assert (
            infer_category("Rexpeed V1 Forged Carbon Side Door Garnish MKV Supra GR", None)
            == "body"
        )
        assert (
            infer_category("Perrin Performance Front Tow Hook, MKV Supra GR", "Tow hook for show.")
            == "body"
        )

    def test_engine_cover_and_ignition_engine(self) -> None:
        # Engine cover, ignition coil → engine (not other)
        assert infer_category("Eventuri Toyota A90 Supra Black Carbon Engine Cover", None) == "engine"
        assert (
            infer_category("Dinan - Ignition Coil B Series Red MKV Supra A90", "Ignition coils.")
            == "engine"
        )

    def test_storage_compartment_interior(self) -> None:
        # Storage compartment cover → interior (not other)
        assert (
            infer_category("Rexpeed Dry Carbon Storage Compartment Cover, MKV Supra", None)
            == "interior"
        )

    def test_door_switch_panel_interior(self) -> None:
        # Door switch panel → interior (not body)
        assert (
            infer_category(
                "Revel GT Dry Carbon Door Switch Panel - Toyota GR Supra A90 2020+",
                "Dry carbon overlays for interior. Door switch panel.",
            )
            == "interior"
        )
