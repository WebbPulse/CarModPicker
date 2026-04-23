"""Admin canonical-parts management: lookup, link-group, promote, unlink, link, rescan."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()
