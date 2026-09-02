# backend/crypto_utils.py
"""
Утилиты для шифрования чувствительных данных (OAuth-токенов) перед
сохранением в базу данных.

Используется симметричное шифрование Fernet (AES-128-CBC + HMAC) из
библиотеки `cryptography`. Это НЕ хеширование (как для паролей) —
токены должны быть расшифровываемы, чтобы ими можно было пользоваться,
поэтому обязателен строгий контроль доступа к ключу.

Настройка:
    1. Сгенерируйте ключ:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    2. Положите его в переменную окружения YANDEX_TOKEN_ENCRYPTION_KEY
       (в .env локально, в секрет-менеджере — в production).
    3. НИКОГДА не коммитьте ключ в git и не логируйте его.
    4. При смене ключа все ранее сохранённые токены станут нерасшифрованными —
       пользователям потребуется подключить Яндекс.Музыку заново.
"""
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


class EncryptionConfigError(RuntimeError):
    """Ключ шифрования не задан, некорректен, либо данные повреждены/от другого ключа."""


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = os.getenv('YANDEX_TOKEN_ENCRYPTION_KEY')
    if not key:
        raise EncryptionConfigError(
            'YANDEX_TOKEN_ENCRYPTION_KEY не задан в окружении. Сгенерируйте ключ командой: '
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" '
            'и добавьте его в .env (файл не должен попадать в git).'
        )
    try:
        return Fernet(key.encode('utf-8'))
    except (ValueError, TypeError) as exc:
        raise EncryptionConfigError(f'Некорректный формат YANDEX_TOKEN_ENCRYPTION_KEY: {exc}') from exc


def encrypt_token(plain_text: str) -> str:
    """Шифрует строку (например, access_token) для хранения в БД."""
    if not plain_text:
        raise ValueError('Нельзя зашифровать пустое значение')
    return _get_fernet().encrypt(plain_text.encode('utf-8')).decode('utf-8')


def decrypt_token(cipher_text: str) -> str:
    """Расшифровывает строку, ранее полученную через encrypt_token()."""
    if not cipher_text:
        raise ValueError('Нельзя расшифровать пустое значение')
    try:
        return _get_fernet().decrypt(cipher_text.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise EncryptionConfigError(
            'Не удалось расшифровать токен: ключ шифрования изменился либо данные повреждены.'
        ) from exc
