"""Admin crawler run, rescrape-archives, service-account endpoints (EventBridge-invokable per D-22)."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter()
