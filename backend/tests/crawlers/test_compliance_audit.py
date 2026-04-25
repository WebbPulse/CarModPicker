"""M002/S03/T03: pin the ``compliance_audit`` script's stdout contract.

Three tests cover the audit module's two terminal branches (all-compliant /
non-compliant) and the per-tier breakdown contract that S04's admin endpoint
will scrape.

- ``test_audit_passes_when_all_compliant`` — happy path: ``audit()`` returns 0
  and stdout reports the current count compliant.
- ``test_audit_per_tier_breakdown_in_stdout`` — guards the per-tier columns
  the M002 closer / S04 admin endpoint depend on.
- ``test_audit_reports_offenders_when_non_compliant`` — patches the
  ``ADAPTER_REGISTRY`` *at the import site inside the audit module* (per
  MEM017) with a small fixture mixing one good adapter and one stub-bad
  adapter; asserts return code 1 plus the ``Non-compliant adapters:`` block
  with the bad adapter's slug.

Per MEM025: the bad-adapter fixture uses ``types.SimpleNamespace`` rather
than declaring an ad-hoc ``RetailerCrawlerAdapter`` subclass, since the
latter would trip ``__init_subclass__``'s non-empty ``ADAPTER_NAME`` check
and pollute global state across worker processes.
"""

from __future__ import annotations

import types

import pytest

from app.crawlers import compliance_audit
from app.crawlers.adapters import ADAPTER_REGISTRY


def test_audit_passes_when_all_compliant(capsys: pytest.CaptureFixture[str]) -> None:
    """``audit()`` returns 0 and reports ``<n>/<n> compliant`` when every adapter is compliant."""
    rc = compliance_audit.audit()
    captured = capsys.readouterr()

    assert rc == 0, f"audit() exit code drift: got {rc}\nstdout:\n{captured.out}"
    total = len(ADAPTER_REGISTRY)
    expected_total_line = f"Total:        {total}/{total} compliant"
    assert expected_total_line in captured.out, (
        f"Expected {expected_total_line!r} in audit stdout; got:\n{captured.out}"
    )
    assert "OK — every adapter declares at least one category_targets entry" in captured.out


def test_audit_per_tier_breakdown_in_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    """Per-tier breakdown rows are present (S04 admin endpoint scrapes these)."""
    rc = compliance_audit.audit()
    captured = capsys.readouterr()

    assert rc == 0
    for marker in ("T0 (http):", "T1 (tls):", "T2 (browser):"):
        assert captured.out.count(marker) == 1, (
            f"Expected exactly one occurrence of {marker!r} in audit stdout; "
            f"got {captured.out.count(marker)}.\nstdout:\n{captured.out}"
        )


def test_audit_reports_offenders_when_non_compliant(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Non-compliant fixture → exit 1 + ``Non-compliant adapters:`` block names the offender."""
    # SimpleNamespace stand-in (per MEM025) — avoids __init_subclass__ side
    # effects from declaring a real RetailerCrawlerAdapter subclass in tests.
    good = types.SimpleNamespace(
        FETCHER_TIER="http",
        category_targets=["universal"],
    )
    bad = types.SimpleNamespace(
        FETCHER_TIER="http",
        category_targets=[],  # the offense under test
    )
    fake_registry = {
        "_t03_good_adapter": good,
        "_t03_bad_adapter": bad,
    }

    # Per MEM017: patch the bound name inside compliance_audit (the import
    # site), not the source module — Python resolves the name at the call
    # site and the audit reads ``compliance_audit.ADAPTER_REGISTRY``.
    monkeypatch.setattr(compliance_audit, "ADAPTER_REGISTRY", fake_registry)

    rc = compliance_audit.audit()
    captured = capsys.readouterr()

    assert rc == 1, f"Expected exit 1 with non-compliant fixture; got {rc}"
    assert "Non-compliant adapters:" in captured.out
    assert "_t03_bad_adapter" in captured.out
    # The compliant adapter must NOT appear in the offenders block.
    offenders_block = captured.out.split("M002/S03 adapter compliance audit", 1)[0]
    assert "_t03_good_adapter" not in offenders_block, (
        f"Compliant adapter leaked into offenders block:\n{offenders_block}"
    )
    # Total line should reflect the patched registry (1/2 compliant).
    assert "Total:        1/2 compliant" in captured.out
