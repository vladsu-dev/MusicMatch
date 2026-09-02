# tests/conftest.py
"""
Общие фикстуры для тестов.

Тесты используют SQLite in-memory вместо PostgreSQL — это специально:
цель этих тестов — проверить бизнес-логику интеграции с Яндекс.Музыкой
(backend/yandex_music_service.py), а не саму СУБД. Для интеграционных
тестов против реального PostgreSQL см. docs/YANDEX_MUSIC_INTEGRATION.md
(раздел "Тестирование").
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
# Импорт models обязателен, чтобы все таблицы зарегистрировались в Base.metadata
from backend import models  # noqa: F401
from backend.crypto_utils import _get_fernet


@pytest.fixture()
def db_session():
    """Чистая in-memory SQLite база на каждый тест."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    """Задаёт тестовый ключ шифрования и сбрасывает lru_cache между тестами,
    чтобы тесты не зависели друг от друга и от реального .env."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv('YANDEX_TOKEN_ENCRYPTION_KEY', Fernet.generate_key().decode())
    _get_fernet.cache_clear()
    yield
    _get_fernet.cache_clear()


@pytest.fixture()
def user_factory(db_session):
    """Быстро создаёт пользователя MusicMatch для тестов."""
    from backend.models import User

    def _make(username='tester', email='tester@example.com'):
        user = User(
            username=username,
            email=email,
            password_hash='not-a-real-hash',
            gender='other',
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make
