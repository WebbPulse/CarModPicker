#!/usr/bin/env python3
"""M003/S01/T04 — repair hover no-ops introduced by the status palette swap.

After the bulk swap collapses shade-pairs like `text-emerald-300 hover:text-emerald-200`
into `text-success hover:text-success`, hover differentiation disappears. This
script restores it by rewriting `<prefix>-<sem> hover:<prefix>-<sem>` →
`<prefix>-<sem> hover:<prefix>-<sem>/90`. Mirrors the T03 hover-fix pattern (MEM154).

Idempotent: only matches the exact no-op form; rerunning is a no-op.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"

PREFIX = r"(text|bg|border)"
SEM = r"(success|warning|destructive|info)"

# Match `<prefix>-<sem> hover:<prefix>-<sem>` where the hover token has no /alpha.
# The negative lookahead (?!/) prevents re-matching already-repaired forms.
NOOP_RE = re.compile(
    rf"\b{PREFIX}-{SEM}\b(\s+)hover:\1-\2\b(?!/)"
)


def transform(text: str) -> str:
    return NOOP_RE.sub(lambda m: f"{m.group(1)}-{m.group(2)}{m.group(3)}hover:{m.group(1)}-{m.group(2)}/90", text)


def main() -> int:
    if not ROOT.is_dir():
        print(f"ERROR: src dir not found at {ROOT}", file=sys.stderr)
        return 2

    changed: list[tuple[Path, int]] = []
    total = 0
    for ext in ("*.tsx", "*.ts"):
        for path in ROOT.rglob(ext):
            original = path.read_text(encoding="utf-8")
            updated = transform(original)
            if updated != original:
                count = len(NOOP_RE.findall(original))
                path.write_text(updated, encoding="utf-8")
                changed.append((path, count))
                total += count
    print(f"Files changed: {len(changed)}")
    print(f"Approx repairs: {total}")
    for path, count in sorted(changed):
        print(f"  {path.relative_to(ROOT.parent)}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
