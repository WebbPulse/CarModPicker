"""
M002/S03/T02: One-shot retrofit helper that inserts a
``category_targets: ClassVar[list[str]] = [...]`` line into every concrete
adapter under ``backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}``.

The mapping is owned here (not spread across 108 diffs) so the
specialist→sub-slug assignments stay reviewable in one place. Specialist
adapters declare their concrete sub-slug plus ``"universal"``; everyone else
declares ``["universal"]`` (the safe floor — the S02 category-name → sub-slug
bridge already routes any non-coilover/brake/turbo categorized payload there).

Re-running the script is a no-op: files that already declare
``category_targets =`` are skipped.

Run from ``backend/``::

    python scripts/m002_s03_apply_category_targets.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: Canonical specialist mapping. Every value is a registered slug in
#: ``app.crawlers.specs.default_registry`` (validated at adapter import time
#: by ``RetailerCrawlerAdapter.__init_subclass__``). Adapter slugs not listed
#: here default to ``["universal"]``.
SPECIALIST_MAPPING: dict[str, list[str]] = {
    # Brake specialists.
    "girodisc": ["brake", "universal"],
    "essexparts": ["brake", "universal"],
    "wilwood": ["brake", "universal"],
    "stoptech": ["brake", "universal"],
    # Coilover specialists.
    "bcracing": ["coilover", "universal"],
    "tein": ["coilover", "universal"],
    "stanceusa": ["coilover", "universal"],
    "kwsuspensions": ["coilover", "universal"],
    "fortuneauto": ["coilover", "universal"],
    # Turbo specialists.
    "atpturbo": ["turbo", "universal"],
    "fullrace": ["turbo", "universal"],
}

DEFAULT_TARGETS: list[str] = ["universal"]

ADAPTERS_ROOT = Path(__file__).resolve().parent.parent / "app" / "crawlers" / "adapters"
TIER_DIRS = ("tier0_http", "tier1_tls", "tier2_browser")
SKIP_FILES = {"__init__.py", "base.py", "generic.py"}

#: Capture the ADAPTER_NAME slug literal and the leading whitespace so the new
#: line lands at the same indentation. Tolerates double or single quotes.
ADAPTER_NAME_RE = re.compile(
    r'^(?P<indent>[ \t]*)ADAPTER_NAME\s*:\s*ClassVar\[str\]\s*=\s*["\'](?P<slug>[^"\']+)["\']'
)
EXISTING_TARGETS_RE = re.compile(r"^[ \t]*category_targets\s*[:=]")


def _format_targets(targets: list[str]) -> str:
    inner = ", ".join(f'"{t}"' for t in targets)
    return f"[{inner}]"


def _process_file(path: Path) -> tuple[str, list[str] | None]:
    """Return ``(status, targets)`` where status is one of:

    - ``"updated"`` — wrote the file.
    - ``"already-present"`` — file already declares ``category_targets``; skipped.
    - ``"no-adapter-name"`` — couldn't locate an ``ADAPTER_NAME`` line; skipped.
    """
    text = path.read_text()
    lines = text.splitlines(keepends=True)

    if any(EXISTING_TARGETS_RE.match(line) for line in lines):
        return ("already-present", None)

    for idx, line in enumerate(lines):
        match = ADAPTER_NAME_RE.match(line)
        if match is None:
            continue
        indent = match.group("indent")
        slug = match.group("slug")
        targets = SPECIALIST_MAPPING.get(slug, DEFAULT_TARGETS)
        new_line = f"{indent}category_targets: ClassVar[list[str]] = {_format_targets(targets)}\n"
        # Preserve the original line ending shape: if the ADAPTER_NAME line
        # didn't end in a newline (last line of file), the new line still gets
        # a newline so the file remains parseable.
        if not lines[idx].endswith("\n"):
            lines[idx] = lines[idx] + "\n"
        lines.insert(idx + 1, new_line)
        path.write_text("".join(lines))
        return ("updated", targets)

    return ("no-adapter-name", None)


def main() -> int:
    if not ADAPTERS_ROOT.is_dir():
        print(f"ERROR: adapters root not found: {ADAPTERS_ROOT}", file=sys.stderr)
        return 2

    counts = {"updated": 0, "already-present": 0, "no-adapter-name": 0}
    skipped_files: list[str] = []

    for tier in TIER_DIRS:
        tier_path = ADAPTERS_ROOT / tier
        if not tier_path.is_dir():
            print(f"WARN: missing tier dir: {tier_path}", file=sys.stderr)
            continue
        for path in sorted(tier_path.glob("*.py")):
            if path.name in SKIP_FILES:
                continue
            status, targets = _process_file(path)
            counts[status] += 1
            rel = f"{tier}/{path.name}"
            if status == "updated":
                assert targets is not None
                print(f"{rel}: category_targets = {targets}")
            elif status == "already-present":
                print(f"{rel}: SKIP (already declares category_targets)")
            else:
                skipped_files.append(rel)
                print(f"{rel}: SKIP (no ADAPTER_NAME line found)", file=sys.stderr)

    total = sum(counts.values())
    print()
    print(
        f"Processed {total} adapter file(s): "
        f"{counts['updated']} updated, "
        f"{counts['already-present']} already-present, "
        f"{counts['no-adapter-name']} skipped."
    )
    return 0 if counts["no-adapter-name"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
