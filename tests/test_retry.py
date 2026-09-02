# tests/test_retry.py
import pytest

from backend.retry import retry_on_error


class _TransientError(Exception):
    pass


class _PermanentError(Exception):
    pass


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr('backend.retry.time.sleep', lambda *_: None)  # тесты не должны реально ждать

    calls = {'count': 0}

    @retry_on_error(exceptions=(_TransientError,), attempts=3, base_delay=0.01)
    def flaky():
        calls['count'] += 1
        if calls['count'] < 3:
            raise _TransientError('временный сбой')
        return 'ok'

    assert flaky() == 'ok'
    assert calls['count'] == 3


def test_raises_after_exhausting_attempts(monkeypatch):
    monkeypatch.setattr('backend.retry.time.sleep', lambda *_: None)

    @retry_on_error(exceptions=(_TransientError,), attempts=2, base_delay=0.01)
    def always_fails():
        raise _TransientError('всегда падает')

    with pytest.raises(_TransientError):
        always_fails()


def test_does_not_catch_unlisted_exceptions(monkeypatch):
    monkeypatch.setattr('backend.retry.time.sleep', lambda *_: None)

    @retry_on_error(exceptions=(_TransientError,), attempts=3, base_delay=0.01)
    def raises_permanent():
        raise _PermanentError('не временная ошибка')

    with pytest.raises(_PermanentError):
        raises_permanent()
