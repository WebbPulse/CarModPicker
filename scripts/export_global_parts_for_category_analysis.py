#!/usr/bin/env python3
"""
Export all global parts with full attributes for category-assumption analysis.

Pulls id, name, description, part_number, category, part_manufacturer, specifications,
source, and related fields so you can:
- See how parts are currently categorized
- Find parts with missing/weak descriptions or names
- Identify name/description patterns per category for better auto-categorization
- Spot misclassified or ambiguous parts

Usage:
    cd backend
    python ../scripts/export_global_parts_for_category_analysis.py [--output-dir DIR]

Output (all CSV in --output-dir, default: scripts/output):
    - global_parts_export_all.<timestamp>.csv — all parts (includes part_manufacturer_attribution_issue column)
    - global_parts_export_other.<timestamp>.csv — parts in category "other"
    - global_parts_export_universal_or_unassociated.<timestamp>.csv — is_universal or car_count == 0
    - global_parts_export_multi_car.<timestamp>.csv — parts associated with more than one car
    - global_parts_export_no_part_manufacturer.<timestamp>.csv — parts without a part_manufacturer
    - global_parts_export_suspicious_part_manufacturer.<timestamp>.csv — parts where part_manufacturer looks wrong (chassis code or part code, e.g. E46, VF540)
    - Summary printed to stdout (counts by category, by source, part_manufacturer attribution issues, data quality hints)
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to path so we can import app modules
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

from sqlalchemy.orm import Session, joinedload

from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.car_model import CarModel  # pyright: ignore[reportMissingImports]
from app.api.models.global_part import GlobalPart  # pyright: ignore[reportMissingImports]
from app.db.session import SessionLocal  # pyright: ignore[reportMissingImports]

# PartManufacturer names that look like chassis/platform codes (E46, E9x, F80) — likely wrong attributions.
CHASSIS_LIKE_PART_MANUFACTURER_PATTERN = re.compile(
    r"^[A-Z][0-9]{1,3}x?$|^[A-Z][0-9]{2,}$",
    re.IGNORECASE,
)

# PartManufacturer names that look like part/model codes (VF540, VF570) — should be part_number, not part_manufacturer.
PART_CODE_LIKE_PART_MANUFACTURER_PATTERN = re.compile(
    r"^[A-Za-z]{2,}[0-9]{2,}$|^[A-Za-z]+[0-9]+[A-Za-z]*$",
    re.IGNORECASE,
)


def is_chassis_like_part_manufacturer(part_manufacturer_name: str | None) -> bool:
    """True if part_manufacturer_name looks like a chassis code (E46, E9x) rather than a real part_manufacturer."""
    if not part_manufacturer_name or not part_manufacturer_name.strip():
        return False
    return bool(CHASSIS_LIKE_PART_MANUFACTURER_PATTERN.match(part_manufacturer_name.strip()))


def is_part_code_like_part_manufacturer(part_manufacturer_name: str | None) -> bool:
    """True if part_manufacturer_name looks like a part/model code (VF540, VF570) — should be part_number."""
    if not part_manufacturer_name or len(part_manufacturer_name.strip()) < 3:
        return False
    return bool(PART_CODE_LIKE_PART_MANUFACTURER_PATTERN.match(part_manufacturer_name.strip()))


def part_manufacturer_attribution_issue(part_manufacturer_name: str | None) -> str | None:
    """Return issue code if part_manufacturer looks wrong (chassis or part code), else None."""
    if is_chassis_like_part_manufacturer(part_manufacturer_name):
        return "chassis_code_as_part_manufacturer"
    if is_part_code_like_part_manufacturer(part_manufacturer_name):
        return "part_code_as_part_manufacturer"
    return None


# Optional display-friendly names for export (make, model, generation_name) -> label without years.
# Only used when the default "Make Model Generation" format needs tweaking (e.g. add "GR", parentheses).
# Generation names are kept user-friendly in the source of truth (car_generations_data.py).
CAR_GENERATION_DISPLAY_OVERRIDES: dict[tuple[str, str, str], str] = {
    ("Toyota", "Supra", "A90"): "Toyota GR Supra (A90)",
    ("BMW", "M4", "G82/G83"): "BMW M4 (G82/G83)",
    ("BMW", "M3", "G80"): "BMW M3 (G80)",
}


def car_to_generation_display(c: Car) -> str:
    """Format a Car (generation) as 'Make Model Generation (start-end)'."""
    make = c.car_model.car_make.name if c.car_model and c.car_model.make else "?"
    model = c.car_model.name if c.car_model else "?"
    gen = (c.generation_name or "").strip()
    end = str(c.end_year) if c.end_year else ""
    years = f"({c.start_year}-{end})" if end else f"({c.start_year}-)"
    key = (make, model, gen)
    if key in CAR_GENERATION_DISPLAY_OVERRIDES:
        base = CAR_GENERATION_DISPLAY_OVERRIDES[key]
    else:
        parts = [p for p in [make, model, gen] if p]
        base = " ".join(parts)
    return base + " " + years


def serialize_specs(specs: dict | None) -> str | None:
    """Convert specifications dict to a string for CSV."""
    if specs is None:
        return None
    if isinstance(specs, dict):
        return json.dumps(specs, sort_keys=True)
    return str(specs)


def part_to_record(p: GlobalPart) -> dict:
    """Turn a GlobalPart (with category and part_manufacturer loaded) into a flat record for export."""
    category = p.category
    part_manufacturer = p.part_manufacturer
    part_manufacturer_name = part_manufacturer.name if part_manufacturer else None
    part_manufacturer_issue = part_manufacturer_attribution_issue(part_manufacturer_name)
    return {
        "id": p.id,
        "name": p.name or "",
        "description": (p.description or "").strip() or None,
        "part_number": p.part_number or None,
        "gtin": p.gtin or None,
        "category_id": p.category_id,
        "category_name": category.name if category else None,
        "category_display_name": category.display_name if category else None,
        "part_manufacturer_id": p.part_manufacturer_id,
        "part_manufacturer_name": part_manufacturer_name,
        "part_manufacturer_attribution_issue": part_manufacturer_issue,
        "specifications": p.specifications,
        "source": p.source or None,
        "is_verified": p.is_verified,
        "is_universal": p.is_universal,
        "car_count": len(p.car_generations) if p.car_generations is not None else 0,
        "car_generations": (
            [car_to_generation_display(c) for c in p.car_generations] if p.car_generations else []
        ),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def part_to_csv_row(record: dict) -> dict:
    """One record as CSV-friendly row (specs as JSON string, car_generations as pipe-separated)."""
    row = dict(record)
    row["specifications"] = serialize_specs(record.get("specifications"))
    # Serialize car_generations list as pipe-separated string for CSV
    gens = record.get("car_generations") or []
    row["car_generations"] = " | ".join(gens) if isinstance(gens, list) else str(gens)
    return row


def write_subset(
    records: list[dict],
    out_dir: Path,
    base_name: str,
    ts: str,
) -> None:
    """Write a subset of records to CSV using the same schema as main export."""
    if not records:
        return
    out_csv = out_dir / f"{base_name}.{ts}.csv"
    rows = [part_to_csv_row(r) for r in records]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_csv} ({len(records):,} parts)")


def print_summary(records: list[dict]) -> None:
    """Print summary stats to help identify category-assumption improvements."""
    n = len(records)
    if n == 0:
        print("No global parts found.")
        return

    by_category: dict[str, int] = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    no_description = 0
    short_description = 0  # e.g. < 20 chars
    no_part_number = 0
    short_name = 0  # e.g. < 5 chars
    no_specs = 0
    name_word_count: list[int] = []

    for r in records:
        cat = r.get("category_name") or "unknown"
        by_category[cat] += 1
        src = r.get("source") or "unknown"
        by_source[src] += 1

        desc = (r.get("description") or "").strip()
        if not desc:
            no_description += 1
        elif len(desc) < 20:
            short_description += 1

        if not (r.get("part_number") or "").strip():
            no_part_number += 1

        name = (r.get("name") or "").strip()
        if len(name) < 5:
            short_name += 1
        name_word_count.append(len(name.split()))

        if not r.get("specifications"):
            no_specs += 1

    other_count = sum(1 for r in records if (r.get("category_name") or "").strip().lower() == "other")
    universal_or_unassociated_count = sum(
        1 for r in records
        if r.get("is_universal") is True or (r.get("car_count") or 0) == 0
    )
    multi_car_count = sum(1 for r in records if (r.get("car_count") or 0) > 1)
    no_part_manufacturer_count = sum(1 for r in records if r.get("part_manufacturer_id") is None or not (r.get("part_manufacturer_name") or "").strip())
    chassis_as_part_manufacturer_count = sum(1 for r in records if r.get("part_manufacturer_attribution_issue") == "chassis_code_as_part_manufacturer")
    part_code_as_part_manufacturer_count = sum(1 for r in records if r.get("part_manufacturer_attribution_issue") == "part_code_as_part_manufacturer")

    print("\n" + "=" * 60)
    print("EXPORT SUMMARY (for category assumption improvements)")
    print("=" * 60)
    print(f"Total global parts: {n:,}")
    print(f"  In 'other' category: {other_count:,}")
    print(f"  Universal or unassociated (car_count=0): {universal_or_unassociated_count:,}")
    print(f"  Associated with >1 car: {multi_car_count:,}")
    print(f"  Without a part_manufacturer: {no_part_manufacturer_count:,}")
    print(f"  PartManufacturer attribution issue (chassis code as part_manufacturer): {chassis_as_part_manufacturer_count:,}")
    print(f"  PartManufacturer attribution issue (part code as part_manufacturer, e.g. VF540): {part_code_as_part_manufacturer_count:,}")
    print()
    print("By category:")
    for cat in sorted(by_category.keys()):
        print(f"  {cat}: {by_category[cat]:,}")
    print()
    print("By source:")
    for src in sorted(by_source.keys()):
        print(f"  {src}: {by_source[src]:,}")
    print()
    print("Data quality (signals for better category assumption):")
    print(f"  Missing description: {no_description:,} ({100 * no_description / n:.1f}%)")
    print(f"  Very short description (<20 chars): {short_description:,}")
    print(f"  Missing part_number: {no_part_number:,} ({100 * no_part_number / n:.1f}%)")
    print(f"  Very short name (<5 chars): {short_name:,}")
    print(f"  No specifications: {no_specs:,} ({100 * no_specs / n:.1f}%)")
    if name_word_count:
        avg_words = sum(name_word_count) / len(name_word_count)
        print(f"  Avg words in name: {avg_words:.1f}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export global parts for category-assumption analysis"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for output files (default: scripts/output)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir) if args.output_dir else Path(__file__).parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Remove any existing export files before creating new ones
    for pattern in ("global_parts_export*.csv",):
        for f in out_dir.glob(pattern):
            f.unlink()
            print(f"Removed {f}")

    db: Session = SessionLocal()
    try:
        parts = (
            db.query(GlobalPart)
            .options(
                joinedload(GlobalPart.category),
                joinedload(GlobalPart.part_manufacturer),
                joinedload(GlobalPart.car_generations)
                .joinedload(Car.car_model)
                .joinedload(CarModel.car_make),
            )
            .order_by(GlobalPart.id)
            .all()
        )

        records = [part_to_record(p) for p in parts]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_csv = out_dir / f"global_parts_export_all.{ts}.csv"
        if not records:
            with open(out_csv, "w", encoding="utf-8", newline="") as f:
                f.write("id,name,description,part_number,gtin,category_id,category_name,category_display_name,part_manufacturer_id,part_manufacturer_name,part_manufacturer_attribution_issue,specifications,source,is_verified,is_universal,car_count,car_generations,created_at,updated_at\n")
        else:
            rows = [part_to_csv_row(r) for r in records]
            with open(out_csv, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
        print(f"Wrote {out_csv} ({len(records):,} parts)")

        # Dedicated exports: other category, universal/unassociated, multi-car, no part_manufacturer
        other_records = [r for r in records if (r.get("category_name") or "").strip().lower() == "other"]
        write_subset(other_records, out_dir, "global_parts_export_other", ts)

        universal_or_unassociated = [
            r for r in records
            if r.get("is_universal") is True or (r.get("car_count") or 0) == 0
        ]
        write_subset(
            universal_or_unassociated,
            out_dir,
            "global_parts_export_universal_or_unassociated",
            ts,
        )

        multi_car = [r for r in records if (r.get("car_count") or 0) > 1]
        write_subset(multi_car, out_dir, "global_parts_export_multi_car", ts)

        no_part_manufacturer = [r for r in records if r.get("part_manufacturer_id") is None or not (r.get("part_manufacturer_name") or "").strip()]
        write_subset(no_part_manufacturer, out_dir, "global_parts_export_no_part_manufacturer", ts)

        suspicious_part_manufacturer = [r for r in records if r.get("part_manufacturer_attribution_issue")]
        write_subset(suspicious_part_manufacturer, out_dir, "global_parts_export_suspicious_part_manufacturer", ts)

        print_summary(records)
    finally:
        db.close()


if __name__ == "__main__":
    main()
