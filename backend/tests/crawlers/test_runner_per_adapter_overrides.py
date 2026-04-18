"""Unit tests for per-adapter delay/skip/category overrides in run_crawlers."""

from unittest.mock import patch
from uuid import uuid4

from app.crawlers import runner


def test_run_crawlers_passes_per_adapter_overrides() -> None:
    """run_crawlers should forward each adapter's own delay/skip/category to run_crawler."""
    cat_a = uuid4()
    cat_b = uuid4()
    fallback_cat = uuid4()

    captured: list[dict] = []

    def fake_run_crawler(name: str, **kwargs: object) -> dict:
        captured.append({"adapter": name, **kwargs})
        return {"adapter": name, "ingested": 0, "skipped": 0, "errors": 0, "total": 0}

    with patch.object(runner, "run_crawler", side_effect=fake_run_crawler):
        runner.run_crawlers(
            ["a90shop", "studiorsr"],
            parallel=False,
            delay_sec=2.5,
            delays={"a90shop": 7.5},
            skip_known_urls=False,
            skip_known_urls_by_adapter={"studiorsr": True},
            default_category_id=fallback_cat,
            default_category_ids={"a90shop": cat_a, "studiorsr": cat_b},
            limits={"a90shop": 10},
        )

    by_name = {c["adapter"]: c for c in captured}
    assert by_name["a90shop"]["delay_sec"] == 7.5
    assert by_name["a90shop"]["skip_known_urls"] is False
    assert by_name["a90shop"]["default_category_id"] == cat_a
    assert by_name["a90shop"]["limit"] == 10

    # studiorsr has no delays override — falls back to the singular default.
    assert by_name["studiorsr"]["delay_sec"] == 2.5
    assert by_name["studiorsr"]["skip_known_urls"] is True
    assert by_name["studiorsr"]["default_category_id"] == cat_b
    assert by_name["studiorsr"]["limit"] is None
