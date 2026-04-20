import logging
import time
from typing import Generator

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Retry config for serverless/DB cold start: wait for DB to become ready
_DB_RETRY_ATTEMPTS = 5
_DB_RETRY_DELAY_SEC = 0.3

# Get settings using the function (which could be overridden in tests)
settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Enable connection health checks
    pool_recycle=3600,  # Recycle connections after 1 hour
    # Defaults (5 / 10) get exhausted when many parallel crawler threads each
    # hold a session during ingest — API endpoints (and the cancel endpoint)
    # then block waiting for a connection and the whole backend appears hung.
    pool_size=20,
    max_overflow=30,
)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _is_connection_error(exc: BaseException) -> bool:
    """True if the exception indicates DB unreachable (cold start, network, etc.)."""
    if isinstance(exc, (OperationalError, InterfaceError)):
        return True
    if isinstance(exc, DBAPIError) and exc.orig is not None:
        return _is_connection_error(exc.orig)
    return False


def get_db() -> Generator[Session, None, None]:
    db: Session | None = None
    last_error: BaseException | None = None
    for attempt in range(1, _DB_RETRY_ATTEMPTS + 1):
        try:
            db = SessionLocal()
            break
        except Exception as e:
            last_error = e
            if _is_connection_error(e) and attempt < _DB_RETRY_ATTEMPTS:
                logger.warning(
                    "Database connection failed (attempt %s/%s), retrying in %ss: %s",
                    attempt,
                    _DB_RETRY_ATTEMPTS,
                    _DB_RETRY_DELAY_SEC,
                    e,
                )
                time.sleep(_DB_RETRY_DELAY_SEC)
            else:
                if _is_connection_error(e):
                    logger.warning(
                        "Database unavailable after %s attempts: %s",
                        _DB_RETRY_ATTEMPTS,
                        e,
                    )
                    raise HTTPException(
                        status_code=503,
                        detail="Service temporarily unavailable; database is starting. Please retry.",
                        headers={"Retry-After": "2"},
                    ) from e
                raise
    if db is None:
        assert last_error is not None
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable; database is starting. Please retry.",
            headers={"Retry-After": "2"},
        ) from last_error
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_ready() -> bool:
    """Return True if the database is reachable (for /ready)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
