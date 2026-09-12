"""Tests for the route key resolver.

The cases are the gateway decisions observed in the staging access log, so a
change that breaks agreement with API Gateway fails here rather than in a
deploy.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from expected_route_key import declared_route_keys, generated_route_keys, resolve

ROUTE_KEYS = [
    "ANY /api/votes",
    "ANY /api/votes/{proxy+}",
    "ANY /api/reports",
    "ANY /api/reports/{proxy+}",
    "ANY /api/bug-reports",
    "ANY /api/bug-reports/{proxy+}",
    "GET /api/reports/{report_id}",
    "PUT /api/reports/{report_id}",
    "DELETE /api/reports/{report_id}",
    "GET /api/bug-reports/{bug_report_id}",
    "GET /api/reports/count",
    "GET /api/reports/my-reports",
    "GET /api/votes/admin/flagged/{entity_type}",
    "POST /api/votes/{entity_type}/{entity_id}",
]


def test_bare_prefix_resolves_to_the_bare_key():
    assert resolve("/api/votes", "GET", ROUTE_KEYS) == "ANY /api/votes"


def test_unclaimed_child_falls_to_proxy():
    assert resolve("/api/votes/probe", "GET", ROUTE_KEYS) == "ANY /api/votes/{proxy+}"


def test_single_segment_variable_beats_proxy():
    assert resolve("/api/reports/probe", "GET", ROUTE_KEYS) == "GET /api/reports/{report_id}"
    assert resolve("/api/bug-reports/probe", "GET", ROUTE_KEYS) == "GET /api/bug-reports/{bug_report_id}"


def test_literal_beats_variable():
    assert resolve("/api/reports/count", "GET", ROUTE_KEYS) == "GET /api/reports/count"
    assert resolve("/api/reports/my-reports", "GET", ROUTE_KEYS) == "GET /api/reports/my-reports"


def test_method_is_respected():
    assert resolve("/api/reports/probe", "POST", ROUTE_KEYS) == "ANY /api/reports/{proxy+}"


def test_deeper_path_falls_to_proxy():
    assert resolve("/api/reports/probe/deeper", "GET", ROUTE_KEYS) == "ANY /api/reports/{proxy+}"


def test_deep_literal_variable_key_wins():
    assert resolve("/api/votes/admin/flagged/part", "GET", ROUTE_KEYS) == "GET /api/votes/admin/flagged/{entity_type}"


def test_unmatched_path_resolves_to_nothing():
    assert resolve("/api/nothing-here", "GET", ROUTE_KEYS) == ""


def test_declared_route_keys_reads_terraform_literals():
    source = '''
      "GET /api/reports/{report_id}"   = { integration = "moderation" }
      "POST /api/votes/{entity_type}/{entity_id}" = { integration = "moderation" }
    '''
    assert declared_route_keys(source) == [
        "GET /api/reports/{report_id}",
        "POST /api/votes/{entity_type}/{entity_id}",
    ]


def test_generated_route_keys_pairs_every_prefix():
    assert generated_route_keys(["/api/votes"]) == ["ANY /api/votes", "ANY /api/votes/{proxy+}"]
