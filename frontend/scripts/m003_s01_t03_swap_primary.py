#!/usr/bin/env python3
"""M003/S01/T03 — bulk swap of `*-primary-N(/A)?` utilities → semantic tokens.

Mechanical regex sweep over .tsx/.ts files in src/. Mirrors the T02 neutral
sweep pattern (MEM153). Idempotent: re-running on already-swapped files is a no-op.

Mapping rules:
  text-primary-{200,300,400}        -> text-primary
  bg-primary-{500,600}              -> bg-primary
  bg-primary-700                    -> bg-primary/80     (deepest active state)
  bg-primary-400                    -> bg-primary
  bg-primary-N/A                    -> bg-primary/A      (alpha preserved)
  border-primary-{400,500}          -> border-primary
  ring-primary-N(/A)?               -> ring-primary(/A)?
  from|to|via-primary-N(/A)?        -> from|to|via-primary(/A)?
  shadow-primary-N/A                -> shadow-primary/A
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"

# (pattern, replacement) — order matters: more-specific patterns first.
RULES: list[tuple[re.Pattern[str], str]] = [
    # bg-primary-700 (no alpha) -> bg-primary/80 (deepest active state)
    (re.compile(r"\bbg-primary-700\b(?!/)"), "bg-primary/80"),

    # Generic prefix-N(/alpha) for all simple stems.
    # Matches bg|text|border|ring|from|to|via|shadow primary-DIGITS optionally /DIGITS.
    (
        re.compile(
            r"\b(bg|text|border|ring|from|to|via|shadow)-primary-\d+(/\d+)?\b"
        ),
        # Reconstruct with semantic token; preserve optional /alpha.
        lambda m: f"{m.group(1)}-primary{m.group(2) or ''}",
    ),
]


def transform(text: str) -> str:
    out = text
    for pat, repl in RULES:
        if callable(repl):
            out = pat.sub(repl, out)
        else:
            out = pat.sub(repl, out)
    return out


def main() -> int:
    if not ROOT.is_dir():
        print(f"ERROR: src dir not found at {ROOT}", file=sys.stderr)
        return 2

    changed: list[tuple[Path, int]] = []
    total_replacements = 0

    for ext in ("*.tsx", "*.ts"):
        for path in ROOT.rglob(ext):
            original = path.read_text(encoding="utf-8")
            updated = transform(original)
            if updated != original:
                # Count replacements by re-running each rule on the original.
                count = 0
                for pat, _ in RULES:
                    count += len(pat.findall(original))
                path.write_text(updated, encoding="utf-8")
                changed.append((path, count))
                total_replacements += count

    print(f"Files changed: {len(changed)}")
    print(f"Approx replacements: {total_replacements}")
    for path, count in sorted(changed):
        print(f"  {path.relative_to(ROOT.parent)}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
