#!/usr/bin/env python3
"""M003/S01/T04 — bulk swap of status-color utilities → semantic tokens.

Mechanical regex sweep over .tsx/.ts files in src/. Mirrors the T02/T03 pattern
(MEM153/MEM154). Idempotent: re-running on already-swapped files is a no-op.

Mapping rules (all shade levels collapse; alpha preserved via /A suffix):
  emerald -> success
  amber   -> warning
  rose    -> destructive
  indigo  -> info

Stems covered: bg, text, border, ring, from, to, via, shadow.

The legacy `text-accent-emerald` utility (1 occurrence per research) is also
mapped to `text-success` here for completeness, even though it lives in
src/index.css comments only and is rewritten separately.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"

COLOR_MAP = {
    "emerald": "success",
    "amber": "warning",
    "rose": "destructive",
    "indigo": "info",
}

PREFIX_RE = r"(bg|text|border|ring|from|to|via|shadow)"
COLOR_RE = r"(emerald|amber|rose|indigo)"

# Generic prefix-color-N(/alpha) -> prefix-<semantic>(/alpha)
# e.g.  text-emerald-400      -> text-success
#       bg-emerald-500/10     -> bg-success/10
#       border-amber-500/50   -> border-warning/50
#       border-emerald-700/60 -> border-success/60
GENERIC_RE = re.compile(rf"\b{PREFIX_RE}-{COLOR_RE}-\d+(/\d+)?\b")

# text-accent-{emerald,amber,rose} -> text-{semantic}
# (purple is intentionally out of scope — see plan.)
ACCENT_MAP = {
    "emerald": "success",
    "amber": "warning",
    "rose": "destructive",
}
ACCENT_RE = re.compile(r"\btext-accent-(emerald|amber|rose)\b")


def _generic_sub(m: re.Match[str]) -> str:
    prefix, color, alpha = m.group(1), m.group(2), m.group(3) or ""
    return f"{prefix}-{COLOR_MAP[color]}{alpha}"


def _accent_sub(m: re.Match[str]) -> str:
    return f"text-{ACCENT_MAP[m.group(1)]}"


def transform(text: str) -> str:
    out = GENERIC_RE.sub(_generic_sub, text)
    out = ACCENT_RE.sub(_accent_sub, out)
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
                count = len(GENERIC_RE.findall(original)) + len(
                    ACCENT_RE.findall(original)
                )
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
