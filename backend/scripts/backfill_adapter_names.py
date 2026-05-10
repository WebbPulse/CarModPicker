"""One-shot: insert ADAPTER_NAME: ClassVar[str] = '<slug>' into every concrete adapter subclass (CRAWL-02 / D-02).

Idempotent: if a module already has an ``ADAPTER_NAME`` class variable, it is
left untouched. Re-running the script on an already-backfilled tree is a no-op.

Reads the ``ADAPTER_REGISTRY = { "<slug>": ClassName, ... }`` mapping from
``backend/app/crawlers/adapters/__init__.py`` as the single source of truth for
each class's canonical slug (CR-1, PATTERNS.md). The ``generic`` -> GenericHtmlParser
entry is intentionally skipped -- ``generic.py`` lives at the adapters/ root and
is marked ``IS_FALLBACK=True`` rather than carrying an ADAPTER_NAME (per D-03).

Usage (run from backend/):
    python scripts/backfill_adapter_names.py
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ADAPTERS_ROOT = BACKEND_ROOT / "app" / "crawlers" / "adapters"
INIT_PY = ADAPTERS_ROOT / "__init__.py"
TIER_DIRS = (
    ADAPTERS_ROOT / "tier0_http",
    ADAPTERS_ROOT / "tier1_tls",
    ADAPTERS_ROOT / "tier2_browser",
)

# Matches ``    "<slug>": ClassName,`` inside the ADAPTER_REGISTRY literal.
REGISTRY_ENTRY_RE = re.compile(r'\s*"([a-z0-9_\-]+)"\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*,')


def read_registry_map() -> dict[str, str]:
    """Parse the hand-maintained ADAPTER_REGISTRY dict into a {ClassName: slug} map."""
    source = INIT_PY.read_text(encoding="utf-8")
    class_to_slug: dict[str, str] = {}
    for m in REGISTRY_ENTRY_RE.finditer(source):
        slug, cls_name = m.group(1), m.group(2)
        if cls_name == "GenericHtmlParser":
            # Fallback adapter is not under tier*/ and is IS_FALLBACK=True per D-03.
            continue
        if cls_name in class_to_slug and class_to_slug[cls_name] != slug:
            print(
                f"ERROR: class {cls_name} mapped to both " f"{class_to_slug[cls_name]!r} and {slug!r}",
                file=sys.stderr,
            )
            raise SystemExit(1)
        class_to_slug[cls_name] = slug
    return class_to_slug


def find_adapter_class(tree: ast.Module) -> ast.ClassDef | None:
    """Return the first ClassDef whose base list includes RetailerCrawlerAdapter."""
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            # ``class Foo(RetailerCrawlerAdapter):`` -> ast.Name
            if isinstance(base, ast.Name) and base.id == "RetailerCrawlerAdapter":
                return node
    return None


def has_adapter_name(cls: ast.ClassDef) -> bool:
    """Return True if the class already declares an ADAPTER_NAME attribute."""
    for stmt in cls.body:
        # AnnAssign: ``ADAPTER_NAME: ClassVar[str] = "slug"``
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == "ADAPTER_NAME":
                return True
        # Assign: ``ADAPTER_NAME = "slug"``
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "ADAPTER_NAME":
                    return True
    return False


def first_body_line(cls: ast.ClassDef) -> int:
    """Return the 1-based line number of the first class-body statement to insert before.

    Skips a leading docstring (ast.Expr wrapping ast.Constant/str).
    """
    body = cls.body
    if not body:
        # Empty class body -- shouldn't happen for concrete adapters, but be safe.
        raise RuntimeError(f"class {cls.name} has empty body")
    first = body[0]
    # Detect docstring
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        if len(body) > 1:
            return body[1].lineno
        # class has only a docstring -- still insert after it
        end = getattr(first, "end_lineno", first.lineno)
        return end + 1
    return first.lineno


def ensure_classvar_import(source: str) -> str:
    """Ensure ``ClassVar`` is imported from typing. Returns the (possibly modified) source."""
    # Parse once to find existing typing imports.
    tree = ast.parse(source)
    typing_imports: list[ast.ImportFrom] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            typing_imports.append(node)

    if any(any(alias.name == "ClassVar" for alias in imp.names) for imp in typing_imports):
        return source

    lines = source.splitlines(keepends=True)
    if typing_imports:
        # Inject ClassVar into the first ``from typing import ...`` alphabetically.
        imp = typing_imports[0]
        line_no = imp.lineno - 1  # 0-based
        original = lines[line_no]
        # Handle both single-line and multi-line imports; start with the simple
        # single-line shape ``from typing import A, B, C\n``.
        m = re.match(r"^(\s*from typing import )(.+?)(\s*)$", original.rstrip("\n"))
        if m:
            prefix, names_part, _trailing = m.group(1), m.group(2), m.group(3)
            # Split at top-level commas (typing imports don't nest parens in practice).
            names = [n.strip() for n in names_part.split(",")]
            if "ClassVar" not in names:
                names.append("ClassVar")
                names = sorted(names)
                new_line = f"{prefix}{', '.join(names)}\n"
                lines[line_no] = new_line
                return "".join(lines)
        # Fallback: add a new import line after the existing typing import.
        insert_at = imp.lineno  # after imp line (1-based -> 0-based insert index)
        lines.insert(insert_at, "from typing import ClassVar\n")
        return "".join(lines)

    # No existing typing import. Insert after the last top-level import.
    import_nodes: list[ast.stmt] = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    if import_nodes:
        last_imp = import_nodes[-1]
        end = getattr(last_imp, "end_lineno", last_imp.lineno)
        lines.insert(end, "from typing import ClassVar\n")
        return "".join(lines)

    # Truly no imports -- prepend.
    return "from typing import ClassVar\n" + source


def insert_adapter_name(path: Path, slug: str) -> tuple[bool, str]:
    """Insert ``ADAPTER_NAME: ClassVar[str] = "<slug>"`` into the first RetailerCrawlerAdapter subclass.

    Returns (changed, message).
    """
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls = find_adapter_class(tree)
    if cls is None:
        return False, f"{path.relative_to(BACKEND_ROOT)}: no RetailerCrawlerAdapter subclass found -- SKIP"
    if has_adapter_name(cls):
        return False, f"{path.relative_to(BACKEND_ROOT)}: ADAPTER_NAME already present -- SKIP"

    # Ensure ClassVar is importable.
    source = ensure_classvar_import(source)
    # Re-parse after potential import modification so lineno is correct.
    tree = ast.parse(source)
    cls = find_adapter_class(tree)
    assert cls is not None  # noqa: S101

    insert_line_1based = first_body_line(cls)
    insert_line_0based = insert_line_1based - 1

    # Determine the indent of the target line (first class-body statement).
    lines = source.splitlines(keepends=True)
    target_line = lines[insert_line_0based]
    indent_match = re.match(r"^(\s*)", target_line)
    indent = indent_match.group(1) if indent_match else "    "

    new_line = f'{indent}ADAPTER_NAME: ClassVar[str] = "{slug}"\n'
    lines.insert(insert_line_0based, new_line)
    path.write_text("".join(lines), encoding="utf-8")
    return True, f'{path.relative_to(BACKEND_ROOT)}: inserted ADAPTER_NAME="{slug}" at line {insert_line_1based}'


def count_adapter_name_declarations() -> int:
    """Count lines declaring ADAPTER_NAME across all tier*/ adapter modules."""
    pattern = re.compile(r"^\s*ADAPTER_NAME\s*(:|=)")
    total = 0
    for tier_dir in TIER_DIRS:
        for path in tier_dir.rglob("*.py"):
            if path.name == "__init__.py":
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if pattern.search(line):
                    total += 1
                    break  # only count the first declaration per file
    return total


def main() -> int:
    class_to_slug = read_registry_map()
    print(f"Loaded {len(class_to_slug)} concrete adapter slugs from ADAPTER_REGISTRY", file=sys.stderr)

    changed = 0
    skipped = 0
    for tier_dir in TIER_DIRS:
        for path in sorted(tier_dir.rglob("*.py")):
            if path.name == "__init__.py":
                continue
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            cls = find_adapter_class(tree)
            if cls is None:
                print(
                    f"WARNING: {path.relative_to(BACKEND_ROOT)} has no RetailerCrawlerAdapter subclass",
                    file=sys.stderr,
                )
                continue
            slug = class_to_slug.get(cls.name)
            if slug is None:
                print(f"ERROR: unknown class {cls.name} in {path.relative_to(BACKEND_ROOT)}", file=sys.stderr)
                return 1
            ok, msg = insert_adapter_name(path, slug)
            print(msg)
            if ok:
                changed += 1
            else:
                skipped += 1

    total = count_adapter_name_declarations()
    print(f"\nChanged: {changed} file(s); Skipped: {skipped} file(s); Total declarations: {total}", file=sys.stderr)
    if total != 108:
        print(
            f"ERROR: expected 108 ADAPTER_NAME declarations across tier0/1/2 after backfill; got {total}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
