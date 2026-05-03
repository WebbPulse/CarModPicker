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

    def test_door_decals_body(self) -> None:
        """Door decals / cosmetic decals should be body, not suspension or other."""
        assert infer_category("Street Hunter - Door Decals, GR 86 ZN8 BRZ ZD8", None) == "body"
        assert infer_category("Racing Decals Pack", "Vinyl decals for exterior.") == "body"

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
        assert infer_category("HKS - Full Carbon Strut Brace, MKV A90 Supra", "Carbon strut brace.") == "suspension"

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
        assert infer_category("Rexpeed V1 Forged Carbon Side Door Garnish MKV Supra GR", None) == "body"
        assert infer_category("Perrin Performance Front Tow Hook, MKV Supra GR", "Tow hook for show.") == "body"

    def test_engine_cover_and_ignition_engine(self) -> None:
        # Engine cover, ignition coil → engine (not other)
        assert infer_category("Eventuri Toyota A90 Supra Black Carbon Engine Cover", None) == "engine"
        assert infer_category("Dinan - Ignition Coil B Series Red MKV Supra A90", "Ignition coils.") == "engine"

    def test_storage_compartment_interior(self) -> None:
        # Storage compartment cover → interior (not other)
        assert infer_category("Rexpeed Dry Carbon Storage Compartment Cover, MKV Supra", None) == "interior"

    def test_door_switch_panel_interior(self) -> None:
        # Door switch panel → interior (not body)
        assert (
            infer_category(
                "Revel GT Dry Carbon Door Switch Panel - Toyota GR Supra A90 2020+",
                "Dry carbon overlays for interior. Door switch panel.",
            )
            == "interior"
        )

    def test_lug_bolt_wheels(self) -> None:
        assert infer_category("Dinan Lug Bolts M14X1.25 33MM MKV Supra A90", "Lug bolts for spacers.") == "wheels"

    def test_wind_buffeting_body(self) -> None:
        assert infer_category("AMS Performance Anti-Wind Buffeting Kit - MKV Supra", "Fixes wind noise.") == "body"

    def test_other_export_engine_lighting_body_drivetrain(self) -> None:
        """Parts from 'other' export that should infer to engine, lighting, body, suspension, drivetrain, exhaust."""
        # OBD/flash adapter -> engine
        assert (
            infer_category(
                "Bootmod3 - Wireless OBDII WIFI Enet Canbus Flash Adapter",
                "Wireless connection for BMW F and G series and 2020+ Toyota Supra.",
            )
            == "engine"
        )
        # Oil cap, fluid cap, engine bay -> engine
        assert infer_category("Verus Engineering MKV Supra GR Oil Cap", "Aluminum cap for engine bay.") == "engine"
        assert (
            infer_category("Verus Engineering MKV Supra GR Engine Bay Fluid Cap Kit", "Fluid caps for Toyota Supra.")
            == "engine"
        )
        # Air filter -> engine
        assert infer_category("aFe MKV Supra GR Magnum FLOW Pro 5R Air Filter", "Pro 5R air filter media.") == "engine"
        # Rod set -> engine
        assert infer_category("Boost Logic MK5 Supra Rod Set", None) == "engine"
        # Reverse light cover -> lighting
        assert (
            infer_category("Rexpeed MKV Supra GR Forged Carbon Reverse Light Cover", "Reverse light cover.")
            == "lighting"
        )
        # Door sill cover -> interior
        assert (
            infer_category("Rexpeed Forged Carbon Door Sill Cover - MKV Supra", "Sill cover with 3M adhesive.")
            == "interior"
        )
        # Rock guards -> body
        assert (
            infer_category("Rexpeed Dry Carbon Rock Guards (4pcs) Toyota Supra GR A90", "4 pcs for 2020+ Supra.")
            == "body"
        )
        # GR Badge -> body
        assert infer_category('JDC Titanium "GR" Badge (GR Supra/GR 86/GR Corolla)', "Replacement GR badge.") == "body"
        # Reflector set -> lighting
        assert (
            infer_category("Rexpeed Painted Front & Rear Reflector Set", "Painted reflectors, 3M adhesive.")
            == "lighting"
        )
        # LPFP line, throttle booster -> engine
        assert infer_category("PFS - Upgraded LPFP Line MKV Supra A90", "Upgraded LPFP line plug-and-play.") == "engine"
        assert infer_category("Dinan - Throttle Booster MKV Supra A90", "Custom throttle curve.") == "engine"
        # Damping delete / error canceller -> suspension
        assert (
            infer_category(
                "Nitron Electronic Damping Delete Kit (Error Canceller) - 2020+ Toyota A90 Supra",
                "Remove OE electronic suspension worry-free.",
            )
            == "suspension"
        )
        # Short shift kit -> drivetrain
        assert (
            infer_category(
                "Rogue Engineering - Short Shift Kit A90 Toyota Supra", "Short shift lever kit for MKV Supra."
            )
            == "drivetrain"
        )
        # Exhaust conversion kit -> exhaust
        assert (
            infer_category(
                "AWE Track-to-Non-Resonated-Touring Edition Conversion Kit - 2020+ A90 Supra", "Conversion kit."
            )
            == "exhaust"
        )

    def test_engine_internals_extension(self) -> None:
        """Tier-2 audit (2026-05-02): pistons, gaskets, valve-train, AN fittings → engine."""
        # Pistons
        assert infer_category("Wiseco K617M85 Forged Pistons", None) == "engine"
        assert infer_category("Pistons Set", "Forged piston set with rings.") == "engine"
        # Head gasket / gasket set
        assert infer_category("Cometic MLS Head Gasket", "Multi-layer steel head gasket.") == "engine"
        assert infer_category("Mahle Engine Gasket Set", None) == "engine"
        # Valve-train
        assert infer_category("BTR LS Stage 3 Camshaft", "Hydraulic roller camshaft.") == "engine"
        assert infer_category("Valve Spring Kit", "Dual valve springs and retainers.") == "engine"
        assert infer_category("Timing Chain Kit", "Replacement timing chain.") == "engine"
        # Studs
        assert infer_category("ARP Head Stud Kit", "ARP2000 head stud set.") == "engine"
        assert infer_category("ARP Main Studs", None) == "engine"
        assert infer_category("Connecting Rod Stud Kit", None) == "engine"
        # Plumbing — AN fittings + silicone hoses → engine (per Tier-2 audit)
        assert infer_category("Vibrant -8 AN Fitting Straight", "AN fitting straight.") == "engine"
        assert infer_category("Silicone Hose 3-inch", "Reinforced silicone coupler.") == "engine"
        # Crankshaft / oil pump / cylinder head
        assert infer_category("Forged Crankshaft", "Stroker crank.") == "engine"
        assert infer_category("Melling High-Volume Oil Pump", None) == "engine"
        assert infer_category("CNC-Ported Cylinder Head", "LS3 cylinder head with valves.") == "engine"

    def test_accessories_category(self) -> None:
        """Tier-2 audit (2026-05-02): apparel + cosmetic supplies → accessories."""
        # Apparel
        assert infer_category("Brand T-Shirt Black L", "Cotton t-shirt with logo.") == "accessories"
        assert infer_category("Snapback Hat", "Embroidered hat.") == "accessories"
        assert infer_category("Keychain Metal", None) == "accessories"
        assert infer_category("Lanyard", "Branded lanyard.") == "accessories"
        # License plate frame / relocator. ``body`` carries ``license plate``
        # and ``bumper`` already; we don't fight it for relocator brackets
        # whose description references the bumper. Plain titles still hit
        # the more-specific accessories phrase.
        assert infer_category("License Plate Frame Carbon", None) == "accessories"
        assert infer_category("License Plate Relocator Bracket", None) == "accessories"
        # Detailing
        assert infer_category("Microfiber Towel Pack", None) == "accessories"
        assert infer_category("Wax & Polish Bundle", "Carnauba wax + polish.") == "accessories"
        assert infer_category("Wheel Cleaner Spray", "Acid-free wheel cleaner.") == "accessories"

    def test_universal_export_category_fixes(self) -> None:
        """Parts from universal/unassociated export: fix injectors→engine, intake muffler→engine, rocker→body."""
        # Fuel injectors -> engine (not exhaust; "tip" in Extended Tip was matching exhaust)
        assert (
            infer_category(
                "Bosch - 980cc (1000cc) Fuel Injectors",
                "Bosch EV14 high precision injector. Nozzle Extended Tip. Fuel injection.",
            )
            == "engine"
        )
        # Intake muffler delete -> engine (not exhaust; intake resonator/muffler is engine bay)
        assert (
            infer_category(
                "Burger Motorsports - BMS Intake Muffler Delete",
                "Delete the factory intake muffler (resonator) for better sound. B58 engines.",
            )
            == "engine"
        )
        # Side rocker extensions -> body (not engine)
        assert (
            infer_category(
                "APR Performance - Side Rocker Extensions - Toyota GR86",
                "Carbon fiber side rocker extensions. Reduce lift at high speeds.",
            )
            == "body"
        )
        # HKS filter replacement / power flow -> engine (not interior)
        assert (
            infer_category(
                "HKS Super Power Flow Assembly - Full Mushroom Cage & Filter Replacement",
                "Replacement of mushroom filter and cage. Air filter. Air intake efficiency.",
            )
            == "engine"
        )
        # Center console covers -> interior
        assert (
            infer_category("Rexpeed Dry Carbon Center Console Covers (2pcs)", "Carbon fiber center console cover.")
            == "interior"
        )
