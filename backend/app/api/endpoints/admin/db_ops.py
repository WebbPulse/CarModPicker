"""Admin database operations: migrations, data init, bulk delete."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()
