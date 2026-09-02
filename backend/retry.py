# backend/retry.py
"""
Декоратор для повторных попыток при временных сбоях внешних API
(таймауты, кратковременная недоступность). Не предназначен для
"проглатывания" логических ошибок вроде невалидного токена — такие
исключения должны быть отдельного типа и НЕ передаваться в `exceptions`.
"""
import logging
import time
from functools import wraps
from typing import Tuple, Type

logger = logging.getLogger(__name__)


def retry_on_error(
    exceptions: Tuple[Type[BaseException], ...],
    attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
):
    """
    exceptions  — какие типы исключений считать временными и повторять.
    attempts    — максимум попыток, включая первую.
    base_delay  — задержка перед первым повтором, сек.
    max_delay   — верхняя граница экспоненциально растущей задержки, сек.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == attempts:
                        break
                    logger.warning(
                        '%s: попытка %s/%s не удалась (%s), повтор через %.1fс',
                        func.__name__, attempt, attempts, exc, delay,
                    )
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
            raise last_exc

        return wrapper

    return decorator
