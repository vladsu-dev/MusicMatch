# Интеграция с Яндекс.Музыкой

MusicMatch умеет подключить аккаунт Яндекс.Музыки и импортировать список
любимых исполнителей в музыкальный профиль пользователя.

> **Важно:** используется неофициальная библиотека `yandex-music`, работающая
> с недокументированным API Яндекс.Музыки. Лицензия библиотеки (LGPL-3.0) не
> является разрешением на использование самого сервиса. Перед production-
> запуском проверьте актуальные условия Яндекса и внутренние требования
> проекта.

Связанный документ: [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).

## Архитектура

```text
HTTP API: app.py
       │
       ▼
backend/yandex_auth_flow.py
       │   device flow в background thread
       ▼
backend/yandex_music_service.py
       │   sync / rate limit / retry / persistence
       ▼
backend/music_providers/base.py
       │
       ▼
backend/music_providers/yandex_music_provider.py
       │
       ▼
 yandex_music (third-party package)
```

Сервисный слой не знает детали конкретного SDK. Провайдер скрывает прямой
импорт `yandex_music`, поэтому другой музыкальный источник можно добавить как
ещё одну реализацию `MusicProviderClient`.

## Почему подключение состоит из двух HTTP-запросов

`device_auth()` блокирует выполнение до подтверждения пользователем. Нельзя
держать HTTP-запрос `/connect` открытым несколько минут, поэтому приложение
разделяет процесс на две части:

1. `POST /api/yandex-music/connect` запускает авторизацию в фоне и возвращает
   код/URL, когда библиотека получает их.
2. `GET /api/yandex-music/connect/status` опрашивает состояние до `connected`
   или `error`.
3. После успеха access/refresh token сохраняется в БД в зашифрованном виде.

## API

Все перечисленные endpoints требуют:

```http
Authorization: Bearer <JWT>
```

### `POST /api/yandex-music/connect`

Запускает новый device flow для текущего пользователя.

Пример успешного промежуточного ответа:

```json
{
  "status": "code_ready",
  "verification_url": "https://...",
  "user_code": "ABCD-1234"
}
```

### `GET /api/yandex-music/connect/status`

Периодически вызывается frontend.

```json
{"status": "connected"}
```

или:

```json
{
  "status": "error",
  "error": "Авторизация не была подтверждена пользователем"
}
```

### `GET /api/yandex-music/status`

Возвращает состояние сохранённого подключения:

```json
{
  "connected": true,
  "connected_at": "...",
  "last_synced_at": "...",
  "last_sync_status": "success"
}
```

### `POST /api/yandex-music/sync`

Импортирует любимых исполнителей.

Пустое тело или `{}` используют штатный rate limit. Для ручного принудительного
запуска:

```json
{"force": true}
```

Успешный ответ:

```json
{
  "success": true,
  "skipped": false,
  "artists_found": 42,
  "artists_added": ["Кино", "Земфира"],
  "last_synced_at": "..."
}
```

Основные коды ошибок:

| Код | HTTP | Значение |
|---|---:|---|
| `not_connected` | 400 | Пользователь ещё не подключил Яндекс.Музыку |
| `reauth_required` | 409 | Сохранённый токен недействителен |
| `provider_error` | 502 | Временная ошибка внешнего провайдера |
| `crypto_error` | 502 | Не настроен ключ шифрования токенов |

### `DELETE /api/yandex-music/disconnect`

Удаляет сохранённый токен пользователя.

```json
{"success": true}
```

## Хранение токенов

Токены не должны храниться в открытом виде.

`backend/crypto_utils.py` получает `YANDEX_TOKEN_ENCRYPTION_KEY` из окружения и
использует Fernet для шифрования перед записью в `yandex_music_accounts`.

Проверка ключа:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Сгенерированный ключ необходимо сохранить в `.env` как
`YANDEX_TOKEN_ENCRYPTION_KEY`.

**Важно:** потеря этого ключа означает потерю возможности расшифровать уже
сохранённые токены. Храните production-ключ в секрет-хранилище или в другом
защищённом месте с резервной копией.

## Rate limit и retry

Повторная синхронизация одного аккаунта обычно не выполняется чаще одного
раза в 5 минут. `force=true` обходит локальный cache/rate limit.

Временные ошибки провайдера повторяются с backoff. Ошибка авторизации токена
не повторяется: пользователю возвращается `reauth_required`.

## Состояние device flow

Сейчас активные попытки авторизации хранятся в памяти процесса через
`YandexAuthFlowManager`.

Это означает:

- один worker/process — нормально;
- несколько Gunicorn workers — небезопасно для этого flow;
- несколько экземпляров приложения — flow между экземплярами не разделяется.

Поэтому в текущем production-шаблоне Gunicorn запускается с **одним worker**.
Для горизонтального масштабирования состояние нужно вынести в Redis или другую
общую очередь/хранилище состояния.

## Тестирование

Тесты интеграции не ходят в реальный API Яндекс.Музыки. Клиент библиотеки
заменяется fake-объектами, поэтому проверяется наша бизнес-логика:

- дедупликация исполнителей;
- повторное использование существующих записей;
- rate limit;
- retry временных ошибок;
- отдельная обработка невалидного токена;
- шифрование и расшифровка токенов.

Запуск:

```bash
pytest -q
```

Перед production также нужен ручной staging smoke-test с реальным аккаунтом.

## Frontend flow

Упрощённая последовательность:

```javascript
async function connectYandexMusic() {
  const start = await api.post('/api/yandex-music/connect');

  if (start.status === 'code_ready') {
    showCodeToUser(start.verification_url, start.user_code);
  }

  const poll = setInterval(async () => {
    const status = await api.get('/api/yandex-music/connect/status');

    if (status.status === 'connected') {
      clearInterval(poll);
      await api.post('/api/yandex-music/sync');
      refreshProfile();
    } else if (status.status === 'error') {
      clearInterval(poll);
      showError(status.error);
    }
  }, 2500);
}
```

## Известные ограничения

- API Яндекс.Музыки, используемое этой библиотекой, недокументировано и может
  измениться без предупреждения.
- Автоматическое обновление refresh token не реализовано; при необходимости
  повторного входа пользователь должен подключить аккаунт заново.
- Аудио не скачивается: интеграция ограничена метаданными любимых исполнителей.
- Глобального rate limit на весь сервис нет.
- Для изменения схемы БД в production рекомендуется Alembic; сейчас приложение
  использует `create_all()`.
