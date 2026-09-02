# backend/yandex_auth_flow.py
"""
Управление OAuth Device Flow поверх синхронного Flask-приложения.

`client.device_auth()` в библиотеке yandex-music — блокирующий вызов: он
ждёт, пока пользователь подтвердит вход на странице Яндекса (от нескольких
секунд до нескольких минут). Держать HTTP-запрос открытым всё это время
недопустимо, поэтому:
  1. POST /api/yandex-music/connect запускает device_auth в фоновом потоке
     и почти сразу возвращает verification_url + user_code (как только
     сработает on_code — это происходит быстро, до ожидания подтверждения).
  2. GET /api/yandex-music/connect/status опрашивается фронтендом, пока
     статус не станет success/error/timeout.

⚠️ Состояние хранится в памяти процесса (словарь ниже). Этого достаточно
для одного Flask-воркера (разработка, debug-сервер). Для production с
несколькими воркерами Gunicorn нужно вынести это состояние в Redis — он
уже упомянут в стеке проекта (см. README.md) как раз для подобных задач.
"""
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from backend.music_providers.base import DeviceAuthCode, ProviderToken
from backend.music_providers.yandex_music_provider import (
    YandexMusicProvider,
    YandexMusicProviderError,
)

logger = logging.getLogger(__name__)


@dataclass
class _FlowState:
    status: str = 'pending'  # pending -> code_ready -> success | error
    code: Optional[DeviceAuthCode] = None
    token: Optional[ProviderToken] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class YandexAuthFlowManager:
    """Потокобезопасный менеджер активных попыток авторизации (ключ — user_id)."""

    def __init__(self, proxy_url: Optional[str] = None):
        self._proxy_url = proxy_url if proxy_url is not None else os.getenv('YANDEX_MUSIC_PROXY_URL')
        self._lock = threading.Lock()
        self._flows: Dict[int, _FlowState] = {}

    def start(self, user_id: int) -> None:
        """Запускает фоновый поток авторизации, если для пользователя ещё
        нет активной попытки."""
        with self._lock:
            existing = self._flows.get(user_id)
            if existing and existing.status in ('pending', 'code_ready'):
                return
            self._flows[user_id] = _FlowState()

        thread = threading.Thread(
            target=self._run_flow, args=(user_id,), daemon=True,
            name=f'yandex-auth-{user_id}',
        )
        thread.start()

    def _run_flow(self, user_id: int) -> None:
        provider = YandexMusicProvider(proxy_url=self._proxy_url)

        def on_code(code: DeviceAuthCode):
            with self._lock:
                state = self._flows.get(user_id)
                if state:
                    state.code = code
                    state.status = 'code_ready'

        try:
            token = provider.start_device_auth(on_code=on_code)
            with self._lock:
                state = self._flows.get(user_id)
                if state:
                    state.token = token
                    state.status = 'success'
        except YandexMusicProviderError as exc:
            logger.warning('Ошибка device-flow для user_id=%s: %s', user_id, exc)
            with self._lock:
                state = self._flows.get(user_id)
                if state:
                    state.status = 'error'
                    state.error = str(exc)
        except Exception:  # noqa: BLE001 — фоновый поток не должен падать молча
            logger.exception('Непредвиденная ошибка device-flow для user_id=%s', user_id)
            with self._lock:
                state = self._flows.get(user_id)
                if state:
                    state.status = 'error'
                    state.error = 'Внутренняя ошибка авторизации'

    def get_status(self, user_id: int, wait_seconds: float = 3.0) -> dict:
        """Возвращает текущее состояние. Недолго ждём (short-poll), чтобы
        фронтенду не приходилось делать запрос раз в 200мс самому."""
        deadline = time.time() + wait_seconds
        while True:
            with self._lock:
                state = self._flows.get(user_id)
                if not state:
                    return {'status': 'not_found'}
                if state.status != 'pending' or time.time() >= deadline:
                    return self._serialize(state)
            time.sleep(0.2)

    def pop_token_if_ready(self, user_id: int) -> Optional[ProviderToken]:
        """Забирает токен и очищает состояние (вызывать сразу после
        успешного сохранения токена в БД, чтобы не хранить его в памяти дольше нужного)."""
        with self._lock:
            state = self._flows.get(user_id)
            if state and state.status == 'success' and state.token:
                token = state.token
                del self._flows[user_id]
                return token
            return None

    def clear_error(self, user_id: int) -> None:
        with self._lock:
            state = self._flows.get(user_id)
            if state and state.status == 'error':
                del self._flows[user_id]

    @staticmethod
    def _serialize(state: _FlowState) -> dict:
        result = {'status': state.status}
        if state.code:
            result['verification_url'] = state.code.verification_url
            result['user_code'] = state.code.user_code
        if state.error:
            result['error'] = state.error
        return result


# Единственный экземпляр на процесс — хранит состояние фоновых попыток авторизации.
auth_flow_manager = YandexAuthFlowManager()
