"""Resolve the API Gateway route key a probe path is expected to match.

`verify_route_cut.sh` asserts that a probe request landed on its domain's own
route key rather than falling through. Predicting that key with a string rule
is what kept breaking: every row that promotes a path to its own explicit key
changes which key a probe below a prefix resolves to, and the script's
expectation went stale each time.

This resolves the expectation the way the gateway does instead. The declared
route keys are read out of terraform/apigateway.tf and matched against the probe
path with API Gateway's own precedence: a literal segment beats a `{var}`
segment, a `{var}` segment beats a greedy `{proxy+}`, and a longer literal
prefix wins over a shorter one. A key added or removed in Terraform therefore
needs no edit here.
"""

from __future__ import annotations

import json
import re
import sys

ROUTE_KEY_PATTERN = re.compile(r'"((?:ANY|GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /[^"\s]*)"')

LITERAL = 2
VARIABLE = 1
GREEDY = 0


def declared_route_keys(terraform_source: str) -> list[str]:
    """Every route key literal declared in the Terraform source."""
    return sorted(set(ROUTE_KEY_PATTERN.findall(terraform_source)))


def generated_route_keys(prefixes: list[str]) -> list[str]:
    """The bare and `{proxy+}` pair that every cut prefix generates."""
    keys = []
    for prefix in prefixes:
        keys.append("ANY %s" % prefix)
        keys.append("ANY %s/{proxy+}" % prefix)
    return keys


def _segment_score(segment: str) -> int:
    if segment == "{proxy+}":
        return GREEDY
    if segment.startswith("{") and segment.endswith("}"):
        return VARIABLE
    return LITERAL


def _match_score(key_path: str, path: str) -> tuple | None:
    """Precedence score for a key against a path, or None when it cannot match.

    Higher sorts better. The score is the per-segment kind from left to right,
    so a literal beats a `{var}` at the first segment they differ on, which is
    the order API Gateway resolves in.
    """
    key_segments = key_path.strip("/").split("/")
    path_segments = path.strip("/").split("/")

    score = []
    for index, key_segment in enumerate(key_segments):
        if key_segment == "{proxy+}":
            if index >= len(path_segments):
                return None
            score.append(GREEDY)
            return (len(score), tuple(score))
        if index >= len(path_segments):
            return None
        kind = _segment_score(key_segment)
        if kind == LITERAL and key_segment != path_segments[index]:
            return None
        score.append(kind)

    if len(key_segments) != len(path_segments):
        return None
    return (len(score), tuple(score))


def resolve(path: str, method: str, route_keys: list[str]) -> str:
    """The route key the gateway resolves `method path` to, or "" for none."""
    best_key = ""
    best_score = None

    for key in route_keys:
        key_method, _, key_path = key.partition(" ")
        if key_method != "ANY" and key_method != method:
            continue

        score = _match_score(key_path, path)
        if score is None:
            continue

        ranked = (score, key_method != "ANY")
        if best_score is None or ranked > best_score:
            best_score = ranked
            best_key = key

    return best_key


def main() -> int:
    """CLI entry point: resolve one path against a Terraform route map."""
    if len(sys.argv) < 4:
        print("usage: expected_route_key.py <apigateway.tf> <method> <path> [prefix ...]", file=sys.stderr)
        return 2

    terraform_path, method, path = sys.argv[1], sys.argv[2], sys.argv[3]
    prefixes = sys.argv[4:]

    try:
        with open(terraform_path, encoding="utf-8") as handle:
            source = handle.read()
    except OSError:
        source = ""

    route_keys = declared_route_keys(source) + generated_route_keys(prefixes)
    resolved = resolve(path, method, route_keys)
    if not resolved:
        return 1

    print(resolved)
    return 0


if __name__ == "__main__":
    sys.exit(main())
