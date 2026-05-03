"""
Profile rescrape_crawled_page_from_archive on a sample of pages.

Run from backend/:
    python scripts/profile_rescrape.py [--count 100] [--source <name>]

Picks N random pages with archived HTML, runs each one through the rescrape
path under cProfile, and prints the top hot functions by cumulative time.

This intentionally runs single-threaded so the profile reflects per-page CPU
breakdown without GIL noise. Each page is committed normally — re-runs
exercise the same code paths a real rescrape would.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import logging
import pstats
import random
import sys
import time
from pstats import SortKey

from sqlalchemy import or_, select

# bootstrap app imports
sys.path.insert(0, ".")

from app.api.models.crawled_page import CrawledPage as DBCrawledPage  # noqa: E402
from app.crawlers.archive_rescrape import rescrape_crawled_page_from_archive  # noqa: E402
from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

logger = logging.getLogger("profile_rescrape")
logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--source", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top", type=int, default=40, help="rows of pstats to print")
    args = parser.parse_args()

    random.seed(args.seed)

    db = SessionLocal()
    try:
        crawler_user = resolve_crawler_user(db)
        cat_id = resolve_default_category_id(db)

        stmt = select(DBCrawledPage).where(
            or_(
                DBCrawledPage.html_s3_key.isnot(None),
                DBCrawledPage.html_local_path.isnot(None),
            )
        )
        if args.source:
            stmt = stmt.where(DBCrawledPage.source == args.source)
        all_pages = db.scalars(stmt).all()
        if not all_pages:
            print("no archived pages found", file=sys.stderr)
            sys.exit(1)
        sample = random.sample(list(all_pages), min(args.count, len(all_pages)))
        print(f"profiling {len(sample)} page(s) of {len(all_pages)} archived total", file=sys.stderr)

        outcomes: dict[str, int] = {}
        durations: list[float] = []
        profiler = cProfile.Profile()

        profiler.enable()
        for i, page in enumerate(sample, 1):
            t0 = time.perf_counter()
            outcome, _, _ = rescrape_crawled_page_from_archive(
                db,
                page,
                crawler_user=crawler_user,
                default_category_id=cat_id,
                log=logger,
            )
            durations.append(time.perf_counter() - t0)
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
            if i % 10 == 0:
                print(f"  {i}/{len(sample)} done", file=sys.stderr)
        profiler.disable()

        # Summary stats
        total = sum(durations)
        durations.sort()
        n = len(durations)
        p50 = durations[n // 2]
        p95 = durations[min(n - 1, int(n * 0.95))]
        p99 = durations[min(n - 1, int(n * 0.99))]
        print(
            f"\nsamples={n} total={total:.2f}s mean={total/n*1000:.1f}ms "
            f"p50={p50*1000:.1f}ms p95={p95*1000:.1f}ms p99={p99*1000:.1f}ms",
            file=sys.stderr,
        )
        print(f"outcomes: {outcomes}", file=sys.stderr)

        # Top by cumulative time (full call chain weight)
        s = io.StringIO()
        pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE).print_stats(args.top)
        print("\n=== top by cumulative time ===")
        print(s.getvalue())

        # Top by tottime (where time is *actually* spent, excluding callees)
        s2 = io.StringIO()
        pstats.Stats(profiler, stream=s2).sort_stats(SortKey.TIME).print_stats(args.top)
        print("\n=== top by tottime (self-time, ex-callees) ===")
        print(s2.getvalue())
    finally:
        db.close()


if __name__ == "__main__":
    main()
