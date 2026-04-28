"""Pin the post-S03 manufacturer baseline so silent regressions on the bootstrap fixture are loud.

S03 lifts manufacturer P/R/F1 by adding `part_manufacturer_universal` (T02),
override hooks (T03), a widened harness predictor (T04), and any per-adapter
overrides driven by gold-set error analysis (T05). The merge gate is "≥10%
relative F1 lift on the gold set," but at the 5-row bootstrap fixture the
gate is held until the operator expands the gold set per
`.gsd/milestones/M004/slices/S03/S03-OPERATOR-HANDOFF.md`.

**T04 re-locked the baseline against post-S03 production code.** The
universal predictor (jsonld_brand×2, microdata×2, opengraph×1) resolves all
5 bootstrap rows, so manufacturer P/R/F1 saturate at 1.0 on the bootstrap
fixture. This test now pins the post-S03 numbers:

    precision = 1.0
    recall    = 1.0
    f1        = 1.0
    sample_size = 5
    harness_version = 1

The **pre-S03** numbers (P=R=0.20, F1=0.20000000000000004) are preserved as
historical reference in the post-S03 directional-lift table inside
`S03-OPERATOR-HANDOFF.md` and the per-source / per-row breakdown in
`S03-LIFT-REPORT.md`. Future re-locks (e.g. T05 per-adapter overrides, or
post gold-set expansion) update the pinned values below — the test failing
is still the cue.

Path resolution: pytest is invoked from `backend/` (per MEM209/MEM220), so
this test file lives at `backend/tests/scripts/test_m004_s03_baseline_freeze.py`
and reaches the repo root via `Path(__file__).resolve().parents[3]`. The
S03 plan text initially said `parents[2]`, which would resolve to `backend/`
and miss the `.gsd/` tree — corrected here against the convention used by
`test_m004_accuracy_harness.py:32`.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

# parents[0] = backend/tests/scripts/
# parents[1] = backend/tests/
# parents[2] = backend/                  (matches sibling tests' _BACKEND_DIR)
# parents[3] = repo root (contains .gsd/)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_PATH = (
    _REPO_ROOT / ".gsd" / "milestones" / "M004" / "baselines" / "manufacturer.json"
)


@pytest.fixture(scope="module")
def manufacturer_baseline() -> dict[str, object]:
    assert _BASELINE_PATH.is_file(), (
        f"Pre-S03 manufacturer baseline missing at {_BASELINE_PATH}. "
        "If you intentionally re-locked the baseline, update the pinned "
        "values in this test and append the post-S03 directional lift to "
        "S03-OPERATOR-HANDOFF.md."
    )
    return json.loads(_BASELINE_PATH.read_text(encoding="utf-8"))


def test_signal_is_manufacturer(manufacturer_baseline: dict[str, object]) -> None:
    assert manufacturer_baseline["signal"] == "manufacturer"


def test_harness_version_pinned(manufacturer_baseline: dict[str, object]) -> None:
    # HARNESS_VERSION is the schema-drift gate (MEM210). Bumping it is the
    # explicit cue that prior baselines must be regenerated.
    assert manufacturer_baseline["harness_version"] == 1


def test_sample_size_is_bootstrap_five(manufacturer_baseline: dict[str, object]) -> None:
    # Five-row bootstrap fixture (MEM213). When this changes, the operator
    # expansion in S03-OPERATOR-HANDOFF.md has happened and this test must be
    # updated alongside the new baseline values.
    assert manufacturer_baseline["sample_size"] == 5


def test_precision_pinned(manufacturer_baseline: dict[str, object]) -> None:
    # Post-S03: universal predictor resolves all 5 bootstrap rows via
    # structured markup (jsonld_brand x2, microdata x2, opengraph x1).
    assert math.isclose(
        float(manufacturer_baseline["precision"]),
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_recall_pinned(manufacturer_baseline: dict[str, object]) -> None:
    assert math.isclose(
        float(manufacturer_baseline["recall"]),
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_f1_pinned(manufacturer_baseline: dict[str, object]) -> None:
    # Post-S03: precision=recall=1.0 → f1 saturates at exactly 1.0 (no
    # float-roundtrip drift at 1.0/1.0 — the 0.20000000000000004 quirk only
    # showed up at the pre-S03 0.2/0.2 numbers).
    assert math.isclose(
        float(manufacturer_baseline["f1"]),
        1.0,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_baseline_has_generated_at_timestamp(
    manufacturer_baseline: dict[str, object],
) -> None:
    # Sanity check on the schema — the ISO timestamp varies per run but the
    # field must be present so a downstream re-lock writes a fresh stamp.
    assert isinstance(manufacturer_baseline.get("generated_at"), str)
    assert manufacturer_baseline["generated_at"].strip() != ""
