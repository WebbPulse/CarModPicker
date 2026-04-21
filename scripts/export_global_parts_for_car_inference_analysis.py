#!/usr/bin/env python3
"""
Export scraped-/archive-/extension-sourced parts grouped by adapter, with flags that
point at likely car-inference problems.

Compared to export_global_parts_for_category_analysis.py (which focuses on category/manufacturer
quality), this one is tuned for: "which parts came from which retailer adapter, and what
did car-inference do to them — where did it miss, and where did it guess wrong?"

Usage:
    cd backend
    python ../scripts/export_global_parts_for_car_inference_analysis.py [--output-dir DIR]

Output (default: scripts/output/car_inference_audit/):
    - all_parts.csv — every scraped/archive/extension Part with flags
    - <adapter>.csv — per-adapter slice (one file per adapter that produced parts)
    - summary.csv — per-adapter counts of each flag + total, used to rebalance Stage-2 clusters
    - summary.txt — same data pretty-printed to stdout

Flags (booleans):
    - no_cars_inferred        car_count == 0 AND not is_universal
    - multi_car_inferred      car_count > 3 (noise smell)
    - multi_make_inferred     inferred triples span more than one make
    - adapter_make_mismatch   adapter has expected makes in ADAPTER_TO_EXPECTED_MAKES AND
                              none of the inferred makes are in the expected set
    - wrong_generation_smell  name contains a 4-digit year (19xx/20xx) or `\\d{2}-\\d{2}` range,
                              and no inferred generation's [start_year, end_year] covers that year
    - ambiguous_code_only     name/description contains an AMBIGUOUS_STANDALONE_CODES member
                              (whole-word) AND at least one inferred generation_name matches it
    - universal_with_cars     is_universal AND car_count > 0 (contradictory state)
    - has_year_in_name        year token found in name (useful context, not an issue by itself)

Adapters where the expected-make set is None (generalist / multi-make retailer) skip the
adapter_make_mismatch check — but every other flag still applies.
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add backend/ so imports resolve.
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv  # noqa: E402

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

from sqlalchemy.orm import Session, selectinload  # noqa: E402

from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]  # noqa: E402
from app.api.models.car_model import CarModel  # pyright: ignore[reportMissingImports]  # noqa: E402
from app.api.models.crawled_page import CrawledPage  # pyright: ignore[reportMissingImports]  # noqa: E402
from app.api.models.part import Part  # pyright: ignore[reportMissingImports]  # noqa: E402
from app.core.car_inference import AMBIGUOUS_STANDALONE_CODES  # pyright: ignore[reportMissingImports]  # noqa: E402
from app.db.session import SessionLocal  # pyright: ignore[reportMissingImports]  # noqa: E402


# Adapter -> set of expected CarMake names. None = multi-make (skip mismatch check).
# Keep the keys matching CrawledPage.source values ("a90shop", "ind", etc.).
ADAPTER_TO_EXPECTED_MAKES: dict[str, Optional[set[str]]] = {
    # JDM — make-specific
    "a90shop": {"Toyota"},
    "studiorsr": {"Toyota"},
    "flyinmiata": {"Mazda"},
    "goodwinracing": {"Mazda"},
    "hondata": {"Honda", "Acura"},
    "ktuner": {"Honda", "Acura"},
    "sheepeybuilt": {"Honda", "Acura"},
    "hasport": {"Honda", "Acura"},
    "iagperformance": {"Subaru"},
    "rallysportdirect": {"Subaru"},
    "subispeed": {"Subaru"},
    "prlmotorsports": {"Subaru"},
    "z1motorsports": {"Nissan", "Infiniti"},
    # BMW
    "ind": {"BMW"},
    "bimmerworld": {"BMW"},
    "turnermotorsport": {"BMW"},
    # Euro / VAG / Porsche
    "awetuning": {"Audi", "Volkswagen", "Porsche"},
    "apr": {"Audi", "Volkswagen", "Porsche"},
    "ie": {"Audi", "Volkswagen", "Porsche"},
    "034motorsport": {"Audi", "Volkswagen", "Porsche"},
    "ecstuning": {"Audi", "Volkswagen", "Porsche", "BMW", "Mercedes-Benz", "Mini"},
    "fcpeuro": {"Audi", "Volkswagen", "Porsche", "BMW", "Mercedes-Benz", "Volvo", "Saab", "Mini"},
    "mackinindustries": {"Audi", "Volkswagen", "Porsche"},
    "suncoastparts": {"Porsche"},
    "gmgracing": {"Porsche"},
    # Ford / GM
    "steeda": {"Ford"},
    "americanmuscle": {"Ford"},
    "texasspeed": {"Chevrolet", "GMC", "Cadillac"},
    "briantooleyracing": {"Chevrolet", "GMC", "Cadillac"},
    "katech": {"Chevrolet", "GMC", "Cadillac"},
    "lingenfelter": {"Chevrolet", "GMC", "Cadillac", "Pontiac"},
    "tickperformance": {"Chevrolet", "GMC", "Cadillac", "Pontiac"},
    # Multi-make tuners / forced induction / generalists — skip mismatch check
    "cobbtuning": None,
    "hksusa": None,
    "greddy": None,
    "tomeiusa": None,
    "evasivemotorsports": None,
    "maperformance": None,
    "atpturbo": None,
    "fullrace": None,
    "27won": None,
    "amsperformance": None,
    "functionwerk": None,
    "adro": None,
    "bcracing": None,
    "enjukuracing": None,
    "essexparts": None,
    "girodisc": None,
    "kwsuspensions": None,
    "fortuneauto": None,
    "vividracing": None,
    "wheelsboutique": None,
    "summitracing": None,
    "jegs": None,
    "tirerack": None,
    "speedindustry": None,
    "xph": None,
    # Wheels & chassis — shapes vary, skip mismatch
    "fifteen52": None,
    "titan7": None,
    "hrewheels": None,
    "forgeline": None,
    "apexwheels": None,
    "roadsportsupply": None,
    "driveshaftshop": None,
    # Extension-submitted pages — any retailer; skip
    "chrome_extension": None,
}


_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_YEAR_RANGE_RE = re.compile(r"\b(\d{2})\s*[-–]\s*(\d{2})\b")


def _expand_year_range(token_2digit: tuple[str, str]) -> tuple[int, int] | None:
    """Expand `14-21` to (2014, 2021). Handles both 19xx and 20xx spans heuristically."""
    a, b = token_2digit
    ai, bi = int(a), int(b)

    def _pick_century(y: int) -> int:
        # Two-digit "07" is more likely 2007 than 1907 in a car-parts context, but "95" → 1995.
        return 1900 + y if y >= 50 else 2000 + y

    return (_pick_century(ai), _pick_century(bi))


def extract_years_from_text(text: str) -> list[int]:
    """Return a sorted list of candidate model years from a part name/description.

    Captures both 4-digit (2015, 1998) and 2-digit range (14-21 → 2014, 2015, ..., 2021).
    Ranges longer than 30 years are dropped (likely false positives).
    """
    if not text:
        return []
    years: set[int] = set()
    for m in _YEAR_RE.finditer(text):
        y = int(m.group(1))
        if 1960 <= y <= datetime.now().year + 1:
            years.add(y)
    for m in _YEAR_RANGE_RE.finditer(text):
        pair = _expand_year_range((m.group(1), m.group(2)))
        if pair is None:
            continue
        lo, hi = sorted(pair)
        if hi - lo <= 30:
            years.update(range(lo, hi + 1))
    return sorted(years)


_AMBIGUOUS_WORD_RE = {
    code: re.compile(rf"(?i)(?<![A-Za-z0-9]){re.escape(code)}(?![A-Za-z0-9])")
    for code in AMBIGUOUS_STANDALONE_CODES
}


def ambiguous_codes_in_text(text: str) -> set[str]:
    """Return the AMBIGUOUS_STANDALONE_CODES members that appear as whole tokens in text."""
    if not text:
        return set()
    found: set[str] = set()
    for code, regex in _AMBIGUOUS_WORD_RE.items():
        if regex.search(text):
            found.add(code)
    return found


def triple_from_car_generation(cg: CarGeneration) -> tuple[str, str, str, int | None, int | None]:
    make = cg.car_model.car_make.name if cg.car_model and cg.car_model.car_make else "?"
    model = cg.car_model.name if cg.car_model else "?"
    gen = cg.generation_name or "?"
    return (make, model, gen, cg.start_year, cg.end_year)


def gen_covers_year(start: int | None, end: int | None, year: int) -> bool:
    """Does [start, end] cover `year`? None end -> current."""
    if start is None:
        return False
    effective_end = end if end is not None else datetime.now().year + 1
    return start <= year <= effective_end


def compute_flags(
    adapter: str,
    name: str,
    description: str,
    is_universal: bool,
    triples: list[tuple[str, str, str, int | None, int | None]],
) -> dict[str, bool | int | str]:
    """Compute every flag for one part. Returns a dict suitable for CSV row columns."""
    car_count = len(triples)
    text = f"{name or ''}  {description or ''}"

    # Basic shape
    no_cars_inferred = car_count == 0 and not is_universal
    multi_car_inferred = car_count > 3
    makes_inferred = {t[0] for t in triples}
    multi_make_inferred = len(makes_inferred) > 1
    universal_with_cars = is_universal and car_count > 0

    # Adapter make match
    expected_makes = ADAPTER_TO_EXPECTED_MAKES.get(adapter)
    if expected_makes is None or car_count == 0:
        adapter_make_mismatch = False
    else:
        adapter_make_mismatch = not (makes_inferred & expected_makes)

    # Year coverage
    years_in_text = extract_years_from_text(text)
    if years_in_text and triples:
        # A "wrong generation" smell: there's a year in the name that falls outside every inferred gen's range.
        any_covers = any(
            gen_covers_year(start, end, y)
            for (_, _, _, start, end) in triples
            for y in years_in_text
        )
        wrong_generation_smell = not any_covers
    else:
        wrong_generation_smell = False

    # Ambiguous-code-only smell: a known-ambiguous token is in the text AND at least one inferred gen
    # name matches it. Heuristic — might fire on legitimate alias matches, but rare enough to be worth eyes.
    ambig_in_text = ambiguous_codes_in_text(text)
    inferred_gen_names = {t[2] for t in triples}
    ambiguous_code_only = bool(ambig_in_text & inferred_gen_names)

    has_year_in_name = bool(extract_years_from_text(name or ""))

    return {
        "no_cars_inferred": no_cars_inferred,
        "multi_car_inferred": multi_car_inferred,
        "multi_make_inferred": multi_make_inferred,
        "adapter_make_mismatch": adapter_make_mismatch,
        "wrong_generation_smell": wrong_generation_smell,
        "ambiguous_code_only": ambiguous_code_only,
        "universal_with_cars": universal_with_cars,
        "has_year_in_name": has_year_in_name,
        "inferred_makes": "|".join(sorted(makes_inferred)) if makes_inferred else "",
        "ambig_tokens_in_text": "|".join(sorted(ambig_in_text)) if ambig_in_text else "",
        "years_in_text": "|".join(str(y) for y in years_in_text) if years_in_text else "",
    }


_FLAG_KEYS = (
    "no_cars_inferred",
    "multi_car_inferred",
    "multi_make_inferred",
    "adapter_make_mismatch",
    "wrong_generation_smell",
    "ambiguous_code_only",
    "universal_with_cars",
    "has_year_in_name",
)


def row_for_crawled_page(page: CrawledPage) -> dict | None:
    """Build a flat dict for one CrawledPage→Part pair, or None if the Part is missing."""
    part = page.part
    if part is None:
        return None
    triples = [triple_from_car_generation(cg) for cg in (part.car_generations or [])]
    adapter = page.source or "unknown"
    flags = compute_flags(
        adapter=adapter,
        name=part.name or "",
        description=part.description or "",
        is_universal=part.is_universal,
        triples=triples,
    )
    triples_str = " | ".join(
        f"{mk}|{md}|{gn}|{start or ''}-{end or ''}" for (mk, md, gn, start, end) in triples
    )
    row = {
        "part_id": str(part.id),
        "crawled_page_id": str(page.id),
        "adapter": adapter,
        "source": part.source,
        "url": page.url,
        "name": (part.name or "")[:400],
        "description": (part.description or "")[:800],
        "is_universal": part.is_universal,
        "car_count": len(triples),
        "inferred_triples": triples_str,
        **{k: flags[k] for k in _FLAG_KEYS},
        "inferred_makes": flags["inferred_makes"],
        "ambig_tokens_in_text": flags["ambig_tokens_in_text"],
        "years_in_text": flags["years_in_text"],
        "parse_status": page.parse_status,
        "created_at": part.created_at.isoformat() if part.created_at else None,
        "updated_at": part.updated_at.isoformat() if part.updated_at else None,
    }
    return row


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        # Still write a header-only file so downstream consumers don't choke.
        path.write_text("")
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def write_summary_csv(path: Path, by_adapter: dict[str, list[dict]]) -> None:
    fieldnames = ["adapter", "total", *_FLAG_KEYS, "expected_makes"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for adapter in sorted(by_adapter.keys()):
            rows = by_adapter[adapter]
            summary_row = {"adapter": adapter, "total": len(rows)}
            for key in _FLAG_KEYS:
                summary_row[key] = sum(1 for r in rows if r[key])
            exp = ADAPTER_TO_EXPECTED_MAKES.get(adapter, "UNMAPPED")
            summary_row["expected_makes"] = "|".join(sorted(exp)) if isinstance(exp, set) else ("multi_make" if exp is None else str(exp))
            w.writerow(summary_row)


def print_summary(by_adapter: dict[str, list[dict]]) -> None:
    total_rows = sum(len(v) for v in by_adapter.values())
    if total_rows == 0:
        print("No parts found for any adapter.")
        return
    print("=" * 80)
    print(f"Car-inference audit summary — {total_rows:,} total (part, crawled_page) rows")
    print("=" * 80)

    # Adapter rollup
    header = f"{'adapter':<22} {'total':>7} " + " ".join(f"{k[:16]:>17}" for k in _FLAG_KEYS)
    print(header)
    print("-" * len(header))
    for adapter in sorted(by_adapter.keys()):
        rows = by_adapter[adapter]
        counts = [sum(1 for r in rows if r[k]) for k in _FLAG_KEYS]
        print(f"{adapter:<22} {len(rows):>7,} " + " ".join(f"{c:>17,}" for c in counts))

    # Global rollup
    print("-" * len(header))
    totals = [sum(sum(1 for r in rows if r[k]) for rows in by_adapter.values()) for k in _FLAG_KEYS]
    print(f"{'TOTAL':<22} {total_rows:>7,} " + " ".join(f"{c:>17,}" for c in totals))

    # Adapters unmapped in ADAPTER_TO_EXPECTED_MAKES (new adapters we haven't categorized yet).
    unmapped = sorted(a for a in by_adapter.keys() if a not in ADAPTER_TO_EXPECTED_MAKES)
    if unmapped:
        print()
        print(f"Adapters NOT in ADAPTER_TO_EXPECTED_MAKES ({len(unmapped)}):")
        for a in unmapped:
            print(f"  {a}  ({len(by_adapter[a]):,} parts)")

    # Volume warning
    print()
    print("Per-adapter volume share:")
    for adapter in sorted(by_adapter.keys(), key=lambda a: -len(by_adapter[a])):
        pct = 100.0 * len(by_adapter[adapter]) / total_rows
        marker = "  ⚠ >30%" if pct > 30 else ""
        print(f"  {adapter:<22} {len(by_adapter[adapter]):>7,}  {pct:5.1f}%{marker}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export scraped parts with car-inference audit flags.")
    parser.add_argument("--output-dir", default=None, help="Output directory (default: scripts/output/car_inference_audit/)")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows for quick iteration")
    args = parser.parse_args()

    out_dir = Path(args.output_dir) if args.output_dir else Path(__file__).parent / "output" / "car_inference_audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous export so stale per-adapter files don't linger.
    for existing in out_dir.glob("*.csv"):
        existing.unlink()

    db: Session = SessionLocal()
    try:
        q = (
            db.query(CrawledPage)
            .options(
                selectinload(CrawledPage.part)
                .selectinload(Part.car_generations)
                .joinedload(CarGeneration.car_model)
                .joinedload(CarModel.car_make),
            )
            .filter(CrawledPage.part_id.is_not(None))
            .order_by(CrawledPage.source, CrawledPage.id)
        )
        if args.limit:
            q = q.limit(args.limit)

        rows: list[dict] = []
        by_adapter: dict[str, list[dict]] = defaultdict(list)
        skipped_missing_part = 0
        for page in q.yield_per(500):
            row = row_for_crawled_page(page)
            if row is None:
                skipped_missing_part += 1
                continue
            rows.append(row)
            by_adapter[row["adapter"]].append(row)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        # Master CSV
        all_path = out_dir / "all_parts.csv"
        write_csv(all_path, rows)
        print(f"Wrote {all_path} ({len(rows):,} rows; skipped {skipped_missing_part:,} with no Part)")

        # Per-adapter
        for adapter, adapter_rows in by_adapter.items():
            safe_adapter = re.sub(r"[^A-Za-z0-9_.-]", "_", adapter) or "unknown"
            path = out_dir / f"{safe_adapter}.csv"
            write_csv(path, adapter_rows)
            print(f"  {path.name:<30} {len(adapter_rows):>6,} rows")

        # Summary
        summary_csv = out_dir / "summary.csv"
        write_summary_csv(summary_csv, by_adapter)
        print(f"Wrote {summary_csv}")

        # Metadata
        meta_path = out_dir / "run_meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "generated_at": ts,
                    "total_rows": len(rows),
                    "adapters": sorted(by_adapter.keys()),
                    "skipped_missing_part": skipped_missing_part,
                },
                indent=2,
            )
        )
        print(f"Wrote {meta_path}")

        print()
        print_summary(by_adapter)
    finally:
        db.close()


if __name__ == "__main__":
    main()
