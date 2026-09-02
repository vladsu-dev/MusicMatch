# MusicMatch

MusicMatch — веб-приложение для знакомств на основе музыкальных предпочтений.
Проект построен на Flask и PostgreSQL и сейчас содержит регистрацию,
авторизацию по JWT, профили пользователей и интеграцию с Яндекс.Музыкой для
импорта любимых исполнителей.

> **Статус:** учебный / развивающийся проект. Перед публичным production-
> релизом нужно отдельно проверить юридические требования, миграции БД,
> мониторинг и масштабирование.

## Возможности

- регистрация и вход пользователей;
- JWT-аутентификация и защищённый профиль;
- хранение музыкального профиля и любимых исполнителей;
- подключение Яндекс.Музыки через device flow;
- шифрование токенов Яндекс.Музыки перед сохранением в БД;
- синхронизация любимых исполнителей с rate limit и retry для временных ошибок;
- тесты бизнес-логики интеграции и криптографических утилит.

Функции вроде DeepSeek, Redis, Socket.IO и полноценного алгоритма дейтинг-
матчинга не считаются реализованными только потому, что они встречались в
старой документации: сейчас они не входят в рабочий стек этого репозитория.

## Стек

| Слой | Технологии |
|---|---|
| Backend | Python 3.12+, Flask, SQLAlchemy |
| Auth | Flask-JWT-Extended, bcrypt |
| Database | PostgreSQL + psycopg 3 |
| Music | `yandex-music` (LGPL-3.0, неофициальная библиотека) |
| Frontend | HTML, CSS, JavaScript |
| Production | Gunicorn + Nginx + Let's Encrypt |
| Tests | pytest |

## Структура проекта

```text
Music_friends-main/
├── app.py                       # Flask entrypoint и HTTP API
├── backend/
│   ├── auth.py                  # регистрация, хеширование и проверка паролей
│   ├── crypto_utils.py          # шифрование токенов
│   ├── database.py              # SQLAlchemy engine / sessions
│   ├── models.py                # модели БД
│   ├── retry.py                 # общий retry-декоратор
│   ├── yandex_auth_flow.py      # device flow в фоне
│   ├── yandex_music_service.py  # бизнес-логика синхронизации
│   └── music_providers/         # абстракция и провайдеры музыки
├── frontend/
│   ├── templates/index.html
│   └── static/{css,js}/
├── tests/                       # автоматические тесты
├── docs/                        # подробная документация по интеграциям
├── deploy/                      # production-конфигурация Nginx
├── .env.template                # безопасный шаблон конфигурации
├── Dockerfile
├── docker-compose.yml
├── THIRD_PARTY_NOTICES.md
├── LICENSE
└── requirements.txt
```

## Быстрый старт

### 1. Требования

- Python 3.12+;
- PostgreSQL 15+;
- Git;
- Docker Desktop — необязательно, но удобно для локальной БД.

### 2. Установка

```bash
git clone <repository-url>
cd Music_friends-main
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Настройка `.env`

Сделайте копию шаблона:

```bash
cp .env.template .env
```

Сгенерируйте секреты:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Первый результат используйте для `SECRET_KEY`, второй — для
`JWT_SECRET_KEY`, третий — для `YANDEX_TOKEN_ENCRYPTION_KEY`.

Заполните PostgreSQL-переменные (`DB_USER`, `DB_PASSWORD`, `DB_HOST`,
`DB_PORT`, `DB_NAME`). Эти значения берутся из вашей локальной или серверной
конфигурации PostgreSQL. Никакие значения из `.env` не нужно коммитить в Git.

### 4. Локальная PostgreSQL через Docker

После заполнения `.env`:

```bash
docker compose up -d db
```

При запуске самого приложения через Docker Compose `DB_HOST` автоматически
переопределяется на `db` — имя сервиса PostgreSQL внутри compose-сети.

Затем запустите приложение:

```bash
python app.py
```

По умолчанию оно будет доступно на `http://127.0.0.1:5001`.

### 5. Проверка тестов

```bash
pytest -q
```

## Конфигурация `.env`

| Переменная | Обязательна | Откуда берётся |
|---|---:|---|
| `DB_USER` | Да | Пользователь PostgreSQL |
| `DB_PASSWORD` | Да | Пароль пользователя PostgreSQL |
| `DB_HOST` | Да | Хост БД, например `localhost` или `db` в Docker Compose |
| `DB_PORT` | Да | Обычно `5432` |
| `DB_NAME` | Да | Имя базы, например `musicmatch` |
| `SECRET_KEY` | Да | Случайная строка, генерируется локально |
| `JWT_SECRET_KEY` | Да | Отдельная случайная строка |
| `YANDEX_TOKEN_ENCRYPTION_KEY` | Да | Fernet-ключ, генерируется локально |
| `YANDEX_MUSIC_PROXY_URL` | Нет | URL вашего HTTP/SOCKS5 proxy |
| `CORS_ORIGINS` | Нет | Домены frontend, если он вынесен на другой origin |
| `TRUST_PROXY` | Для production | `true`, только если перед Flask стоит ваш Nginx/reverse proxy |

### Важное правило для секретов

`.env` предназначен только для конкретного окружения. `.env.template` — единственный
вариант, который можно хранить в Git. Никогда не вставляйте API-токены,
пароли БД, JWT-ключи или Fernet-ключ в README, исходный код или коммиты.

## API

### Аутентификация

| Метод | Endpoint | Назначение |
|---|---|---|
| `POST` | `/api/register` | Регистрация |
| `POST` | `/api/login` | Вход и получение JWT |
| `GET` | `/api/profile` | Профиль текущего пользователя |

### Яндекс.Музыка

| Метод | Endpoint | Назначение |
|---|---|---|
| `POST` | `/api/yandex-music/connect` | Запуск device flow |
| `GET` | `/api/yandex-music/connect/status` | Проверка статуса авторизации |
| `GET` | `/api/yandex-music/status` | Статус подключения |
| `POST` | `/api/yandex-music/sync` | Синхронизация любимых исполнителей |
| `DELETE` | `/api/yandex-music/disconnect` | Отключение Яндекс.Музыки |

Состояние авторизации и ошибки интеграции подробно описаны в
[`docs/YANDEX_MUSIC_INTEGRATION.md`](docs/YANDEX_MUSIC_INTEGRATION.md).

### Health check

```text
GET /api/health
```

Используется reverse proxy или системой мониторинга для проверки доступности
приложения.

## Production и HTTPS

В production приложение **не должно** поднимать TLS самостоятельно через
`app.run()`. Рекомендуемая схема:

```text
Internet
   │
   │ HTTPS :443
   ▼
Nginx
   │  TLS termination + security headers
   │  HTTP :8000 / X-Forwarded-*
   ▼
Gunicorn
   │
   ▼
Flask (app.py)
   │
   ├── PostgreSQL
   └── Yandex Music API
```

Nginx принимает HTTPS и проксирует запросы на Gunicorn. Это стандартная схема
для Flask production deployment; приложение настроено принимать доверенные
`X-Forwarded-*` заголовки через `ProxyFix`, когда `TRUST_PROXY=true`.

Готовый конфиг находится в
[`deploy/nginx.conf.template`](deploy/nginx.conf.template).

### Что нужно сделать на сервере

1. Привязать DNS вашего домена к серверу.
2. Получить сертификат Let's Encrypt для домена.
3. Подставить домен в `deploy/nginx.conf.template` и установить конфиг Nginx.
4. Запустить Gunicorn/контейнер приложения на `127.0.0.1:8000`.
5. Установить `TRUST_PROXY=true` в `.env`.
6. Для отдельного frontend-origin заполнить `CORS_ORIGINS`.

Сертификат является инфраструктурной частью deployment: без домена и доступа
к серверу его невозможно выпустить из одного только репозитория.

## База данных и миграции

Сейчас таблицы создаются через `SQLAlchemy.metadata.create_all()` при запуске
приложения. Для production это упрощённый вариант. Перед первой серьёзной
миграцией схемы следует добавить Alembic и перестать менять структуру БД
неявно через `create_all()`.

## Яндекс.Музыка и ограничения

Интеграция использует неофициальную библиотеку `yandex-music`. Upstream прямо
указывает, что она работает с недокументированным API Яндекс.Музыки. Поэтому
лицензия библиотеки и разрешённость использования самого сервиса — разные
вопросы. Подробнее: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

Не храните расшифрованные токены в логах. Не передавайте их на frontend.
Токены, сохранённые MusicMatch, шифруются Fernet до записи в БД.

## Разработка

Перед коммитом рекомендуется выполнять:

```bash
python -m compileall app.py backend tests
pytest -q
```

Не добавляйте в репозиторий `.env`, приватные ключи TLS, дампы БД и локальные
runtime-файлы.

## Авторы

- Vlasislav Subarev — https://github.com/vladsu-dev
- Kirill Svitov — https://github.com/kirillsvi
- Andrey Denisov — https://github.com/hkkcxzq

## Лицензия

Проприетарные части проекта распространяются по
[`LICENSE`](LICENSE). Сторонние компоненты лицензируются отдельно — см.
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
