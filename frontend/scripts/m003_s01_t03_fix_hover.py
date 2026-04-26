#!/usr/bin/env python3
"""M003/S01/T03 follow-up — restore hover differentiation lost to global swap.

After the bulk primary-N → primary swap, several anchors collapsed to
`text-primary hover:text-primary` (a no-op hover). Per the task plan:
"collapse to `text-primary hover:text-primary/90`" so hover state still reads.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"

# Replace `hover:text-primary` (without alpha) when it follows `text-primary`
# in the same className. Use word-boundary lookahead so we don't match
# `hover:text-primary/90` etc.
PATTERN = re.compile(r"text-primary(\s+)hover:text-primary(?![/\w-])")
REPLACEMENT = r"text-primary\1hover:text-primary/90"


def main() -> int:
    changed: list[tuple[Path, int]] = []
    total = 0
    for ext in ("*.tsx", "*.ts"):
        for path in ROOT.rglob(ext):
            text = path.read_text(encoding="utf-8")
            new_text, count = PATTERN.subn(REPLACEMENT, text)
            if count:
                path.write_text(new_text, encoding="utf-8")
                changed.append((path, count))
                total += count
    print(f"Files changed: {len(changed)}; replacements: {total}")
    for path, count in sorted(changed):
        print(f"  {path.relative_to(ROOT.parent)}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
