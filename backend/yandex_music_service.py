# backend/yandex_music_service.py
"""
Сервис синхронизации любимых исполнителей пользователя из Яндекс.Музыки
в его профиль MusicMatch.

Это единственное место, где бизнес-логика приложения соприкасается с
конкретным провайдером (YandexMusicProvider). Если в будущем добавится
второй провайдер (например, Spotify), для него нужно будет реализовать
MusicProviderClient и написать аналогичный сервис с тем же публичным
интерфейсом — sync_favorite_artists(...).
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.crypto_utils import EncryptionConfigError, decrypt_token, encrypt_token
from backend.models import Artist, User, YandexMusicAccount
from backend.music_providers.base import ProviderToken
from backend.music_providers.yandex_music_provider import (
    YandexMusicAuthError,
    YandexMusicProvider,
    YandexMusicProviderError,
)

logger = logging.getLogger(__name__)

# Не дёргаем Yandex API чаще этого интервала на одного пользователя.
# Одновременно служит и простым кэшем результата, и rate limiter'ом
# на случай, если фронтенд вызовет /sync повторно по ошибке или полёту руки пользователя.
MIN_SYNC_INTERVAL = timedelta(minutes=5)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _proxy_url() -> Optional[str]:
    return os.getenv('YANDEX_MUSIC_PROXY_URL')


def save_token(db: Session, user_id: int, token: ProviderToken) -> YandexMusicAccount:
    """Сохраняет (или обновляет) OAuth-токен пользователя в зашифрованном виде.
    Токен НИКОГДА не логируется и не возвращается в открытом виде наружу."""
    account = db.query(YandexMusicAccount).filter_by(user_id=user_id).first()
    is_new = account is None
    if is_new:
        account = YandexMusicAccount(user_id=user_id)
        db.add(account)

    account.access_token_encrypted = encrypt_token(token.access_token)
    account.refresh_token_encrypted = (
        encrypt_token(token.refresh_token) if token.refresh_token else None
    )
    account.token_type = token.token_type
    account.expires_at = (
        _utcnow() + timedelta(seconds=token.expires_in) if token.expires_in else None
    )
    if is_new:
        account.connected_at = _utcnow()

    db.commit()
    db.refresh(account)
    logger.info('Яндекс.Музыка подключена для user_id=%s', user_id)
    return account


def get_connection_status(db: Session, user_id: int) -> dict:
    account = db.query(YandexMusicAccount).filter_by(user_id=user_id).first()
    if not account:
        return {'connected': False}
    return {
        'connected': True,
        'connected_at': account.connected_at.isoformat() if account.connected_at else None,
        'last_synced_at': account.last_synced_at.isoformat() if account.last_synced_at else None,
        'last_sync_status': account.last_sync_status,
    }


def disconnect(db: Session, user_id: int) -> bool:
    """Отключает интеграцию: удаляет сохранённый (зашифрованный) токен пользователя."""
    account = db.query(YandexMusicAccount).filter_by(user_id=user_id).first()
    if not account:
        return False
    db.delete(account)
    db.commit()
    logger.info('Яндекс.Музыка отключена для user_id=%s', user_id)
    return True


def _fetch_artists_with_retry(
    provider: YandexMusicProvider,
    access_token: str,
    attempts: int = 3,
    base_delay: float = 1.5,
    max_delay: float = 10.0,
):
    """
    Повторяет запрос при временных сбоях (YandexMusicProviderError), но
    НЕ повторяет при YandexMusicAuthError — невалидный/истёкший токен не
    починится сам собой, повторные попытки только зря нагрузят API и
    задержат ответ пользователю. Поэтому не используется общий
    backend/retry.py decorator (он не различает подтипы исключений).
    """
    delay = base_delay
    last_exc: Optional[YandexMusicProviderError] = None
    for attempt in range(1, attempts + 1):
        try:
            return provider.get_favorite_artists(access_token)
        except YandexMusicAuthError:
            raise
        except YandexMusicProviderError as exc:
            last_exc = exc
            if attempt == attempts:
                break
            logger.warning(
                'Синхронизация с Яндекс.Музыкой: попытка %s/%s не удалась (%s), повтор через %.1fс',
                attempt, attempts, exc, delay,
            )
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
    raise last_exc


def sync_favorite_artists(db: Session, user_id: int, force: bool = False) -> dict:
    """
    Забирает любимых исполнителей из Яндекс.Музыки и добавляет их в
    `User.favorite_artists`. Возвращает словарь, готовый к отдаче как JSON
    из Flask-эндпоинта.
    """
    account = db.query(YandexMusicAccount).filter_by(user_id=user_id).first()
    if not account:
        return {'success': False, 'error': 'Яндекс.Музыка не подключена', 'code': 'not_connected'}

    if not force and account.last_synced_at:
        elapsed = _utcnow() - account.last_synced_at
        if elapsed < MIN_SYNC_INTERVAL:
            retry_after = int((MIN_SYNC_INTERVAL - elapsed).total_seconds())
            return {
                'success': True,
                'skipped': True,
                'reason': 'Синхронизация недавно уже выполнялась',
                'retry_after_seconds': retry_after,
                'last_synced_at': account.last_synced_at.isoformat(),
            }

    try:
        access_token = decrypt_token(account.access_token_encrypted)
    except EncryptionConfigError as exc:
        logger.error('Не удалось расшифровать токен user_id=%s: %s', user_id, exc)
        return {'success': False, 'error': 'Ошибка конфигурации шифрования на сервере', 'code': 'crypto_error'}

    provider = YandexMusicProvider(proxy_url=_proxy_url())

    try:
        provider_artists = _fetch_artists_with_retry(provider, access_token)
    except YandexMusicAuthError:
        account.last_sync_status = 'error'
        account.last_sync_error = 'Токен недействителен — требуется повторное подключение'
        db.commit()
        return {'success': False, 'error': account.last_sync_error, 'code': 'reauth_required'}
    except YandexMusicProviderError as exc:
        account.last_sync_status = 'error'
        account.last_sync_error = str(exc)
        db.commit()
        return {
            'success': False,
            'error': f'Яндекс.Музыка временно недоступна: {exc}',
            'code': 'provider_error',
        }

    user = db.query(User).filter_by(id=user_id).first()
    if not user:
        return {'success': False, 'error': 'Пользователь не найден', 'code': 'user_not_found'}

    added = []
    existing_names = {a.name for a in user.favorite_artists}
    for provider_artist in provider_artists:
        artist = db.query(Artist).filter_by(name=provider_artist.name).first()
        if not artist:
            artist = Artist(name=provider_artist.name, genre=provider_artist.genre)
            db.add(artist)
            db.flush()  # получаем artist.id до commit, чтобы связать с пользователем

        if provider_artist.name not in existing_names:
            user.favorite_artists.append(artist)
            existing_names.add(provider_artist.name)
            added.append(provider_artist.name)

    account.last_synced_at = _utcnow()
    account.last_sync_status = 'success'
    account.last_sync_error = None
    db.commit()

    return {
        'success': True,
        'skipped': False,
        'artists_found': len(provider_artists),
        'artists_added': added,
        'last_synced_at': account.last_synced_at.isoformat(),
    }
