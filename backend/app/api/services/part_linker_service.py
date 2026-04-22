"""
Canonical part linker.

Every scrape/user-create produces its own Part row. This service decides whether
that row should be linked (via ``Part.canonical_part_id``) to an existing canonical
that represents the same real-world product, and handles re-election when the new
part has richer metadata than the existing canonical.

Linking model:
- ``canonical_part_id IS NULL`` → the part is itself a canonical (may have siblings
  pointing at it, or be a singleton).
- ``canonical_part_id IS NOT NULL`` → the part is a duplicate; the referenced part
  is the surface representation. The tree is always depth-1 (no chains).

The read path surfaces only canonicals; ``PartListing``/``PartPriceHistory`` from
siblings are aggregated onto the canonical at read time.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.part import Part as DBPart
from app.api.services.part_listing_service import (
    find_part_by_gtin,
    find_part_by_part_manufacturer_and_part_number,
    find_part_by_product_url,
    normalize_gtin,
    normalize_part_number,
)

logger = logging.getLogger(__name__)


# Heuristic weights for canonical election. Richer metadata wins; ties broken by
# earliest created_at (see _score_tuple).
_SCORE_GTIN = 3
_SCORE_PART_NUMBER = 2
_SCORE_IMAGE = 1
_MAX_IMAGE_SCORE = 5
_SCORE_DESCRIPTION = 1
_DESCRIPTION_MIN_LEN = 40
_SCORE_CATEGORY = 1
_SCORE_VERIFIED = 4  # admin-verified parts should almost always stay canonical


def score_metadata_richness(part: DBPart) -> int:
    """Integer score used to compare parts when electing a canonical. Higher wins."""
    score = 0
    if normalize_gtin(part.gtin):
        score += _SCORE_GTIN
    if normalize_part_number(part.part_number):
        score += _SCORE_PART_NUMBER
    images = part.image_urls or []
    score += min(len(images), _MAX_IMAGE_SCORE) * _SCORE_IMAGE
    if part.description and len(part.description.strip()) >= _DESCRIPTION_MIN_LEN:
        score += _SCORE_DESCRIPTION
    if part.category_id is not None:
        score += _SCORE_CATEGORY
    if part.is_verified:
        score += _SCORE_VERIFIED
    return score


def _score_tuple(part: DBPart) -> tuple[int, float]:
    """(richness desc, created_at asc) — higher-richness wins, older wins on ties."""
    created_ts = part.created_at.timestamp() if part.created_at else float("inf")
    # Return a tuple where "greater" means "should be canonical": negate created_ts
    # so earlier (smaller timestamp) is greater.
    return (score_metadata_richness(part), -created_ts)


def find_canonical_candidates(
    db: Session,
    *,
    gtin: Optional[str] = None,
    product_url: Optional[str] = None,
    part_manufacturer_id: Optional[UUID] = None,
    part_number: Optional[str] = None,
    exclude_part_id: Optional[UUID] = None,
) -> list[DBPart]:
    """
    Find distinct canonical parts (``canonical_part_id IS NULL``) matching any of
    the provided dedup keys.

    Returns canonicals only; the underlying lookups in ``part_listing_service``
    filter out non-canonicals (and ``source == "user_created"`` UGC rows by
    default) so the linker never recommends a duplicate — or a UGC row — as a
    merge target. UGC is fully isolated from the scraped dedup graph.
    """
    candidates: dict[UUID, DBPart] = {}

    if gtin and normalize_gtin(gtin):
        hit = find_part_by_gtin(db, gtin)
        if hit and (exclude_part_id is None or hit.id != exclude_part_id):
            candidates[hit.id] = hit

    if product_url and product_url.strip():
        hit = find_part_by_product_url(db, product_url)
        if hit is not None:
            # find_part_by_product_url returns any non-UGC part; resolve to its
            # canonical so the linker never recommends a duplicate as a merge target.
            if hit.canonical_part_id is not None:
                canonical = db.get(DBPart, hit.canonical_part_id)
                if canonical is not None:
                    hit = canonical
            if exclude_part_id is None or hit.id != exclude_part_id:
                candidates[hit.id] = hit

    if part_manufacturer_id and part_number and str(part_number).strip():
        hit = find_part_by_part_manufacturer_and_part_number(db, part_manufacturer_id, str(part_number))
        if hit and (exclude_part_id is None or hit.id != exclude_part_id):
            candidates[hit.id] = hit

    # Belt-and-suspenders: even if a helper ever returns a UGC row, drop it here
    # so a scraped part can never elect a user-contributed canonical.
    return [c for c in candidates.values() if c.source != "user_created"]


def _point_siblings_at(db: Session, old_canonical_id: UUID, new_canonical_id: UUID) -> int:
    """Repoint every part currently linked to ``old_canonical_id`` onto ``new_canonical_id``."""
    rows = list(
        db.scalars(select(DBPart).where(DBPart.canonical_part_id == old_canonical_id)).all()
    )
    for row in rows:
        row.canonical_part_id = new_canonical_id
        db.add(row)
    return len(rows)


def reelect_canonical(db: Session, new_canonical: DBPart) -> DBPart:
    """
    Make ``new_canonical`` the canonical of its link group.

    Safe to call whether ``new_canonical`` is currently canonical or a sibling —
    at minimum it clears ``canonical_part_id`` and repoints any existing siblings.
    """
    # IN-03: lock subject row FIRST, then re-read canonical_part_id under the lock
    # before taking the early-return branch. The previous ordering read
    # canonical_part_id off the passed-in ORM object (possibly stale) and returned
    # early without any lock, so a concurrent link_new_part that was mid-flight
    # setting new_canonical.canonical_part_id could leave this call with a
    # "return value is canonical" contract violation. Under the subject-row lock
    # the re-read is consistent with anything about to mutate it.
    # Silent no-op on SQLite (Pitfall 1); concurrency guarantees hold on Postgres.
    locked_subject = db.scalars(
        select(DBPart).where(DBPart.id == new_canonical.id).with_for_update()
    ).one_or_none()
    if locked_subject is None:
        # Row vanished (delete race). Fall back to returning the passed-in object;
        # callers treat this as an already-canonical no-op.
        return new_canonical
    # Rebind to the freshly-locked row so subsequent mutations see consistent state.
    new_canonical = locked_subject

    if new_canonical.canonical_part_id is None:
        # Already canonical; nothing to do unless callers want to repoint other
        # groups into this one, which they should do via link_new_part.
        return new_canonical

    # DATA-03 (Phase 4 D-01/D-05): lock new_canonical + old_canonical + all siblings
    # before reading/mutating. Siblings are discovered under the lock to freeze the
    # set against a concurrent link_new_part that might be adding a new sibling.
    # Silent no-op on SQLite (Pitfall 1); concurrency test runs on Postgres.
    #
    # Phase 4 code-review WR-02: sort lock_ids before WHERE id IN (...) so that
    # concurrent reelect_canonical / link_new_part calls acquire row locks in a
    # deterministic (by-id) order. Without this, two transactions locking
    # overlapping row sets in different orders can deadlock under index-dependent
    # SQL lock acquisition.
    old_canonical_id = new_canonical.canonical_part_id
    lock_ids_set: set[UUID] = {new_canonical.id, old_canonical_id}
    sibling_ids = db.scalars(
        select(DBPart.id)
        .where(DBPart.canonical_part_id == old_canonical_id)
        .with_for_update()
    ).all()
    lock_ids_set.update(sibling_ids)
    lock_ids = sorted(lock_ids_set)
    db.scalars(
        select(DBPart).where(DBPart.id.in_(lock_ids)).with_for_update()
    ).all()

    old_canonical = db.get(DBPart, old_canonical_id)

    new_canonical.canonical_part_id = None
    db.add(new_canonical)

    if old_canonical is not None:
        old_canonical.canonical_part_id = new_canonical.id
        db.add(old_canonical)

    moved = _point_siblings_at(db, old_canonical_id, new_canonical.id)
    # Guard against self-reference that could happen during the mutation above.
    if new_canonical.canonical_part_id == new_canonical.id:
        new_canonical.canonical_part_id = None
        db.add(new_canonical)

    db.flush()
    logger.info(
        "Re-elected canonical: new=%s old=%s siblings_moved=%d",
        new_canonical.id,
        old_canonical_id,
        moved,
    )
    return new_canonical


def unlink_part(db: Session, part: DBPart) -> DBPart:
    """Make ``part`` its own canonical, detaching it from its current link group.

    DATA-03 (Phase 4 D-01/D-05) lock scope: subject + canonical (if any) + siblings.
    The full sibling set must be locked so that a concurrent reelect_canonical
    cannot read subject.canonical_part_id as non-null and then mutate a stale
    sibling view. The invariant to preserve: every sibling's canonical_part_id
    resolves to a live Part row with canonical_part_id IS NULL.
    Silent no-op on SQLite (Pitfall 1); concurrency test runs on Postgres.
    """
    # Lock the subject row first (stable ordering — subject.id is always in set).
    subject = db.scalars(
        select(DBPart).where(DBPart.id == part.id).with_for_update()
    ).one()

    canonical_id = subject.canonical_part_id
    if canonical_id is None:
        return subject

    # Lock the canonical row.
    db.scalars(
        select(DBPart).where(DBPart.id == canonical_id).with_for_update()
    ).one()

    # Lock every sibling that shares this canonical so any interleaving with
    # reelect_canonical / _point_siblings_at / another unlink serializes here.
    db.scalars(
        select(DBPart.id)
        .where(DBPart.canonical_part_id == canonical_id)
        .with_for_update()
    ).all()

    # Now safe to mutate.
    subject.canonical_part_id = None
    db.add(subject)
    db.flush()
    logger.info("Unlinked part %s from prior canonical", subject.id)
    return subject


def link_new_part(
    db: Session,
    new_part: DBPart,
    *,
    product_url: Optional[str] = None,
) -> DBPart:
    """
    After a new Part row is created, try to link it to an existing canonical.

    Strategy:
    - Find canonical candidates using GTIN / URL / manufacturer+part_number.
    - 0 candidates → ``new_part`` stays canonical (``canonical_part_id = NULL``).
    - 1+ candidates → pick the richest among ``{candidates ∪ new_part}`` as canonical.
      If multiple candidates exist (former ``PART_DEDUP_CONFLICT``), their link
      groups are merged under the chosen canonical.

    Returns the canonical of the resulting link group (may be ``new_part`` itself
    or an existing part).
    """
    candidates = find_canonical_candidates(
        db,
        gtin=new_part.gtin,
        product_url=product_url,
        part_manufacturer_id=new_part.part_manufacturer_id,
        part_number=new_part.part_number,
        exclude_part_id=new_part.id,
    )

    if not candidates:
        logger.debug("Linker: no canonical candidates for part %s; leaving canonical", new_part.id)
        return new_part

    # DATA-03 (Phase 4 D-01/D-05): lock every candidate + new_part so concurrent
    # link_new_part calls serialize on these rows. Re-reads the latest state in
    # case the candidates lookup was stale. Silent no-op on SQLite (Pitfall 1) —
    # concurrency test (test_part_linker_concurrency.py) runs on Postgres.
    #
    # Phase 4 code-review WR-02: sort lock_ids so overlapping link_new_part /
    # reelect_canonical transactions acquire row locks in the same deterministic
    # order and cannot deadlock on index-dependent lock acquisition.
    lock_ids = sorted({c.id for c in candidates} | {new_part.id})
    locked = db.scalars(
        select(DBPart)
        .where(DBPart.id.in_(lock_ids))
        .with_for_update()
    ).all()
    locked_by_id = {p.id: p for p in locked}
    candidates = [locked_by_id[c.id] for c in candidates]
    new_part = locked_by_id[new_part.id]

    all_candidates = candidates + [new_part]
    chosen = max(all_candidates, key=_score_tuple)

    if len(candidates) > 1:
        logger.info(
            "Linker: merging link groups for part %s (candidates=%s chosen=%s)",
            new_part.id,
            [c.id for c in candidates],
            chosen.id,
        )

    if chosen is new_part:
        # New part wins; every candidate (each was a canonical) becomes a sibling of new_part.
        for cand in candidates:
            old_canonical_id = cand.id
            cand.canonical_part_id = new_part.id
            db.add(cand)
            _point_siblings_at(db, old_canonical_id, new_part.id)
        db.flush()
        logger.info(
            "Linker: part %s elected canonical over %d existing canonical(s)",
            new_part.id,
            len(candidates),
        )
        return new_part

    # Existing candidate wins. Link new_part under it, and if there were other
    # candidates (conflict case), fold their groups into chosen.
    new_part.canonical_part_id = chosen.id
    db.add(new_part)
    for cand in candidates:
        if cand.id == chosen.id:
            continue
        old_canonical_id = cand.id
        cand.canonical_part_id = chosen.id
        db.add(cand)
        _point_siblings_at(db, old_canonical_id, chosen.id)
    db.flush()
    logger.info("Linker: part %s linked to existing canonical %s", new_part.id, chosen.id)
    return chosen


def resolve_canonical(db: Session, part_id: UUID) -> Optional[DBPart]:
    """Return the canonical part for ``part_id`` (itself if already canonical)."""
    part = db.get(DBPart, part_id)
    if part is None:
        return None
    if part.canonical_part_id is None:
        return part
    canonical = db.get(DBPart, part.canonical_part_id)
    return canonical or part


def link_group_part_ids(db: Session, part_id: UUID) -> list[UUID]:
    """
    Return every Part ID that is part of the same link group as ``part_id``.

    Used by read paths that aggregate listings/price history across siblings
    onto a canonical. Returns ``[part_id]`` if the part is a singleton or does
    not exist, the canonical + its duplicates if ``part_id`` is canonical, or
    the canonical + all its duplicates (including ``part_id``) if it is one.
    """
    part = db.get(DBPart, part_id)
    if part is None:
        return [part_id]
    canonical_id = part.canonical_part_id or part.id
    sibling_ids = list(
        db.scalars(select(DBPart.id).where(DBPart.canonical_part_id == canonical_id)).all()
    )
    return [canonical_id, *sibling_ids]
