# tests/test_yandex_music_provider.py
"""
Тесты адаптера backend/music_providers/yandex_music_provider.py.

Класс `yandex_music.Client` подменяется фейком — реальная сеть и
библиотека здесь не нужны. Цель — проверить именно нашу логику
извлечения имён исполнителей (включая запасной путь на случай, если
artists_name() отсутствует) и корректную обработку ошибок авторизации.
"""
import pytest

from backend.music_providers import yandex_music_provider as ymp
from backend.music_providers.yandex_music_provider import (
    YandexMusicAuthError,
    YandexMusicProvider,
    YandexMusicProviderError,
)


class _FakeArtist:
    def __init__(self, name):
        self.name = name


class _FakeFullTrack:
    def __init__(self, names=None, artists=None):
        self._names = names
        self.artists = artists or []

    def artists_name(self):
        if self._names is None:
            raise AttributeError('метод недоступен в этой версии')
        return self._names


class _FakeShortTrack:
    def __init__(self, full_track):
        self._full_track = full_track

    def fetch_track(self):
        return self._full_track


class _FakeClient:
    """Подменяет yandex_music.Client. instances с UnauthorizedError='init'
    или ='likes' симулируют сбой авторизации на соответствующем шаге."""

    def __init__(self, access_token=None, request=None, liked=None, fail_at=None):
        self._liked = liked or []
        self._fail_at = fail_at

    def init(self):
        if self._fail_at == 'init':
            raise ymp.UnauthorizedError('токен недействителен')

    def users_likes_tracks(self):
        if self._fail_at == 'likes':
            raise ymp.UnauthorizedError('токен недействителен')
        return self._liked


def _patch_client(monkeypatch, liked=None, fail_at=None):
    monkeypatch.setattr(
        ymp, 'YandexClient',
        lambda *args, **kwargs: _FakeClient(*args, liked=liked, fail_at=fail_at, **kwargs),
    )


def test_get_favorite_artists_uses_artists_name_method(monkeypatch):
    liked = [_FakeShortTrack(_FakeFullTrack(names=['Земфира']))]
    _patch_client(monkeypatch, liked=liked)

    result = YandexMusicProvider().get_favorite_artists('token')

    assert [a.name for a in result] == ['Земфира']


def test_get_favorite_artists_falls_back_to_artists_list(monkeypatch):
    # artists_name() отсутствует в этой "версии" библиотеки — используем artists[].name
    liked = [_FakeShortTrack(_FakeFullTrack(names=None, artists=[_FakeArtist('Кино')]))]
    _patch_client(monkeypatch, liked=liked)

    result = YandexMusicProvider().get_favorite_artists('token')

    assert [a.name for a in result] == ['Кино']


def test_get_favorite_artists_deduplicates_across_tracks(monkeypatch):
    liked = [
        _FakeShortTrack(_FakeFullTrack(names=['Земфира'])),
        _FakeShortTrack(_FakeFullTrack(names=['Земфира'])),
        _FakeShortTrack(_FakeFullTrack(names=['Кино'])),
    ]
    _patch_client(monkeypatch, liked=liked)

    result = YandexMusicProvider().get_favorite_artists('token')

    assert sorted(a.name for a in result) == ['Земфира', 'Кино']


def test_get_favorite_artists_empty_likes_returns_empty_list(monkeypatch):
    _patch_client(monkeypatch, liked=[])
    assert YandexMusicProvider().get_favorite_artists('token') == []


def test_unauthorized_on_init_raises_auth_error(monkeypatch):
    _patch_client(monkeypatch, fail_at='init')
    with pytest.raises(YandexMusicAuthError):
        YandexMusicProvider().get_favorite_artists('token')


def test_unauthorized_on_likes_raises_auth_error(monkeypatch):
    _patch_client(monkeypatch, fail_at='likes')
    with pytest.raises(YandexMusicAuthError):
        YandexMusicProvider().get_favorite_artists('token')


def test_track_fetch_failure_is_skipped_not_fatal(monkeypatch):
    class _BrokenShortTrack:
        def fetch_track(self):
            raise ymp.YandexMusicError('временная ошибка на конкретном треке')

    liked = [_BrokenShortTrack(), _FakeShortTrack(_FakeFullTrack(names=['Кино']))]
    _patch_client(monkeypatch, liked=liked)

    result = YandexMusicProvider().get_favorite_artists('token')

    assert [a.name for a in result] == ['Кино']
