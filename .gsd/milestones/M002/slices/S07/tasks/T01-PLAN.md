---
estimated_steps: 1
estimated_files: 7
skills_used: []
---

# T01: Add part_price_alerts model + migration + Pydantic schemas

Foundation task. Create the SQLAlchemy ORM model `PartPriceAlert` for per-user subscriptions to per-part price thresholds, run an alembic autogenerate migration, add Pydantic schemas for create/read/update/list, and register the model in the package __init__ so future autogenerate runs see it. Schema fields: id (UUID, uuid7, PK), user_id (UUID FK→users.id, NOT NULL, indexed), part_id (UUID FK→parts.id, NOT NULL, indexed), threshold_cents (int, NOT NULL, CHECK threshold_cents >= 0 — enforced at Pydantic layer with ge=0), active (bool, default True, NOT NULL), last_fired_at (datetime, nullable), created_at (datetime, default now UTC), updated_at (datetime, default now UTC, onupdate now UTC). Add a UniqueConstraint('user_id', 'part_id', name='uq_part_price_alert_user_part') so a user can only have one alert per part — re-subscribing updates threshold instead of creating a duplicate. Pydantic schemas: `PartPriceAlertCreate(part_id: UUID, threshold_cents: int = Field(ge=0))`, `PartPriceAlertUpdate(threshold_cents: Optional[int] = None, active: Optional[bool] = None)`, `PartPriceAlertRead(id, user_id, part_id, threshold_cents, active, last_fired_at, created_at, updated_at)` with `model_config = ConfigDict(from_attributes=True)`. Run `cd backend && alembic revision --autogenerate -m 'add part_price_alerts'` per CLAUDE.md (NEVER hand-write migrations). Apply with `alembic upgrade head` against a fresh dev DB and confirm schema, then write a focused pytest file that asserts the unique constraint and CHECK behaviors. NOTE: pytest uses SQLite in-memory and creates schema via metadata, so the migration is exercised manually but the unit tests verify the Python-level model and constraints.

## Inputs

- ``backend/app/api/models/user.py``
- ``backend/app/api/models/part_listing.py``
- ``backend/app/api/models/part_price_history.py``
- ``backend/app/api/models/__init__.py``
- ``backend/app/api/schemas/part_price_history.py``

## Expected Output

- ``backend/app/api/models/part_price_alert.py``
- ``backend/app/api/schemas/part_price_alert.py``
- ``backend/app/api/models/__init__.py``
- ``backend/alembic/versions/<autogen>_add_part_price_alerts.py``
- ``backend/tests/models/test_part_price_alert.py``

## Verification

TESTING=true pytest backend/tests/models/test_part_price_alert.py -n auto --rootdir=backend -q --no-cov && cd backend && alembic upgrade head && alembic current

## Observability Impact

None at runtime — model-only task. Verification is the alembic current head check + the model unit tests.
