# MusicMatch

MusicMatch переписан на Python. Теперь проект состоит из Django-приложения, HTML-шаблонов, CSS, PostgreSQL и JWT-авторизации через httpOnly cookies. React, Vite, Node-сервер и npm-команды больше не нужны для запуска приложения.

## Что находится в проекте

| Путь | За что отвечает |
| --- | --- |
| `manage.py` | Главная команда Django: миграции, тесты, запуск сервера. |
| `config/settings.py` | Настройки Django, PostgreSQL, cookies, CSRF, CSP и static files. |
| `music/models.py` | Модели для существующих таблиц: users, profiles, decisions, matches, messages, sessions. |
| `music/authentication.py` | JWT access/refresh cookies, проверка старых паролей и обновление старого хэша. |
| `music/views.py` | Страницы регистрации, входа, анкеты, ленты, мэтчей, чата и health-check. |
| `music/migrations/` | Миграции PostgreSQL. Первая принимает старую схему, вторая добавляет Python-служебные поля. |
| `templates/music/` | Обычные HTML-страницы Django. |
| `static/music/styles.css` | Внешний вид проекта. |
| `scripts/setup_env.py` | Создаёт `.env` и генерирует секреты. |
| `tests/` и `music/tests.py` | Проверки новой версии и миграции со старой базы. |

## Быстрый запуск на Mac

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/setup_env.py
docker compose up -d --wait
python manage.py migrate
python manage.py runserver
```

После запуска откройте `http://127.0.0.1:8000`.

Если Docker пишет, что порт `5432` занят, это нормально для Mac, где уже может работать PostgreSQL. В этой версии Docker по умолчанию публикует базу на `127.0.0.1:5433`, а внутри контейнера PostgreSQL остаётся на `5432`.

## Если база уже была создана прошлой версией

Перед первым запуском новой версии лучше сделать резервную копию:

```bash
pg_dump "$DATABASE_URL" > musicmatch_backup.dump
```

Затем выполните:

```bash
python manage.py migrate
```

Миграция не пересоздаёт старые таблицы, если они уже есть и совпадают со схемой MusicMatch. Пользователи, анкеты, лайки, мэтчи, сообщения и старые refresh-сессии остаются в базе. Старые пароли формата Node `scrypt` принимаются при входе, а после успешного входа пароль автоматически сохраняется уже в Django-формате.

После переписывания пользователям нужно войти заново в браузере, потому что cookies теперь называются `mm_py_access` и `mm_py_refresh`.

## Как устроена авторизация

При входе сервер создаёт запись в таблице `sessions`. В браузер отправляются две httpOnly cookies:

- `mm_py_access` — короткий JWT на 15 минут;
- `mm_py_refresh` — случайный refresh-токен на 30 дней, в базе хранится только SHA-256 хэш.

Если access-токен истёк, middleware пробует обновить его через refresh-токен и выдаёт новую пару cookies. Если refresh-токен устарел или уже был использован, пользователь попадает на вход.

## Как работает приложение

1. Пользователь регистрируется или входит.
2. Без анкеты его отправляет на `/profile/`.
3. После анкеты открывается лента `/`, где показываются профили других людей.
4. Нажатие `Нравится` или `Пропустить` создаёт запись в `decisions`.
5. Если два пользователя поставили друг другу `Нравится`, создаётся запись в `matches`.
6. У мэтча появляется чат `/chat/<match_id>/`, сообщения сохраняются в `messages`.

Чат и страница мэтчей обновляются через HTML `meta refresh`. Поле ввода сообщения находится вне обновляемой истории, поэтому набираемый текст не пропадает при обновлении истории.

## Проверки

Для обычной проверки:

```bash
python manage.py check
python manage.py migrate
python manage.py test music.tests
```

Для проверки сценария старой базы нужен отдельный тестовый PostgreSQL database URL:

```bash
LEGACY_DATABASE_URL=postgres://musicmatch:musicmatch_password@127.0.0.1:5433/musicmatch_legacy_test python tests/check_legacy_upgrade.py
```

Браузерный тест без JavaScript:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python manage.py test tests.test_browser
```

## Продакшен

Для продакшена установите:

```env
DJANGO_DEBUG=0
APP_ORIGIN=https://your-domain.example
ALLOWED_HOSTS=your-domain.example
TRUST_HTTPS_PROXY=1
```

Запуск через Gunicorn:

```bash
python manage.py collectstatic --noinput
gunicorn config.wsgi:application
```

Периодически удаляйте старые сессии и rate-limit записи:

```bash
python manage.py cleanup_musicmatch
```
