#!/usr/bin/env python3
"""
Export all global parts with full attributes for category-assumption analysis.

Pulls id, name, description, part_number, category, brand, specifications,
source, and related fields so you can:
- See how parts are currently categorized
- Find parts with missing/weak descriptions or names
- Identify name/description patterns per category for better auto-categorization
- Spot misclassified or ambiguous parts

Usage:
    cd backend
    python ../scripts/export_global_parts_for_category_analysis.py [--output-dir DIR] [--format json|csv|both]

Output:
    - global_parts_export.<timestamp>.json (and/or .csv) in --output-dir (default: scripts/output)
    - Summary printed to stdout (counts by category, by source, data quality hints)
"""

import argparse
import csv
import json
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

from app.api.models.global_part import GlobalPart  # pyright: ignore[reportMissingImports]
from app.db.session import SessionLocal  # pyright: ignore[reportMissingImports]


def serialize_specs(specs: dict | None) -> str | None:
    """Convert specifications dict to a string for CSV; keep as dict for JSON."""
    if specs is None:
        return None
    if isinstance(specs, dict):
        return json.dumps(specs, sort_keys=True)
    return str(specs)


def part_to_record(p: GlobalPart) -> dict:
    """Turn a GlobalPart (with category and brand loaded) into a flat record for export."""
    category = p.category
    brand = p.brand
    return {
        "id": p.id,
        "name": p.name or "",
        "description": (p.description or "").strip() or None,
        "part_number": p.part_number or None,
        "gtin": p.gtin or None,
        "category_id": p.category_id,
        "category_name": category.name if category else None,
        "category_display_name": category.display_name if category else None,
        "brand_id": p.brand_id,
        "brand_name": brand.name if brand else None,
        "specifications": p.specifications,
        "source": p.source or None,
        "is_verified": p.is_verified,
        "is_universal": p.is_universal,
        "car_count": len(p.cars) if p.cars is not None else 0,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def part_to_csv_row(record: dict) -> dict:
    """One record as CSV-friendly row (specs as JSON string)."""
    row = dict(record)
    row["specifications"] = serialize_specs(record.get("specifications"))
    return row


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

    print("\n" + "=" * 60)
    print("EXPORT SUMMARY (for category assumption improvements)")
    print("=" * 60)
    print(f"Total global parts: {n:,}")
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
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Output format (default: both)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir) if args.output_dir else Path(__file__).parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    db: Session = SessionLocal()
    try:
        parts = (
            db.query(GlobalPart)
            .options(
                joinedload(GlobalPart.category),
                joinedload(GlobalPart.brand),
                joinedload(GlobalPart.cars),
            )
            .order_by(GlobalPart.id)
            .all()
        )

        records = [part_to_record(p) for p in parts]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = out_dir / f"global_parts_export.{ts}"

        if args.format in ("json", "both"):
            # JSON: keep specifications as dict
            out_json = base.with_suffix(".json")
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            print(f"Wrote {out_json} ({len(records):,} parts)")

        if args.format in ("csv", "both"):
            out_csv = base.with_suffix(".csv")
            if not records:
                with open(out_csv, "w", encoding="utf-8", newline="") as f:
                    f.write("id,name,description,part_number,gtin,category_id,category_name,category_display_name,brand_id,brand_name,specifications,source,is_verified,is_universal,car_count,created_at,updated_at\n")
            else:
                rows = [part_to_csv_row(r) for r in records]
                with open(out_csv, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=rows[0].keys())
                    w.writeheader()
                    w.writerows(rows)
            print(f"Wrote {out_csv} ({len(records):,} parts)")

        print_summary(records)
    finally:
        db.close()


if __name__ == "__main__":
    main()
