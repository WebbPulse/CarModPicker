"""PARTS-02 regression: pin current car_inference ambiguity-resolution behavior.

NOTE: these tests assert CURRENT BEHAVIOR, not CORRECTNESS. The ML-based
rewrite (PARTS-V2-01) deferred to v2 will invert some of these expectations.
Do NOT fix individual vectors to match intuition — file a v2 issue instead
and update the vectors only when the behavior itself is intentionally changed.

Each vector pins one (or zero) expected generation triple for a given
(name, description) pair. The test fails if current behavior drifts from the
pinned expectation. This gives us a CI-visible signal whenever changes to
AMBIGUOUS_STANDALONE_CODES / PHRASE_TRIPLES / CAR_ALIASES shift ambiguity
resolution for well-known collision cases.
"""

from __future__ import annotations

from typing import Optional

import pytest

from app.core.car_inference import infer_car_generations

# Each vector: (name, description, expected_tuple_if_should_match_or_None, rationale)
#
# When `expected` is None, the vector pins "no match for the collision code"
# (the code is in AMBIGUOUS_STANDALONE_CODES and nothing disambiguates it).
# When `expected` is a tuple, the vector pins that the tuple appears in the
# result (other tuples may also appear — we assert containment, not equality).
AMBIGUITY_VECTORS: list[tuple[str, Optional[str], Optional[tuple[str, str, str]], str]] = [
    # --- Explicit disambiguation — SHOULD match ---
    (
        "Cusco Rear Chassis Power Brace MKV Supra GR A90 / A91",
        "Cusco Rear Chassis Power Brace for the 2020 GR Supra A90.",
        ("Toyota", "Supra", "A90"),
        "MKV Supra A90 — multiple explicit aliases present",
    ),
    (
        "Remark Toyota Supra GR A90 Full Titanium Cat-Back Exhaust",
        None,
        ("Toyota", "Supra", "A90"),
        "Toyota Supra GR A90 explicit in name",
    ),
    (
        "Vorsteiner BMW G8X M3 Gloss Black Front Grille",
        "G82 M4 compatible.",
        ("BMW", "M3", "G80"),
        "G8X M3 alias fires — BMW context present",
    ),
    (
        "FK8 Civic Type R Front Lip",
        "FK8 Type R.",
        ("Honda", "Civic Type R", "FK8"),
        "FK8 is not in AMBIGUOUS_STANDALONE_CODES; alias fires",
    ),
    (
        "Honda Civic 10th Gen Cold Air Intake",
        None,
        ("Honda", "Civic", "10th Gen"),
        "Civic 10th Gen alias fires — explicit Honda Civic context",
    ),
    (
        "Toyota GR Corolla Cold Air Intake",
        "Fits GR Corolla E210 platform.",
        ("Toyota", "GR Corolla", "1st Gen"),
        "GR Corolla alias fires — Toyota GR Corolla unambiguous",
    ),
    (
        "BMW E46 M3 Differential Bushings",
        "E46 M3 chassis upgrade.",
        ("BMW", "M3", "E46"),
        "E46 M3 explicit alias fires despite E46 in AMBIGUOUS_STANDALONE_CODES",
    ),
    # --- Ambiguous-standalone codes WITHOUT adjacent make+model — should NOT fire ---
    (
        "HKS Hi Power Exhaust Universal",
        None,
        None,
        "HI is ambiguous standalone — no adjacent make+model",
    ),
    (
        "CTEK MXS 5.0 NA Battery Charger",
        None,
        None,
        "NA is ambiguous standalone — product code, not Miata NA",
    ),
    (
        "Bilstein B4 OE Replacement Shock Absorber",
        None,
        None,
        "B4 is ambiguous — Bilstein B4 product line, not Audi RS2 B4",
    ),
    (
        "Bilstein EVO T1 Coilover System",
        None,
        None,
        "EVO is ambiguous — Bilstein EVO product line, not Lamborghini Huracán EVO",
    ),
    (
        "D2 Racing RS Coilovers",
        None,
        None,
        "D2 is ambiguous — D2 Racing brand, not a generation code standalone",
    ),
    (
        "Rexpeed V10 Carbon Fiber Mirror Cover",
        None,
        None,
        "V10 is ambiguous — product model name, not Camry V10 generation",
    ),
    (
        "ADRO AT-P1 Front Bumper",
        None,
        None,
        "P1 is ambiguous — product SKU (AT-P1), not McLaren P1",
    ),
    (
        "ACT HD Heavy Duty Clutch Kit",
        None,
        None,
        "HD is ambiguous — product branding, not Hyundai Elantra HD",
    ),
    (
        "Bilstein B6 Performance Shock",
        None,
        None,
        "B6 is ambiguous — Bilstein B6, not Audi A4/S4 B6 or Miata B6 engine",
    ),
    (
        "Bilstein B8 5100 Shock",
        None,
        None,
        "B8 is ambiguous — Bilstein B8 shock line, not Audi A4 B8",
    ),
    (
        "Bilstein B16 PSS9 Coilover",
        None,
        None,
        "B16 is ambiguous — Bilstein B16 coilover, not Nissan Sentra B16 / Honda B16",
    ),
    (
        "KW V3 Coilovers Universal Fit",
        None,
        None,
        "V and V3 roman-numeral standalone — no adjacent make+model",
    ),
    (
        "ARE S1 Silicone Hose",
        None,
        None,
        "S1 is ambiguous — product SKU, not Mazda RX-3 S1",
    ),
    (
        "Cusco Type OS Rear Strut Bar",
        None,
        None,
        "OS is ambiguous — Cusco product line, not Kona N OS generation",
    ),
    (
        "MAGDRAIN MD-05 Magnetic Drain Bolt",
        None,
        None,
        "MD is ambiguous — product prefix, not Hyundai Elantra MD",
    ),
    (
        "Thule AirScreen XT Roof Rack",
        None,
        None,
        "XT is ambiguous — product trim, not Subaru Forester XT",
    ),
    (
        "BP Automotive Standalone Harness",
        None,
        None,
        "BP is ambiguous — BP Automotive brand, not Mazda3 BP",
    ),
    (
        "KW RS Coilovers Universal",
        None,
        None,
        "RS is ambiguous — KW RS product line, not Honda HR-V RS",
    ),
    (
        "0.42 Mu Brake Pad Friction Coefficient",
        None,
        None,
        "42 is decimal-fractional; Audi R8 42 false-positive guard rejects",
    ),
]


# Negative-vector map: when a negative vector's input produces OTHER (allowed) matches
# under current behavior, we only assert a specific triple does NOT appear, rather than
# requiring the full result to be empty. Key: (name, desc). Value: forbidden triple.
#
# The 19 negative vectors not listed here must produce an EMPTY inference result.
NEGATIVE_FORBIDDEN_TUPLES: dict[tuple[str, Optional[str]], tuple[str, str, str]] = {
    # Bilstein EVO T1 — the "T1" token legitimately matches GM trucks. The ambiguity
    # we're pinning is that EVO standalone does NOT fire Huracán EVO, not that the
    # whole inference must be empty.
    ("Bilstein EVO T1 Coilover System", None): ("Lamborghini", "Huracán", "EVO"),
}


@pytest.mark.parametrize(
    "name,desc,expected,rationale",
    AMBIGUITY_VECTORS,
)
def test_ambiguity_resolution_pins_current_behavior(
    name: str,
    desc: Optional[str],
    expected: Optional[tuple[str, str, str]],
    rationale: str,
) -> None:
    """pins current behavior — see module docstring for non-correctness caveat.

    Vector semantics:
    - `expected` is a tuple → that triple must appear in the result (other matches allowed).
    - `expected` is None and the vector is in NEGATIVE_EXPECTING_EMPTY → result must be empty.
    - `expected` is None and the vector is in NEGATIVE_FORBIDDEN_TUPLES → the mapped tuple
      must NOT appear in the result (other matches are permitted).
    """
    result = infer_car_generations(name, desc)
    if expected is not None:
        assert expected in result, f"{rationale}: expected {expected} in result, got {result}"
        return

    forbidden = NEGATIVE_FORBIDDEN_TUPLES.get((name, desc))
    if forbidden is not None:
        assert forbidden not in result, f"{rationale}: forbidden {forbidden} must not appear, got {result}"
    else:
        assert result == [], f"{rationale}: expected no inference, got {result}"


def test_vector_count_meets_floor() -> None:
    """Plan 04-06 D-37 requires at least 20 vectors."""
    assert len(AMBIGUITY_VECTORS) >= 20, f"Expected >=20 ambiguity vectors; got {len(AMBIGUITY_VECTORS)}"


# ---------------------------------------------------------------------------
# Tier-1 audit (2026-05) false-positive purge regression tests.
#
# The audit found ``_build_phrase_triples`` was splitting gen_name strings like
# ``Turbo/Shelby``, ``BE/BH``, ``R/T Turbo``, ``E36/7 E36/8`` and ``V1`` into
# 1-2 char tokens that matched English words and SKU fragments inside product
# titles. The fix:
#   * Adds the offending whole-gen-name strings + their generic alpha
#     components to ``AMBIGUOUS_STANDALONE_CODES``.
#   * Adds a ``_is_too_short_to_dispatch`` length filter that drops pure-alpha
#     < 4 chars and pure-digit < 3 chars (always rejects single digits).
#
# These tests pin the post-fix behavior so the Tier-1 cleanup migration does
# not silently regress.
# ---------------------------------------------------------------------------


class TestTier1AuditFalsePositivePurge:
    def test_garrett_turbo_supercore_no_dodge_daytona(self) -> None:
        """'turbo' inside a generic part title must NOT fire Dodge Daytona Turbo/Shelby."""
        result = infer_car_generations(
            "Garrett G30-770 Supercore",
            "High-flow turbo upgrade for street and track use.",
        )
        assert ("Dodge", "Daytona", "Turbo/Shelby") not in result
        assert ("Dodge", "Stealth", "R/T Turbo") not in result

    def test_kw_v3_must_be_installed_no_subaru_legacy_be_bh(self) -> None:
        """'V3 must be installed' product copy must NOT fire Subaru Legacy BE/BH."""
        result = infer_car_generations("KW V3 must be installed", "", None)
        assert ("Subaru", "Legacy", "BE/BH") not in result
        assert ("Subaru", "Legacy GT", "BE/BH") not in result
        assert ("Volvo", "S40", "V1") not in result
        assert ("Volvo", "V40", "V1") not in result

    def test_borgwarner_k27_turbo_no_daytona_no_z3m(self) -> None:
        """'K27 Turbo' must NOT fire Daytona Turbo/Shelby OR BMW Z3 M E36/7 / E36/8."""
        result = infer_car_generations("BorgWarner K27 Turbo", "", None)
        assert ("Dodge", "Daytona", "Turbo/Shelby") not in result
        assert ("Dodge", "Stealth", "R/T Turbo") not in result
        assert ("BMW", "Z3 M", "E36/7") not in result
        assert ("BMW", "Z3 M", "E36/8") not in result
        assert ("BMW", "Z3", "E36/7 E36/8") not in result

    def test_e92_m3_still_attributes_correctly(self) -> None:
        """Positive case: an explicit 'E92 M3' title must still resolve to BMW M3 E90/E92/E93."""
        result = infer_car_generations("BMW E92 M3 Carbon Fiber Trunk Spoiler", None)
        assert ("BMW", "M3", "E90/E92/E93") in result

    def test_explicit_legacy_be_bh_phrase_still_matches(self) -> None:
        """Positive case: 'Subaru Legacy BE/BH' as a full phrase must still match."""
        result = infer_car_generations("Subaru Legacy BE/BH 2.0L Engine Mount", None)
        assert ("Subaru", "Legacy", "BE/BH") in result

    def test_pure_digit_single_char_never_dispatches(self) -> None:
        """Bare '7' / '8' tokens must never fire BMW Z3 E36/7 / E36/8."""
        result = infer_car_generations("Random product with 7 ports and 8 channels", None)
        assert ("BMW", "Z3 M", "E36/7") not in result
        assert ("BMW", "Z3 M", "E36/8") not in result
        assert ("BMW", "Z3", "E36/7 E36/8") not in result

    def test_dodge_stealth_rt_turbo_no_random_r_t(self) -> None:
        """Generic 'R' or 'T' tokens must NOT fire Dodge Stealth R/T Turbo."""
        result = infer_car_generations("Some R-spec T-bracket clamp", None)
        assert ("Dodge", "Stealth", "R/T Turbo") not in result

    def test_aria_battery_no_miata_nb_nc_nd(self) -> None:
        """Generic '... ND ...' / '... NC ...' fragments must NOT fire Miata generations."""
        result = infer_car_generations("AntiGravity ATX-30-HD Battery Replacement", None)
        assert ("Mazda", "Miata", "ND") not in result
        assert ("Mazda", "Miata", "NC") not in result
        assert ("Mazda", "Miata", "NB") not in result

    def test_kw_rs_no_subaru_wrx_va_vb(self) -> None:
        """'VA' / 'VB' as state-abbrev / SKU prefix must NOT fire Subaru WRX VA/VB."""
        result = infer_car_generations("KW RS Coilovers Universal Fit", None)
        assert ("Subaru", "WRX", "VA") not in result
        assert ("Subaru", "WRX", "VB") not in result
