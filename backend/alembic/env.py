import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

from alembic import context

# Add the app directory to Python path so we can import app modules
sys.path.insert(0, "/app")

# Load .env file variables into environment
# Assumes .env is in the project root (one level up from alembic dir)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


from app.db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Get the database URL from the environment variable
# Use DATABASE_URL, fallback to the value in alembic.ini
DATABASE_URL = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")

# Log database connection info (without exposing credentials)
if DATABASE_URL:
    # Parse URL to log connection info safely
    try:
        from urllib.parse import urlparse

        parsed = urlparse(DATABASE_URL)
        db_info = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 'default'}/{parsed.path.split('/')[-1] if parsed.path else 'default'}"
        import logging

        logging.getLogger("alembic").info(f"Connecting to database: {db_info}")
    except Exception:
        pass  # Don't fail if logging fails

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set, and sqlalchemy.url is not configured in alembic.ini"
    )


config.set_main_option("sqlalchemy.url", DATABASE_URL)


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


def run_migrations_offline() -> None:

    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Use NullPool for migrations to avoid connection pool issues
    # Add connect_args for better Railway compatibility
    connectable = create_engine(
        str(DATABASE_URL),
        poolclass=pool.NullPool,
        connect_args={
            "connect_timeout": 10,  # 10 second connection timeout
            "options": "-c statement_timeout=30000",  # 30 second statement timeout
        },
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
