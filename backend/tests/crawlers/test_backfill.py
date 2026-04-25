"""Tests for the re-extraction backfill CLI (M002/S04/T01).

Covers:
  - Selection filter (only NULL or empty-dict specifications)
  - Dry-run makes no writes
  - Idempotent second run processes zero parts
  - Resume cursor advances the SELECT
  - Above-threshold failure rate exits 2
  - --source filter restricts to one adapter
  - Argparse rejects malformed --batch-size and --max-failure-rate

Patches always target the import site
(``app.crawlers.backfill.rescrape_crawled_page_from_archive``) per MEM011 /
MEM017 — Python resolves bound names at the call site, so patching the
source module after import is a no-op.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.models.category import Category as DBCategory
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.crawlers import backfill


@pytest.fixture()
def cli_state_dir(tmp_path: Path) -> Path:
    """Per-test directory for the resume cursor file."""
    state = tmp_path / "crawler-state"
    state.mkdir()
    return state


@pytest.fixture()
def patched_session_factory(
    db_session: Session, engine: Engine
) -> Generator[None, None, None]:
    """Patch ``backfill.SessionLocal`` to mint sessions on the test connection.

    The CLI opens its own session per batch (and a bootstrap session for the
    crawler-user/category lookups). Each of those sessions must see — and be
    isolated by — the same outer transaction the test fixture controls.
    Binding via ``join_transaction_mode='create_savepoint'`` against the same
    connection lets the CLI commit freely while keeping the rollback at the
    test boundary.
    """
    Factory = sessionmaker(
        bind=db_session.connection(),
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    with patch.object(backfill, "SessionLocal", Factory):
        yield


@pytest.fixture()
def crawler_user(db_session: Session) -> DBUser:
    """Service-account crawler user — resolve_crawler_user() picks the first non-disabled service account."""
    user = DBUser(
        id=uuid4(),
        username=f"svc-{uuid4().hex[:8]}",
        email=f"svc-{uuid4().hex[:8]}@example.test",
        hashed_password="x",
        email_verified=True,
        is_service_account=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def default_category(db_session: Session) -> DBCategory:
    """Active category that resolve_default_category_id() will fall through to."""
    cat = DBCategory(
        id=uuid4(),
        name=f"cat-{uuid4().hex[:8]}",
        display_name="Test Cat",
        is_active=True,
        sort_order=1,
    )
    db_session.add(cat)
    db_session.commit()
    return cat


def _make_part(
    db: Session,
    *,
    user_id,
    category_id,
    name: str,
    specifications=None,
) -> DBPart:
    part = DBPart(
        name=name,
        category_id=category_id,
        user_id=user_id,
        specifications=specifications,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return part


def _make_crawled_page(
    db: Session,
    *,
    part_id,
    source: str = "stub_adapter",
    url_suffix: str | None = None,
    parse_status: str = "parsed",
) -> DBCrawledPage:
    page = DBCrawledPage(
        url=f"https://example.test/{url_suffix or uuid4().hex}",
        source=source,
        html_local_path="/tmp/never-read.html",  # stubbed rescrape never reads it
        parse_status=parse_status,
        last_parsed_at=datetime.now(timezone.utc),
        part_id=part_id,
    )
    db.add(page)
    db.commit()
    return page


# ----------------------------- selection filter -----------------------------


def test_select_only_parts_with_empty_specifications(
    db_session: Session,
    crawler_user: DBUser,
    default_category: DBCategory,
) -> None:
    """The SELECT returns only parts whose specifications is NULL or '{}'."""
    p_null = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="null-specs",
        specifications=None,
    )
    p_empty = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="empty-specs",
        specifications={},
    )
    p_full = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="full-specs",
        specifications={"weight_grams": 100, "weight_grams_confidence": "high"},
    )
    for p in (p_null, p_empty, p_full):
        _make_crawled_page(db_session, part_id=p.id)

    ids = backfill._select_candidate_part_ids(
        db_session,
        batch_size=10,
        after_part_id=None,
        source=None,
        remaining_limit=None,
    )

    assert set(ids) == {p_null.id, p_empty.id}
    assert p_full.id not in ids


# ----------------------------- dry-run makes no writes ----------------------


def test_dry_run_makes_no_writes(
    db_session: Session,
    crawler_user: DBUser,
    default_category: DBCategory,
    patched_session_factory,
    cli_state_dir: Path,
) -> None:
    """--dry-run counts but never invokes rescrape and never updates Parts."""
    p1 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="dry-1",
        specifications=None,
    )
    p2 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="dry-2",
        specifications={},
    )
    page1 = _make_crawled_page(db_session, part_id=p1.id, url_suffix="dry-1")
    page2 = _make_crawled_page(db_session, part_id=p2.id, url_suffix="dry-2")
    p1_orig_specs = p1.specifications
    p2_orig_specs = p2.specifications
    page1_orig_parsed = page1.last_parsed_at
    page2_orig_parsed = page2.last_parsed_at

    rescrape_calls: list = []

    def _stub_rescrape(*args, **kwargs):
        rescrape_calls.append(args)
        return ("parsed_ok", uuid4(), None)

    with patch.object(backfill, "rescrape_crawled_page_from_archive", _stub_rescrape):
        rc = backfill.main(
            argv=[
                "--dry-run",
                "--state-dir",
                str(cli_state_dir),
                "--batch-size",
                "10",
            ]
        )

    assert rc == 0
    assert rescrape_calls == [], "dry-run must not call rescrape"

    db_session.expire_all()
    refreshed_p1 = db_session.get(DBPart, p1.id)
    refreshed_p2 = db_session.get(DBPart, p2.id)
    refreshed_page1 = db_session.get(DBCrawledPage, page1.id)
    refreshed_page2 = db_session.get(DBCrawledPage, page2.id)
    assert refreshed_p1.specifications == p1_orig_specs
    assert refreshed_p2.specifications == p2_orig_specs
    assert refreshed_page1.last_parsed_at == page1_orig_parsed
    assert refreshed_page2.last_parsed_at == page2_orig_parsed
    # Cursor file is NOT written on dry-run.
    assert not (cli_state_dir / backfill.CURSOR_FILENAME).exists()


# ----------------------------- idempotency ----------------------------------


def test_idempotent_second_run_processes_zero_parts(
    db_session: Session,
    crawler_user: DBUser,
    default_category: DBCategory,
    patched_session_factory,
    cli_state_dir: Path,
) -> None:
    """Once a part has populated specs, the next run's SELECT skips it."""
    p1 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="idem",
        specifications=None,
    )
    _make_crawled_page(db_session, part_id=p1.id, url_suffix="idem")

    populated_specs = {"weight_grams": 1.0, "weight_grams_confidence": "high"}

    def _stub_rescrape(db, page, **kwargs):
        # Simulate the universal-extractor wiring populating specs on the part.
        part = db.get(DBPart, page.part_id)
        part.specifications = populated_specs
        db.add(part)
        db.commit()
        return ("parsed_ok", part.id, None)

    with patch.object(backfill, "rescrape_crawled_page_from_archive", _stub_rescrape):
        rc1 = backfill.main(
            argv=["--state-dir", str(cli_state_dir), "--batch-size", "10"]
        )
    assert rc1 == 0

    db_session.expire_all()
    assert db_session.get(DBPart, p1.id).specifications == populated_specs

    second_calls: list = []

    def _stub_rescrape_second(*args, **kwargs):
        second_calls.append(args)
        return ("parsed_ok", uuid4(), None)

    with patch.object(backfill, "rescrape_crawled_page_from_archive", _stub_rescrape_second):
        rc2 = backfill.main(
            argv=["--state-dir", str(cli_state_dir), "--batch-size", "10"]
        )
    assert rc2 == 0
    assert second_calls == [], "second run must not invoke rescrape — specs already populated"


# ----------------------------- resume cursor --------------------------------


def test_resume_starts_from_cursor(
    db_session: Session,
    crawler_user: DBUser,
    default_category: DBCategory,
    patched_session_factory,
    cli_state_dir: Path,
) -> None:
    """--resume reads the cursor file and skips parts whose id <= cursor."""
    p1 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="resume-1",
        specifications=None,
    )
    p2 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="resume-2",
        specifications=None,
    )
    p3 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="resume-3",
        specifications=None,
    )
    # uuid7 is monotonic, so id1 < id2 < id3 by creation order. Sort to confirm.
    ordered = sorted([p1, p2, p3], key=lambda p: p.id)
    earliest, middle, latest = ordered
    for p in (earliest, middle, latest):
        _make_crawled_page(db_session, part_id=p.id, url_suffix=str(p.id))

    cursor_path = cli_state_dir / backfill.CURSOR_FILENAME
    cursor_path.write_text(json.dumps({"last_processed_part_id": str(earliest.id)}))

    touched_part_ids: list = []

    def _stub_rescrape(db, page, **kwargs):
        touched_part_ids.append(page.part_id)
        part = db.get(DBPart, page.part_id)
        part.specifications = {"weight_grams": 1.0, "weight_grams_confidence": "high"}
        db.add(part)
        db.commit()
        return ("parsed_ok", part.id, None)

    with patch.object(backfill, "rescrape_crawled_page_from_archive", _stub_rescrape):
        rc = backfill.main(
            argv=[
                "--resume",
                "--state-dir",
                str(cli_state_dir),
                "--batch-size",
                "10",
            ]
        )

    assert rc == 0
    assert touched_part_ids == [middle.id, latest.id]


# ----------------------------- failure-rate exit 2 --------------------------


def test_above_threshold_failure_rate_exits_2(
    db_session: Session,
    crawler_user: DBUser,
    default_category: DBCategory,
    patched_session_factory,
    cli_state_dir: Path,
) -> None:
    """All-failures run with default 0.5 threshold returns exit code 2."""
    p1 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="fail-1",
        specifications=None,
    )
    p2 = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="fail-2",
        specifications=None,
    )
    _make_crawled_page(db_session, part_id=p1.id, url_suffix="fail-1")
    _make_crawled_page(db_session, part_id=p2.id, url_suffix="fail-2")

    def _stub_rescrape(*args, **kwargs):
        return ("parse_failed", None, "stub error")

    with patch.object(backfill, "rescrape_crawled_page_from_archive", _stub_rescrape):
        rc = backfill.main(
            argv=["--state-dir", str(cli_state_dir), "--batch-size", "10"]
        )

    assert rc == 2


# ----------------------------- --source filter ------------------------------


def test_source_filter_restricts_adapter(
    db_session: Session,
    crawler_user: DBUser,
    default_category: DBCategory,
    patched_session_factory,
    cli_state_dir: Path,
) -> None:
    """--source <adapter> only touches crawled_pages with that source."""
    p_a = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="source-a",
        specifications=None,
    )
    p_b = _make_part(
        db_session,
        user_id=crawler_user.id,
        category_id=default_category.id,
        name="source-b",
        specifications=None,
    )
    _make_crawled_page(db_session, part_id=p_a.id, source="adapter_a", url_suffix="src-a")
    _make_crawled_page(db_session, part_id=p_b.id, source="adapter_b", url_suffix="src-b")

    touched: list = []

    def _stub_rescrape(db, page, **kwargs):
        touched.append(page.source)
        part = db.get(DBPart, page.part_id)
        part.specifications = {"weight_grams": 1.0, "weight_grams_confidence": "high"}
        db.add(part)
        db.commit()
        return ("parsed_ok", part.id, None)

    with patch.object(backfill, "rescrape_crawled_page_from_archive", _stub_rescrape):
        rc = backfill.main(
            argv=[
                "--source",
                "adapter_a",
                "--state-dir",
                str(cli_state_dir),
                "--batch-size",
                "10",
            ]
        )

    assert rc == 0
    assert touched == ["adapter_a"], f"only adapter_a pages should be touched, got {touched}"


# ----------------------------- argparse negatives ---------------------------


def test_argparse_rejects_invalid_batch_size(cli_state_dir: Path) -> None:
    """--batch-size 0 fails fast with SystemExit code 2 (argparse error)."""
    with pytest.raises(SystemExit) as excinfo:
        backfill.main(
            argv=["--batch-size", "0", "--state-dir", str(cli_state_dir)]
        )
    assert excinfo.value.code == 2


def test_argparse_rejects_negative_batch_size(cli_state_dir: Path) -> None:
    """--batch-size -1 also fails fast."""
    with pytest.raises(SystemExit) as excinfo:
        backfill.main(
            argv=["--batch-size", "-1", "--state-dir", str(cli_state_dir)]
        )
    assert excinfo.value.code == 2


def test_argparse_rejects_invalid_failure_rate(cli_state_dir: Path) -> None:
    """--max-failure-rate 1.5 must be in [0, 1]; argparse exits 2."""
    with pytest.raises(SystemExit) as excinfo:
        backfill.main(
            argv=["--max-failure-rate", "1.5", "--state-dir", str(cli_state_dir)]
        )
    assert excinfo.value.code == 2
