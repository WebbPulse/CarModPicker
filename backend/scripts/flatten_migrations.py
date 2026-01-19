#!/usr/bin/env python3
"""
Script to flatten Alembic migrations into a new baseline.

This script:
1. Creates a new baseline migration from the current models
2. Archives old migrations to a backup directory
3. Provides instructions for updating the database

WARNING: This will remove all existing migration history.
Only use this if you're sure you want to start fresh.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get the backend directory (parent of scripts)
BACKEND_DIR = Path(__file__).parent.parent
ALEMBIC_DIR = BACKEND_DIR / "alembic"
VERSIONS_DIR = ALEMBIC_DIR / "versions"
ARCHIVE_DIR = ALEMBIC_DIR / "versions_archive"


def main():
    print("=" * 60)
    print("Alembic Migration Flattening Script")
    print("=" * 60)
    print()
    print("WARNING: This will:")
    print("  1. Create a new baseline migration")
    print("  2. Archive all existing migrations")
    print("  3. You'll need to manually update your database")
    print()

    response = input("Are you sure you want to proceed? (yes/no): ")
    if response.lower() != "yes":
        print("Aborted.")
        return

    # Step 1: Create archive directory
    print("\n[1/4] Creating archive directory...")
    if ARCHIVE_DIR.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ARCHIVE_DIR.rename(ARCHIVE_DIR.parent / f"versions_archive_{timestamp}")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"   Archive directory: {ARCHIVE_DIR}")

    # Step 2: Archive existing migrations
    print("\n[2/4] Archiving existing migrations...")
    migration_files = list(VERSIONS_DIR.glob("*.py"))
    if not migration_files:
        print("   No existing migrations found.")
    else:
        for migration_file in migration_files:
            shutil.move(str(migration_file), str(ARCHIVE_DIR / migration_file.name))
            print(f"   Archived: {migration_file.name}")
        print(f"   Archived {len(migration_files)} migration files")

    # Step 3: Clear alembic_version table (if database is accessible)
    print("\n[3/5] Clearing alembic_version table...")
    os.chdir(BACKEND_DIR)

    try:
        # Try to directly update the database's alembic_version table
        # This avoids needing the migration files that we just archived
        from dotenv import load_dotenv
        from sqlalchemy import create_engine, text

        # Load environment variables
        dotenv_path = BACKEND_DIR / ".env"
        if dotenv_path.exists():
            load_dotenv(dotenv_path)

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment")

        # Create engine and clear the alembic_version table
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.begin() as conn:  # begin() handles transaction automatically
            # Try to delete all rows from alembic_version table
            # If table doesn't exist, this will raise an exception which we'll catch
            result = conn.execute(text("DELETE FROM alembic_version"))
            rows_deleted = result.rowcount
            if rows_deleted > 0:
                print(f"   ✓ Cleared alembic_version table (removed {rows_deleted} row(s))")
            else:
                print("   ✓ alembic_version table is empty")

        engine.dispose()
    except Exception as e:
        # If database is not accessible, that's okay - we'll proceed anyway
        # The user will need to manually update the database later
        print(f"   ⚠ Could not clear alembic_version table: {str(e)}")
        print("   This is okay - you'll need to manually update the database later")
        print("   You can run: DELETE FROM alembic_version; (or DROP TABLE alembic_version;)")

    # Step 4: Create new baseline migration
    print("\n[4/5] Creating new baseline migration...")

    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", "baseline_schema"],
            check=True,
            capture_output=True,
            text=True,
        )
        print("   ✓ Baseline migration created successfully")
        if result.stdout.strip():
            print(f"   Output: {result.stdout}")

        # Find the newly created migration file
        new_migrations = [f for f in VERSIONS_DIR.glob("*.py") if f not in ARCHIVE_DIR.glob("*.py")]
        if new_migrations:
            new_migration = new_migrations[0]
            print(f"   New migration file: {new_migration.name}")

            # Read and modify the migration to set it as a baseline
            content = new_migration.read_text()
            # Remove any actual revision ID that might have been set
            import re

            content = re.sub(
                r'down_revision: Union\[str, None\] = "[^"]+"',
                "down_revision: Union[str, None] = None  # Baseline migration",
                content,
            )
            # Also handle the case where it might be set to None already but we want to ensure it
            if "down_revision: Union[str, None] = None" not in content:
                content = re.sub(
                    r"down_revision: Union\[str, None\] = .+",
                    "down_revision: Union[str, None] = None  # Baseline migration",
                    content,
                )
            new_migration.write_text(content)
            print("   ✓ Migration set as baseline (down_revision = None)")
        else:
            print("   ⚠ Warning: Could not find newly created migration file")
    except subprocess.CalledProcessError as e:
        print(f"   ✗ Error creating migration: {e.stderr}")
        print("\n   Restoring archived migrations...")
        for migration_file in ARCHIVE_DIR.glob("*.py"):
            shutil.move(str(migration_file), str(VERSIONS_DIR / migration_file.name))
        print("   Restored. Please fix the issue and try again.")
        return

    # Step 5: Instructions
    print("\n[5/5] Next steps:")
    print("=" * 60)
    print("IMPORTANT: You need to manually update your database!")
    print()
    print("Option A - For a fresh database (no existing data):")
    print("  1. Drop and recreate your database")
    print("  2. Run: alembic upgrade head")
    print()
    print("Option B - For an existing database (with data):")
    print("  1. Connect to your database")
    print("  2. Update the alembic_version table:")
    print("     UPDATE alembic_version SET version_num = '<new_revision_id>';")
    print("     (Replace <new_revision_id> with the revision ID from the new migration)")
    print("  3. Or delete the alembic_version table and let Alembic recreate it:")
    print("     DROP TABLE alembic_version;")
    print("     alembic stamp head")
    print()
    print("Option C - For production (safest):")
    print("  1. Backup your database first!")
    print("  2. Follow Option B steps")
    print("  3. Test thoroughly before deploying")
    print()
    print(f"Archived migrations are in: {ARCHIVE_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
