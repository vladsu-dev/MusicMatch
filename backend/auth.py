# backend/auth.py
from backend.database import SessionLocal
from backend.models import User
import bcrypt
from datetime import datetime, timezone


def hash_password(password: str) -> str:
    """Хеширует пароль с помощью bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль"""
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )
    except Exception:
        return False


def register_user(username: str, email: str, password: str,
                  gender: str, age: int = None, bio: str = '') -> dict:
    """Регистрирует нового пользователя"""
    db = SessionLocal()
    try:
        # Проверяем, существует ли пользователь
        existing_user = db.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing_user:
            if existing_user.email == email:
                return {'success': False, 'error': 'Email уже зарегистрирован'}
            else:
                return {'success': False, 'error': 'Имя пользователя занято'}

        # Создаем нового пользователя
        new_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            gender=gender,
            age=age,
            bio=bio
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return {
            'success': True,
            'user_id': new_user.id
        }
    except Exception as e:
        db.rollback()
        return {'success': False, 'error': f'Ошибка: {str(e)}'}
    finally:
        db.close()


def login_user(email: str, password: str) -> dict:
    """Аутентифицирует пользователя"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()

        if not user:
            return {'success': False, 'error': 'Пользователь не найден'}

        if not verify_password(password, user.password_hash):
            return {'success': False, 'error': 'Неверный пароль'}

        return {
            'success': True,
            'user_id': user.id
        }
    except Exception as e:
        return {'success': False, 'error': f'Ошибка: {str(e)}'}
    finally:
        db.close()


def get_user_by_id(user_id: int) -> User:
    """Получает пользователя по ID"""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()