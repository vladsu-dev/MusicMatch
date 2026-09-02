# database/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем параметры подключения из переменных окружения
DB_USER = os.getenv('DB_USER', 'user')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'musicmatch')
DB_PORT = os.getenv('DB_PORT', '5432')

# Создаем URL для подключения
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаем движок
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Показывать SQL запросы (для разработки)
    pool_size=10,
    max_overflow=20
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

# Функция для получения сессии
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Функция для создания всех таблиц
def init_db():
    # Импортируем модели здесь, чтобы избежать циклического импорта
    from backend import models  # noqa: F401
    Base.metadata.create_all(bind=engine)