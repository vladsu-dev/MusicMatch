# backend/music_providers/base.py
"""
Абстрактный слой между бизнес-логикой приложения (backend/yandex_music_service.py,
эндпоинты Flask) и конкретной библиотекой-обёрткой музыкального сервиса.

Бизнес-логика работает только с типами и интерфейсом из этого файла и
ничего не знает о `yandex_music`. Если в будущем понадобится добавить
другой провайдер (Spotify, Apple Music и т.п.), достаточно реализовать
`MusicProviderClient` — остальной код менять не придётся.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class ProviderArtist:
    """Универсальное представление исполнителя, не зависящее от провайдера."""

    name: str
    genre: Optional[str] = None
    external_id: Optional[str] = None


@dataclass
class DeviceAuthCode:
    """Данные для показа пользователю на шаге подтверждения device-flow."""

    verification_url: str
    user_code: str


@dataclass
class ProviderToken:
    """Результат успешной авторизации — то, что нужно сохранить."""

    access_token: str
    refresh_token: Optional[str]
    expires_in: Optional[int]
    token_type: str = 'bearer'


class MusicProviderClient(ABC):
    """Интерфейс, который должен реализовать каждый провайдер музыки."""

    provider_name: str = 'base'

    @abstractmethod
    def start_device_auth(self, on_code: Callable[[DeviceAuthCode], None]) -> ProviderToken:
        """
        Блокирующий вызов OAuth Device Flow.
        `on_code` вызывается сразу, как только известны verification_url и
        user_code — до того, как пользователь подтвердит вход. Вызывающий
        код обязан запускать это в отдельном потоке (см. yandex_auth_flow.py).
        """
        raise NotImplementedError

    @abstractmethod
    def get_favorite_artists(self, access_token: str) -> List[ProviderArtist]:
        """Возвращает список любимых исполнителей пользователя."""
        raise NotImplementedError
