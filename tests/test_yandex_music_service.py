# tests/test_yandex_music_service.py
"""
Тесты бизнес-логики синхронизации (backend/yandex_music_service.py).

Реальная библиотека yandex_music и сеть здесь НЕ используются — вместо
настоящего YandexMusicProvider подставляется фейк с предсказуемым
поведением. Это позволяет проверить логику (кеш/rate-limit, дедупликацию
исполнителей, обработку ошибок авторизации и временных сбоев) без
интернета и без реального аккаунта Яндекс.Музыки.
"""
from datetime import timedelta

import pytest

from backend.models import Artist, YandexMusicAccount
from backend.music_providers.base import ProviderArtist, ProviderToken
from backend.music_providers.yandex_music_provider import (
    YandexMusicAuthError,
    YandexMusicProviderError,
)
from backend import yandex_music_service as svc


class _FakeProvider:
    """Подменяет YandexMusicProvider в тестах."""

    def __init__(self, artists=None, raise_error=None, proxy_url=None):
        self._artists = artists or []
        self._raise_error = raise_error
        self.calls = 0

    def get_favorite_artists(self, access_token):
        self.calls += 1
        if self._raise_error:
            raise self._raise_error
        return self._artists


def _patch_provider(monkeypatch, artists=None, raise_error=None):
    fake = _FakeProvider(artists=artists, raise_error=raise_error)
    monkeypatch.setattr(svc, 'YandexMusicProvider', lambda proxy_url=None: fake)
    return fake


def _connect(db_session, user, refresh_token='refresh-abc'):
    token = ProviderToken(access_token='access-abc', refresh_token=refresh_token, expires_in=3600)
    return svc.save_token(db_session, user.id, token)


def test_sync_without_connection_returns_not_connected(db_session, user_factory):
    user = user_factory()
    result = svc.sync_favorite_artists(db_session, user.id)
    assert result == {'success': False, 'error': 'Яндекс.Музыка не подключена', 'code': 'not_connected'}


def test_save_token_encrypts_and_persists(db_session, user_factory):
    user = user_factory()
    account = _connect(db_session, user)

    assert account.access_token_encrypted != 'access-abc'  # не в открытом виде
    stored = db_session.query(YandexMusicAccount).filter_by(user_id=user.id).one()
    assert stored.access_token_encrypted == account.access_token_encrypted
    assert stored.refresh_token_encrypted is not None


def test_sync_adds_new_artists_to_profile(db_session, user_factory, monkeypatch):
    user = user_factory()
    _connect(db_session, user)
    _patch_provider(monkeypatch, artists=[
        ProviderArtist(name='Земфира'),
        ProviderArtist(name='Кино'),
    ])

    result = svc.sync_favorite_artists(db_session, user.id)

    assert result['success'] is True
    assert result['skipped'] is False
    assert sorted(result['artists_added']) == ['Земфира', 'Кино']
    assert {a.name for a in user.favorite_artists} == {'Земфира', 'Кино'}


def test_sync_reuses_existing_artist_row_no_duplicates(db_session, user_factory, monkeypatch):
    user1 = user_factory(username='user1', email='u1@example.com')
    user2 = user_factory(username='user2', email='u2@example.com')
    _connect(db_session, user1)
    _connect(db_session, user2)

    _patch_provider(monkeypatch, artists=[ProviderArtist(name='Кино')])
    svc.sync_favorite_artists(db_session, user1.id)
    svc.sync_favorite_artists(db_session, user2.id)

    # Оба пользователя любят "Кино", но в таблице artists должна быть одна строка.
    assert db_session.query(Artist).filter_by(name='Кино').count() == 1


def test_sync_is_rate_limited_without_force(db_session, user_factory, monkeypatch):
    user = user_factory()
    _connect(db_session, user)
    _patch_provider(monkeypatch, artists=[ProviderArtist(name='Земфира')])

    first = svc.sync_favorite_artists(db_session, user.id)
    assert first['skipped'] is False

    second = svc.sync_favorite_artists(db_session, user.id)
    assert second['success'] is True
    assert second['skipped'] is True
    assert 'retry_after_seconds' in second


def test_force_bypasses_rate_limit(db_session, user_factory, monkeypatch):
    user = user_factory()
    account = _connect(db_session, user)
    _patch_provider(monkeypatch, artists=[ProviderArtist(name='Земфира')])

    svc.sync_favorite_artists(db_session, user.id)
    # "телепортируем" последнюю синхронизацию в прошлое, чтобы её не хватало для лимита
    account.last_synced_at = svc._utcnow() - timedelta(minutes=1)
    db_session.commit()

    result = svc.sync_favorite_artists(db_session, user.id, force=True)
    assert result['skipped'] is False


def test_sync_handles_auth_error_without_retrying(db_session, user_factory, monkeypatch):
    user = user_factory()
    _connect(db_session, user)
    fake = _patch_provider(monkeypatch, raise_error=YandexMusicAuthError('токен истёк'))

    result = svc.sync_favorite_artists(db_session, user.id)

    assert result['success'] is False
    assert result['code'] == 'reauth_required'
    assert fake.calls == 1  # невалидный токен сам себя не починит — повторять бессмысленно
    account = db_session.query(YandexMusicAccount).filter_by(user_id=user.id).one()
    assert account.last_sync_status == 'error'


def test_sync_retries_transient_provider_error_then_gives_up(db_session, user_factory, monkeypatch):
    user = user_factory()
    _connect(db_session, user)
    fake = _patch_provider(monkeypatch, raise_error=YandexMusicProviderError('Яндекс недоступен'))
    monkeypatch.setattr(svc.time, 'sleep', lambda *_: None)  # не ждём реальные секунды backoff'а в тесте

    result = svc.sync_favorite_artists(db_session, user.id)

    assert result['success'] is False
    assert result['code'] == 'provider_error'
    assert fake.calls == 3  # 3 попытки по умолчанию, прежде чем сдаться


def test_disconnect_removes_account(db_session, user_factory):
    user = user_factory()
    _connect(db_session, user)

    assert svc.disconnect(db_session, user.id) is True
    assert db_session.query(YandexMusicAccount).filter_by(user_id=user.id).first() is None
    assert svc.disconnect(db_session, user.id) is False  # повторное отключение — no-op
