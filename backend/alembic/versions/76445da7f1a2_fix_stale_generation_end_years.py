"""fix_stale_generation_end_years

Revision ID: 76445da7f1a2
Revises: f99b709f371a
Create Date: 2026-05-02 22:25:33.771976

Tier-1 generation end_year cleanup.

Conventions (per data audit, May 2026):
- Generation still in production -> end_year IS NULL.
- Discontinued -> end_year is the final US production model year (NOT NULL).
- Modern chassis-coded rows are canonical; numeric "Nth Gen" duplicates
  are folded into them.

This migration:
  1. Flips end_year to NULL for ~70 high-confidence still-in-production
     generations whose end_year was set to the audit-pull year (2024) or
     a single-year placeholder.
  2. Flips Toyota Supra A90 from end_year=2026 to NULL.
  3. Confirms Nissan GT-R R35 end_year=2024 (final US MY).
  4. Dedupes Acura MDX rows (numeric "Nth Gen" vs. chassis-coded YDx) by
     redirecting part_cars / build_lists to the chassis-coded row and
     deleting the numeric loser.
  5. Merges Tesla Model Y "1st Gen" (2020-2025) into "Juniper" (2025-NULL),
     final span 2020-NULL.
  6. Merges Lamborghini Urus "Urus" (base, 2018-2024) into "Performante"
     (2023-NULL), final span 2018-NULL.
  7. Inserts seven still-in-production generations (Ford F-150 15th, Audi
     S4 B10, Audi RS4 B10, Mini Cooper F66, Honda CR-V 6th, Toyota Camry
     XV80, Subaru Impreza 6th) where they don't yet exist.

All operations are guarded so re-runs are no-ops. INSERTs use Python-side
uuid.uuid4() (one per row) for SQLite-test compatibility; gen_random_uuid()
is Postgres-only and would also collide if used for multi-row INSERT...SELECT.
"""
from typing import Sequence, Union
import uuid

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '76445da7f1a2'
down_revision: Union[str, None] = 'ea29b2450841'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Generation IDs whose end_year is currently 2024 but should be NULL
# (still in production). Verified against the live DB on 2026-05-02. Audi
# A4 B9, S4 B9, RS4 B9 are intentionally NOT in this list: A4 B10 already
# exists, and we INSERT S4 B10 + RS4 B10 below, so those B9 rows stay
# closed at 2023.
STILL_IN_PRODUCTION_IDS = [
    '019da33b-caff-7935-a334-91a9c8e6b6d2',  # Subaru BRZ ZD8
    '019da33b-cc8f-76da-a807-45760cd01924',  # BMW M4 G82/G83
    '019da33b-cce5-76c1-b8bd-6ca2759ecd84',  # BMW M240i G42
    '019da33b-cb7a-7cbc-882d-c6a4efe85484',  # Mazda Miata ND
    '019da33b-cc7e-7994-b0a2-27a5b77120d8',  # BMW 3 Series G20/G21
    '019da33b-cbef-72c9-a0d7-f662d825d396',  # Ford F-150 Raptor 3rd Gen
    '019da33b-ca04-7f1b-a915-71b56eb38fe0',  # Honda Civic Type R FL5
    '019da33b-cc70-7321-8f60-2d6e0444f9bc',  # BMW M3 G80
    '019da33b-cceb-7cc8-8dd9-c2ed35a545a1',  # BMW M2 G87
    '019da33b-ccca-73b8-a243-26a8c6e55ed7',  # BMW M340i
    '019da33b-cf54-7e2a-9caf-bc7261983f55',  # Acura Integra 5th
    '019da33b-cc9e-7b23-beed-ff82b50a729e',  # BMW 2 Series G42
    '019da33b-cc8b-7f55-a5e1-da7e0d6297f8',  # BMW 330i
    '019da33b-d05b-7794-8001-d6a82932394f',  # Porsche 718 982
    '019da33b-cce0-7cd3-9b96-20606187ddfc',  # BMW M440i
    '019da33b-c9c0-787c-bcaf-a97f93672495',  # Honda Civic 11th
    '019da33b-ceb6-72bb-bfe9-f4510bc74ea2',  # VW Golf Mk8
    '019da33b-ced0-76f7-8eb6-b3c1d7fcc3e1',  # VW Golf R Mk8
    '019da33b-cec7-78aa-a3b6-994c2828aa5c',  # VW GTI Mk8
    '019da33b-cbe9-7262-9994-0770fd7c1561',  # Ford Bronco 6th
    '019da33b-cbc1-7341-aabc-87b1c63aac23',  # Ford Mustang 7th (was 2024-2024)
    '019da33b-d039-7d7d-9aba-f0252aaac785',  # Porsche 911 992
    '019da33b-cf7c-77de-b104-affa7f2da499',  # Acura TLX 2nd
    '019da33b-ccda-71b6-b6c9-d8b1b548760e',  # BMW 4 Series G22/G23/G26
    '019da33b-d10e-7201-aea9-ba3486941178',  # Genesis G70 RG
    '019da33b-cc2a-7a13-8fac-c126cdc6d7c5',  # Chevrolet Corvette C8
    '019da33b-cafa-7068-a347-271cdcf68750',  # Subaru WRX VB
    '019da33b-cb50-7fc2-bfa4-61773a45f288',  # Nissan Z RZ34
    '019da33b-cd65-710b-b439-250baa48d361',  # Audi A3 8Y
    '019da33b-cd73-7b92-a8be-94a8c61635be',  # Audi RS3 8Y
    '019da33b-cd6d-7e00-80c3-45e44262539b',  # Audi S3 8Y
    '019dae77-c566-7532-ab14-1de2f2100845',  # BMW X3 G01
    '019da38c-5455-796e-aaf7-390335d4e4b8',  # BMW X3 M F97
    '019dae77-c5a7-766d-ab39-278c10b36693',  # BMW i4 G26
    '019da33b-cd2f-7205-9fe7-1ce95423841d',  # BMW i4 M50 G26
    '019dae77-c56a-7e6e-a1c1-f61a18997a61',  # BMW X4 G02
    '019dae77-c575-7376-89d7-0e7edaf57283',  # BMW X5 G05
    '019dae77-c57b-7aa2-9473-986f19653e25',  # BMW X6 G06
    '019da33b-cd9e-771b-bd3b-beb3dbafc48b',  # Audi RS6 Avant C8
    '019da38c-5e7a-7504-ac5a-e79d7ba65f24',  # BMW X4 M F98
    '019dae77-c57d-7bbb-8b54-a2f758c0d2b3',  # BMW X7 G07
    '019da33b-d1ab-7833-94c7-bf9987a0c7c3',  # Ferrari 296 GTB
    '019dadac-048d-7fce-9e88-bc98872e09b5',  # Acura RDX TC1
    '019da33b-cd22-769b-837d-2493d30f1619',  # BMW X5 M F95
    '019da33b-cd2b-7b50-afb3-ea5474a6d096',  # BMW XM F95
    '019da33b-cdaa-72ba-bf48-cf5f6672670d',  # Audi RS Q8 4M
    '019da33b-cd29-76f6-82d8-9682e3897946',  # BMW X6 M F96
    '019da33b-d0a1-7cc7-a415-9f92b90964d2',  # Hyundai Elantra N CN7
    '019dae77-ca1d-71fa-bf4d-887e4285b6f8',  # Alfa Romeo Giulia 952
    '019dae77-c5a3-7aaa-adc0-5bff9a39503f',  # BMW 8 Series G14/G15/G16
    '019dae77-c580-7136-8adc-a801b453d2b6',  # BMW 2 Series Gran Coupe F44
    '019da33b-cd33-717a-b818-7b3b9c2efc2d',  # BMW i5 M60 G60 (was 2024-2024)
    '019dae77-c434-7746-a209-9a547572eab7',  # Ford Bronco Sport
    '019da33b-cb9b-739d-a14f-43f0ab41cfa4',  # Mazda Mazda3 BP
    '019dae77-c5a0-7c17-8d10-ca0c78679777',  # BMW 7 Series G70
    '019dae77-c4b0-7423-8e5d-99979573ba88',  # Cadillac Escalade T1
    '019dae77-c485-79f2-805e-69819ae53d3d',  # Chevrolet Silverado T1
    '019dae77-c493-7c65-a9af-3b21f19909c8',  # Chevrolet Suburban T1
    '019dae77-c48d-7690-bdbc-df25adf766cd',  # Chevrolet Tahoe T1
    '019dae77-c4bb-76de-8ad4-356904ce1b1b',  # GMC Sierra T1
    '019dae77-c4c3-733e-bf65-977277786d8c',  # GMC Yukon T1
    '019dae77-c360-7655-b7bd-dd22f3eeb8da',  # Subaru Ascent 1st
    '019da33b-cd04-74ec-8282-3fa8dbf5aad6',  # BMW M8 F91/F92/F93
    '019da33b-cda7-77dd-966c-e0b1458749aa',  # Audi RS Q3 F3
    '019dae77-c431-780d-9f7c-4b6356fa9a27',  # Ford Maverick 1st
    '019da33b-d0aa-76d4-aaef-ef4c963bbc4e',  # Hyundai Ioniq 5 N NE (was 2024-2024)
    '019da33b-cda2-7217-8c49-0ad4cc107e9e',  # Audi RS7 Sportback C8
    '019da33b-cd36-7b05-bb52-bcf16a88d036',  # BMW i7 M70 G70
    '019dae77-c4a3-7195-aca6-c582d36b85f4',  # Cadillac CT4-V Blackwing
    '019da33b-d11d-74f0-ab37-a990de7999cd',  # Genesis GV70 JK1
]

# Single-year (start=end=2024) gens that should be open-ended; matched by
# (make, model, generation_name, start_year=2024, end_year=2024) so re-runs
# are safe.
SINGLE_YEAR_2024_FLIPS = [
    # (make, model, generation_name)
    ('Aston Martin', 'Valhalla', 'Valhalla'),
    ('Aston Martin', 'Vanquish', 'Vanquish'),  # 2001 + 2012 + 2024 rows; only the 2024 row matches start=end=2024
    ('Audi', 'SQ5', 'FYS'),
    ('Dodge', 'Charger', '2024+'),
    ('Ford', 'Ranger', 'Next Gen'),
    ('Ford', 'Ranger Raptor', '1st Gen'),
    ('Lexus', 'GX', 'J250'),
    ('Porsche', 'Cayenne', 'PO536 (Facelift)'),
    ('Porsche', 'Macan', 'PO536 (Electric)'),
    ('Porsche', 'Panamera', '971 (Facelift)'),
]

# New still-in-production generations to insert.
# (make, model, generation_name, slug, start_year, car_model_id)
NEW_OPEN_ENDED_GENS = [
    ('Ford', 'F-150', '15th Gen', '15th-gen', 2024, '019dad99-1b43-7544-af46-27a12c3cec90'),
    ('Audi', 'S4', 'B10', 'b10', 2024, '019da33b-cd46-759e-90ab-988e142b4d1b'),
    ('Audi', 'RS4', 'B10', 'b10', 2024, '019da33b-cd7b-7eeb-baf6-bba14202deae'),
    ('Mini', 'Cooper', 'F66', 'f66', 2024, '019dada5-7cd5-7f6f-85c1-16995f77d843'),
    ('Honda', 'CR-V', '6th Gen', '6th-gen', 2023, '019dadab-9d6c-7df3-913a-4cc5f81043a3'),
    ('Toyota', 'Camry', 'XV80', 'xv80', 2025, '019da33b-ca3a-71aa-beb5-2a4f54b21f3e'),
    ('Subaru', 'Impreza', '6th Gen', '6th-gen', 2024, '019da33b-cafd-7ea0-bfc6-644c4b99cbf7'),
]

# Acura MDX dedup pairs: (loser_id, canonical_id, label_for_logging)
# Canonical chosen by part_cars count (audited 2026-05-02); ties broken by
# preferring the chassis-coded YDx row (modern naming convention).
MDX_DEDUP_PAIRS = [
    ('019da33b-cf60-7aa1-a66b-6f0517d57884',
     '019dadac-0670-732a-8fe8-305dd083a25e',
     '1st Gen -> YD1'),
    ('019da33b-cf61-75ec-b565-e8b6ca8ad104',
     '019dadac-0671-7255-a845-2d111d4bbf99',
     '2nd Gen -> YD2'),
    ('019da33b-cf62-77ab-a6cf-44557fee11a4',
     '019dadac-0672-75e7-9ea7-908f634beb84',
     '3rd Gen -> YD3'),
    ('019da33b-cf63-7a66-bb5a-f01d39a91929',
     '019dadac-0673-753a-a174-803265555fca',
     '4th Gen -> YD4'),
]

TOYOTA_SUPRA_A90_ID = '019da33b-ca59-7603-8f41-5caa50e82258'
NISSAN_GTR_R35_ID = '019da33b-cb4a-782e-b0f8-398db624a814'

TESLA_MODEL_Y_1ST_GEN_ID = '019da38c-abda-7f68-9287-a142fd820298'
TESLA_MODEL_Y_JUNIPER_ID = '019da38c-abdb-7208-ad40-d379e38eebd7'

LAMBO_URUS_BASE_ID = '019da33b-d151-7aff-92cc-590569d8ec2f'
LAMBO_URUS_PERFORMANTE_ID = '019da33b-d152-7b5a-acfd-f8a3a7838f6f'


def _id_match_clause(column: str, dialect_name: str) -> str:
    """Return a SQL fragment matching a uuid column against a string param.

    Postgres stores uuids natively so we cast to text. SQLite stores them as
    strings already, so a direct equality works.
    """
    if dialect_name == 'postgresql':
        return f"{column}::text = :id"
    return f"{column} = :id"


def _redirect_and_delete(conn, loser_id: str, canonical_id: str) -> None:
    """Move part_cars + build_lists from loser to canonical, then delete loser.

    Avoids duplicate-key collisions on part_cars (same part_id + canonical
    car_id) by skipping rows that would conflict, then dropping leftovers.
    """
    dialect = conn.dialect.name

    # part_cars: redirect rows on the loser, but only when an equivalent
    # (part_id, canonical_id) row doesn't already exist.
    if dialect == 'postgresql':
        conn.execute(
            sa.text("""
                UPDATE part_cars
                SET car_id = CAST(:canonical AS uuid)
                WHERE car_id::text = :loser
                  AND NOT EXISTS (
                      SELECT 1 FROM part_cars pc2
                      WHERE pc2.part_id = part_cars.part_id
                        AND pc2.car_id::text = :canonical
                  )
            """),
            {'loser': loser_id, 'canonical': canonical_id},
        )
        conn.execute(
            sa.text("DELETE FROM part_cars WHERE car_id::text = :loser"),
            {'loser': loser_id},
        )
        conn.execute(
            sa.text("""
                UPDATE build_lists
                SET car_id = CAST(:canonical AS uuid)
                WHERE car_id::text = :loser
            """),
            {'loser': loser_id, 'canonical': canonical_id},
        )
        conn.execute(
            sa.text("DELETE FROM car_generations WHERE id::text = :loser"),
            {'loser': loser_id},
        )
    else:
        conn.execute(
            sa.text("""
                UPDATE part_cars
                SET car_id = :canonical
                WHERE car_id = :loser
                  AND NOT EXISTS (
                      SELECT 1 FROM part_cars pc2
                      WHERE pc2.part_id = part_cars.part_id
                        AND pc2.car_id = :canonical
                  )
            """),
            {'loser': loser_id, 'canonical': canonical_id},
        )
        conn.execute(
            sa.text("DELETE FROM part_cars WHERE car_id = :loser"),
            {'loser': loser_id},
        )
        conn.execute(
            sa.text("UPDATE build_lists SET car_id = :canonical WHERE car_id = :loser"),
            {'loser': loser_id, 'canonical': canonical_id},
        )
        conn.execute(
            sa.text("DELETE FROM car_generations WHERE id = :loser"),
            {'loser': loser_id},
        )


def _row_exists(conn, table: str, id_value: str) -> bool:
    dialect = conn.dialect.name
    sql = f"SELECT 1 FROM {table} WHERE {_id_match_clause('id', dialect)} LIMIT 1"
    return conn.execute(sa.text(sql), {'id': id_value}).first() is not None


def _row_columns(conn, table: str, id_value: str, columns: str):
    dialect = conn.dialect.name
    sql = f"SELECT {columns} FROM {table} WHERE {_id_match_clause('id', dialect)} LIMIT 1"
    return conn.execute(sa.text(sql), {'id': id_value}).first()


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # 1. Bulk flip stale end_year=2024 -> NULL for still-in-production rows.
    #    Guard: only touch rows whose end_year is NOT NULL (idempotent).
    for gen_id in STILL_IN_PRODUCTION_IDS:
        sql = (
            f"UPDATE car_generations SET end_year = NULL, "
            f"updated_at = CURRENT_TIMESTAMP "
            f"WHERE {_id_match_clause('id', dialect)} AND end_year IS NOT NULL"
        )
        conn.execute(sa.text(sql), {'id': gen_id})

    # 2. Toyota Supra A90: was end_year=2026, flip to NULL (still in production).
    sql = (
        f"UPDATE car_generations SET end_year = NULL, "
        f"updated_at = CURRENT_TIMESTAMP "
        f"WHERE {_id_match_clause('id', dialect)} AND end_year IS NOT NULL"
    )
    conn.execute(sa.text(sql), {'id': TOYOTA_SUPRA_A90_ID})

    # 3. Nissan GT-R R35: confirm end_year=2024 (final US production MY).
    sql = (
        f"UPDATE car_generations SET end_year = 2024, "
        f"updated_at = CURRENT_TIMESTAMP "
        f"WHERE {_id_match_clause('id', dialect)} "
        f"AND (end_year IS NULL OR end_year <> 2024)"
    )
    conn.execute(sa.text(sql), {'id': NISSAN_GTR_R35_ID})

    # 4. Single-year recent gens (start=end=2024) -> NULL. Match by name to
    #    avoid touching unintended rows; double-guard on start_year=2024 AND
    #    end_year=2024 so re-runs on already-flipped data are no-ops, and
    #    historical same-named rows (e.g. Vanquish 2001-2007, 2012-2018)
    #    don't get hit.
    for make, model, gen_name in SINGLE_YEAR_2024_FLIPS:
        conn.execute(
            sa.text("""
                UPDATE car_generations
                SET end_year = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT g.id
                    FROM car_generations g
                    JOIN car_models m ON m.id = g.car_model_id
                    JOIN car_makes mk ON mk.id = m.car_make_id
                    WHERE mk.name = :make
                      AND m.name = :model
                      AND g.generation_name = :gen_name
                      AND g.start_year = 2024
                      AND g.end_year = 2024
                )
            """),
            {'make': make, 'model': model, 'gen_name': gen_name},
        )

    # 5. Acura MDX dedup. Each pair: redirect part_cars + build_lists from
    #    the numeric "Nth Gen" row into the chassis-coded "YDx" row, then
    #    delete the numeric row. Guarded by existence check.
    for loser_id, canonical_id, _label in MDX_DEDUP_PAIRS:
        if (_row_exists(conn, 'car_generations', loser_id)
                and _row_exists(conn, 'car_generations', canonical_id)):
            _redirect_and_delete(conn, loser_id, canonical_id)

    # 6a. Tesla Model Y: merge "1st Gen" (2020-2025) into "Juniper" (2025-NULL).
    #     Final span: 2020-NULL on the Juniper row.
    if (_row_exists(conn, 'car_generations', TESLA_MODEL_Y_1ST_GEN_ID)
            and _row_exists(conn, 'car_generations', TESLA_MODEL_Y_JUNIPER_ID)):
        _redirect_and_delete(
            conn, TESLA_MODEL_Y_1ST_GEN_ID, TESLA_MODEL_Y_JUNIPER_ID
        )
        sql = (
            f"UPDATE car_generations SET start_year = 2020, end_year = NULL, "
            f"updated_at = CURRENT_TIMESTAMP "
            f"WHERE {_id_match_clause('id', dialect)} "
            f"AND (start_year <> 2020 OR end_year IS NOT NULL)"
        )
        conn.execute(sa.text(sql), {'id': TESLA_MODEL_Y_JUNIPER_ID})

    # 6b. Lamborghini Urus: merge base into Performante. Sanity-guard on
    #     the verified pattern (base 2018-2024, Performante 2023-NULL).
    base_row = _row_columns(
        conn, 'car_generations', LAMBO_URUS_BASE_ID, 'start_year, end_year'
    )
    perf_row = _row_columns(
        conn, 'car_generations', LAMBO_URUS_PERFORMANTE_ID, 'start_year, end_year'
    )
    if (base_row and perf_row
            and base_row[0] == 2018 and base_row[1] == 2024
            and perf_row[1] is None):
        _redirect_and_delete(
            conn, LAMBO_URUS_BASE_ID, LAMBO_URUS_PERFORMANTE_ID
        )
        sql = (
            f"UPDATE car_generations SET start_year = 2018, end_year = NULL, "
            f"updated_at = CURRENT_TIMESTAMP "
            f"WHERE {_id_match_clause('id', dialect)} AND start_year <> 2018"
        )
        conn.execute(sa.text(sql), {'id': LAMBO_URUS_PERFORMANTE_ID})

    # 7. INSERT new still-in-production generations where missing.
    #    Match key: (car_model_id, slug). Skip if already present.
    #
    #    car_model_id is resolved at runtime by (make, model) rather than
    #    trusting the hardcoded UUID in NEW_OPEN_ENDED_GENS: those UUIDs
    #    only exist if the app's car-seed had already run, but migrations
    #    execute before app startup, so on a forward-migrating prod DB the
    #    hardcoded id has no matching car_models row and the INSERT used to
    #    fail with a ForeignKeyViolation (rolling back every deploy). If the
    #    model can't be resolved we skip the row — it will be created by the
    #    app's idempotent car seed on startup instead.
    for _make, _model, gen_name, slug, start_year, _hardcoded_id in NEW_OPEN_ENDED_GENS:
        model_row = conn.execute(
            sa.text("""
                SELECT m.id
                FROM car_models m
                JOIN car_makes mk ON mk.id = m.car_make_id
                WHERE mk.name = :make AND m.name = :model
                LIMIT 1
            """),
            {'make': _make, 'model': _model},
        ).first()
        if model_row is None:
            # Model not seeded yet at migration time — app startup seed
            # will create both the model and this generation.
            continue
        car_model_id = str(model_row[0])
        if dialect == 'postgresql':
            existing_sql = (
                "SELECT 1 FROM car_generations "
                "WHERE car_model_id::text = :model_id AND slug = :slug LIMIT 1"
            )
        else:
            existing_sql = (
                "SELECT 1 FROM car_generations "
                "WHERE car_model_id = :model_id AND slug = :slug LIMIT 1"
            )
        existing = conn.execute(
            sa.text(existing_sql),
            {'model_id': car_model_id, 'slug': slug},
        ).first()
        if existing:
            continue
        new_id = str(uuid.uuid4())
        if dialect == 'postgresql':
            insert_sql = """
                INSERT INTO car_generations
                    (id, car_model_id, generation_name, slug,
                     start_year, end_year, created_at, updated_at)
                VALUES
                    (CAST(:id AS uuid), CAST(:model_id AS uuid),
                     :gen_name, :slug,
                     :start_year, NULL,
                     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        else:
            insert_sql = """
                INSERT INTO car_generations
                    (id, car_model_id, generation_name, slug,
                     start_year, end_year, created_at, updated_at)
                VALUES
                    (:id, :model_id, :gen_name, :slug,
                     :start_year, NULL,
                     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        conn.execute(
            sa.text(insert_sql),
            {
                'id': new_id,
                'model_id': car_model_id,
                'gen_name': gen_name,
                'slug': slug,
                'start_year': start_year,
            },
        )


def downgrade() -> None:
    # Forward-only data migration: reversing risks resurrecting stale or
    # deleted-and-redirected references. Per project convention for
    # data-only migrations (see afdf25556c6c), git-revert the PR if
    # functional rollback is needed.
    pass
