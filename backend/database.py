"""Движок базы данных и управление сессиями SQLAlchemy."""

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
    """Создаёт PostgreSQL-движок при первом реальном обращении к базе.

    Ленивое создание позволяет импортировать модели и запускать юнит-тесты
    без зависимости от драйвера PostgreSQL и локальной конфигурации базы.
    """
    global _engine
    if _engine is None:
        if not DB_PASSWORD:
            raise RuntimeError(
                "DB_PASSWORD обязателен. Скопируйте .env.template в .env и настройте учётные данные PostgreSQL."
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
    """Возвращает новую SQLAlchemy-сессию, привязанную к конфигурируемой базе."""
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
    """Создаёт отсутствующие таблицы для локальной разработки.

    Изменения схемы в production должны управляться через Alembic-миграции.
    """
    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())
