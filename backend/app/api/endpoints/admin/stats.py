"""Admin statistics endpoints (table counts, crawl bucket listing)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()
