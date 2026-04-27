"""One-shot: export CAR_GENERATIONS dict to car_generations_data.json.

Run once per data change, from backend/:
    python scripts/export_car_generations.py

Commits the resulting JSON to git. The script stays in-repo so future data
changes can regenerate the JSON reproducibly.

NOTE: Must be run BEFORE car_generations_data.py is converted to the thin
shim (on a branch where the big dict literal still exists). For Phase 3,
run the script BEFORE step 4 of the plan's Task 2.
"""

from __future__ import annotations

import json
from pathlib import Path

# This import must resolve the pre-shim literal. Run the script before the
# shim replacement lands.
from app.core.car_generations_data import CAR_GENERATIONS

TARGET = Path(__file__).resolve().parent.parent / "app" / "core" / "car_generations_data.json"


def main() -> int:
    TARGET.write_text(
        json.dumps(CAR_GENERATIONS, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
