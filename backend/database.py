"""Database engine and SQLAlchemy session management."""

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DB_USER = os.getenv("DB_USER", "musicmatch")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "musicmatch")
DB_PORT = os.getenv("DB_PORT", "5432")

_engine = None
_session_factory = None


def get_engine():
    """Create the PostgreSQL engine on first real database use.

    Lazy initialization keeps model-only imports and unit tests independent of
    the PostgreSQL driver and of a developer's local database configuration.
    """
    global _engine
    if _engine is None:
        if not DB_PASSWORD:
            raise RuntimeError(
                "DB_PASSWORD is required. Copy .env.template to .env and configure PostgreSQL credentials."
            )

        database_url = (
            f"postgresql+psycopg://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
            f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        _engine = create_engine(
            database_url,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            pool_pre_ping=True,
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
        )
    return _engine


def SessionLocal():
    """Return a new SQLAlchemy session bound to the configured database."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _session_factory()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create missing tables for local development.

    Production schema changes should be managed with Alembic migrations.
    """
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
