# backend/music_providers/yandex_music_provider.py
"""
Реализация MusicProviderClient поверх неофициальной библиотеки
yandex-music-api (https://github.com/MarshalX/yandex-music-api, LGPL-3.0).
См. THIRD_PARTY_NOTICES.md — там разбор лицензии и связанных рисков.

⚠️ ВАЖНО: это НЕофициальная, реверс-инжиниринговая библиотека — у Яндекса
нет публичного API Яндекс.Музыки. Это отдельный риск от лицензии самой
библиотеки: использование может нарушать условия использования сервиса
и в любой момент перестать работать из-за изменений на стороне Яндекса.
Подробности и рекомендации — в THIRD_PARTY_NOTICES.md.

Используется синхронный `Client`, т.к. Flask-приложение в этом проекте —
синхронное (WSGI). Если бэкенд когда-нибудь переедет на ASGI/async-фреймворк,
здесь же можно добавить асинхронный вариант на `ClientAsync` — интерфейс
MusicProviderClient для этого специально не завязан на конкретный клиент.
"""
import logging
from typing import Callable, List, Optional

from yandex_music import Client as YandexClient
from yandex_music.exceptions import TimedOut, UnauthorizedError, YandexMusicError

from backend.music_providers.base import (
    DeviceAuthCode,
    MusicProviderClient,
    ProviderArtist,
    ProviderToken,
)

logger = logging.getLogger(__name__)


class YandexMusicProviderError(Exception):
    """Базовое исключение адаптера — временный/неизвестный сбой на стороне Яндекса."""


class YandexMusicAuthError(YandexMusicProviderError):
    """Токен недействителен или истёк — пользователю нужно подключиться заново."""


class YandexMusicProvider(MusicProviderClient):
    provider_name = 'yandex_music'

    def __init__(self, proxy_url: Optional[str] = None):
        # Прокси можно задать отдельно для этого провайдера через
        # YANDEX_MUSIC_PROXY_URL в .env — см. README/docs.
        self._proxy_url = proxy_url

    def _build_request(self):
        """Создаёт объект Request с прокси, если он настроен. Socks-прокси
        поддерживаются только синхронным клиентом (см. документацию библиотеки)."""
        if not self._proxy_url:
            return None
        from yandex_music.utils.request import Request  # локальный импорт — модуль опционален
        return Request(proxy_url=self._proxy_url)

    def start_device_auth(self, on_code: Callable[[DeviceAuthCode], None]) -> ProviderToken:
        client = YandexClient(request=self._build_request())

        def _on_code(code):
            on_code(DeviceAuthCode(verification_url=code.verification_url, user_code=code.user_code))

        try:
            token = client.device_auth(on_code=_on_code)
        except UnauthorizedError as exc:
            raise YandexMusicAuthError(str(exc)) from exc
        except YandexMusicError as exc:
            raise YandexMusicProviderError(str(exc)) from exc

        if token is None:
            # Библиотека может вернуть None при отказе/таймауте подтверждения —
            # трактуем как ошибку авторизации, а не временный сбой.
            raise YandexMusicAuthError('Авторизация не была подтверждена пользователем')

        return ProviderToken(
            access_token=token.access_token,
            refresh_token=getattr(token, 'refresh_token', None),
            expires_in=getattr(token, 'expires_in', None),
            token_type=getattr(token, 'token_type', None) or 'bearer',
        )

    def get_favorite_artists(self, access_token: str) -> List[ProviderArtist]:
        client = YandexClient(access_token, request=self._build_request())
        try:
            client.init()
        except UnauthorizedError as exc:
            raise YandexMusicAuthError('Токен Яндекс.Музыки недействителен или истёк') from exc
        except (TimedOut, YandexMusicError) as exc:
            raise YandexMusicProviderError(f'Не удалось инициализировать клиента: {exc}') from exc

        try:
            liked = client.users_likes_tracks()
        except UnauthorizedError as exc:
            raise YandexMusicAuthError('Токен Яндекс.Музыки недействителен или истёк') from exc
        except (TimedOut, YandexMusicError) as exc:
            raise YandexMusicProviderError(f'Ошибка при получении понравившихся треков: {exc}') from exc

        if not liked:
            return []

        artist_names = set()
        for short_track in liked:
            try:
                full_track = short_track.fetch_track()
            except TimedOut as exc:
                logger.warning('Таймаут при получении трека — пропускаем: %s', exc)
                continue
            except YandexMusicError as exc:
                logger.warning('Не удалось получить полную информацию о треке: %s', exc)
                continue

            if not full_track:
                continue

            names: List[str] = []
            # artists_name() — основной способ по документации библиотеки;
            # оставляем запасной путь через artists[].name на случай, если
            # метод отсутствует в установленной версии пакета.
            if hasattr(full_track, 'artists_name'):
                try:
                    names = full_track.artists_name() or []
                except Exception as exc:  # noqa: BLE001 — защита от изменений внешнего API
                    logger.debug('artists_name() не сработал, используем запасной путь: %s', exc)
                    names = []
            if not names and getattr(full_track, 'artists', None):
                names = [a.name for a in full_track.artists if getattr(a, 'name', None)]

            artist_names.update(n.strip() for n in names if n and n.strip())

        return [ProviderArtist(name=name) for name in sorted(artist_names)]
