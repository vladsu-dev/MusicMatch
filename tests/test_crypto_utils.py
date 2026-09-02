# tests/test_crypto_utils.py
import pytest

from backend.crypto_utils import EncryptionConfigError, decrypt_token, encrypt_token


def test_encrypt_decrypt_roundtrip():
    original = 'super-secret-access-token'
    encrypted = encrypt_token(original)

    assert encrypted != original
    assert decrypt_token(encrypted) == original


def test_encrypt_rejects_empty_value():
    with pytest.raises(ValueError):
        encrypt_token('')


def test_missing_key_raises_config_error(monkeypatch):
    from backend.crypto_utils import _get_fernet

    monkeypatch.delenv('YANDEX_TOKEN_ENCRYPTION_KEY', raising=False)
    _get_fernet.cache_clear()

    with pytest.raises(EncryptionConfigError):
        encrypt_token('some-token')

    _get_fernet.cache_clear()


def test_decrypt_with_wrong_key_raises_config_error(monkeypatch):
    from cryptography.fernet import Fernet

    from backend.crypto_utils import _get_fernet

    encrypted = encrypt_token('some-token')

    # Меняем ключ шифрования "на лету" — имитация ситуации, когда токен
    # был зашифрован старым ключом, а сервис перезапустили с новым.
    monkeypatch.setenv('YANDEX_TOKEN_ENCRYPTION_KEY', Fernet.generate_key().decode())
    _get_fernet.cache_clear()

    with pytest.raises(EncryptionConfigError):
        decrypt_token(encrypted)
