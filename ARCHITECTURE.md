ARCHITECTURE — Полный разбор проекта MusicMatch

Цель
- MusicMatch: сопоставление людей по музыкальным предпочтениям. Синхронизация любимых исполнителей из Яндекс.Музыки и использование их в профилях/матчах.

Ключевые переменные окружения
- SECRET_KEY, JWT_SECRET_KEY — Flask/JWT.
- DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME — Postgres.
- YANDEX_TOKEN_ENCRYPTION_KEY — Fernet-ключ.
- YANDEX_MUSIC_PROXY_URL — опционально.

Структура файлов и подробный разбор

1) app.py — точка входа
- Основные элементы:
  - create_app() -> Flask
    - Конфигурация: SECRET_KEY, JWT_SECRET_KEY, JWT_ACCESS_TOKEN_EXPIRES
    - SESSION_COOKIE_* безопасность
    - ProxyFix если TRUST_PROXY
    - CORS если CORS_ORIGINS
    - JWTManager(app), init_db()
  - Маршруты:
    - GET / -> render_template('index.html')
    - POST /api/register
      - Вход (JSON): {"username": str, "email": str, "password": str, "gender": str, "age": int?, "bio": str?}
      - Логика: валидация, register_user(...), create_access_token(identity=user_id)
      - Выход: 201 {"message": "Регистрация успешна", "access_token": token, "user_id": id}
    - POST /api/login
      - Вход: {"email": str, "password": str}
      - Логика: login_user(...), create_access_token
      - Выход: 200 {"message": "Вход выполнен", "access_token": token, "user_id": id}
    - GET /api/profile (jwt_required)
      - Возвращает профиль пользователя
    - /api/yandex-music/*
      - POST /connect -> auth_flow_manager.start(user_id) и быстрый ответ с статусом (verification_url + user_code когда готово)
      - GET /connect/status -> опрашивает состояние флоу, при success сохраняет токен через save_token
      - POST /sync -> вызывает sync_favorite_artists
      - DELETE /disconnect -> удаляет YandexMusicAccount
    - GET /api/health -> {"status":"healthy","version":"1.0.0"}

2) backend/database.py
- get_engine() -> Engine
  - Лениво создаёт движок SQLAlchemy для PostgreSQL: postgresql+psycopg://...
  - Проверяет DB_PASSWORD и конфигурацию
- SessionLocal() -> Session
  - Возвращает объект session (sessionmaker())
- Base(DeclarativeBase)
  - Базовый класс моделей
- init_db()
  - Base.metadata.create_all(bind=get_engine()) — только для разработки

3) backend/models.py — модели данных
- utcnow() -> datetime (UTC-aware)
- user_artists: таблица many-to-many
- User
  - Поля: id, username, email, password_hash, gender, age, bio, avatar_url, created_at, updated_at
  - Отношения: favorite_artists (M2M), music_profile (1-1), swipes, matches, messages, yandex_music_account (1-1)
- Artist, MusicProfile, YandexMusicAccount, Swipe, Match, Message — см. файл для полей
- Важная заметка: YandexMusicAccount хранит токены только в зашифрованном виде

4) backend/auth.py — регистрация и логин
- hash_password(password: str) -> str — bcrypt.hashpw
- verify_password(password: str, password_hash: str) -> bool
- register_user(username, email, password, gender, age=None, bio='') -> dict
  - Проверка существования, создание User, commit, возвращает {'success': True, 'user_id': id} или {'success': False,'error': msg}
- login_user(email, password) -> dict
- get_user_by_id(user_id) -> User

5) backend/crypto_utils.py — шифрование токенов
- _get_fernet() -> Fernet (использует YANDEX_TOKEN_ENCRYPTION_KEY)
- encrypt_token(plain_text: str) -> str
- decrypt_token(cipher_text: str) -> str
- EncryptionConfigError

6) backend/music_providers/base.py — интерфейс провайдера
- ProviderArtist(name: str, genre: Optional[str], external_id: Optional[str])
- DeviceAuthCode(verification_url: str, user_code: str)
- ProviderToken(access_token: str, refresh_token: Optional[str], expires_in: Optional[int], token_type: str='bearer')
- MusicProviderClient (ABC)
  - start_device_auth(on_code: Callable[[DeviceAuthCode], None]) -> ProviderToken
    - Блокирующий вызов (device flow). Вызвать в отдельном потоке.
  - get_favorite_artists(access_token: str) -> List[ProviderArtist]

7) backend/music_providers/yandex_music_provider.py — реализация провайдера
- Использует yandex_music.Client
- _build_request() -> Request|None (для proxy)
- start_device_auth(on_code) -> ProviderToken
  - client.device_auth(on_code=_on_code)
  - Обрабатывает UnauthorizedError -> YandexMusicAuthError, YandexMusicError -> YandexMusicProviderError
- get_favorite_artists(access_token) -> List[ProviderArtist]
  - client.init(), client.users_likes_tracks(), для каждого short_track -> fetch_track(); получаем artists_name() или artists[].name
  - Обрабатывает UnauthorizedError, TimedOutError и YandexMusicError

8) backend/yandex_auth_flow.py — менеджер device-flow
- _FlowState: status, code, token, error, created_at
- YandexAuthFlowManager
  - start(user_id)
  - _run_flow(user_id) — запускает provider.start_device_auth в фоне; on_code пишет verification_url/user_code; сохраняет token в state
  - get_status(user_id, wait_seconds=3.0) -> dict
  - pop_token_if_ready(user_id) -> Optional[ProviderToken]
  - clear_error(user_id)
- Примечание: state хранится в памяти процесса — для multi-worker нужен Redis

9) backend/yandex_music_service.py — бизнес-логика синхронизации
- MIN_SYNC_INTERVAL = 5 min
- save_token(db: Session, user_id: int, token: ProviderToken) -> YandexMusicAccount
  - Шифрует токены, сохраняет account, connected_at
- get_connection_status(db, user_id) -> dict
- disconnect(db, user_id) -> bool
- _fetch_artists_with_retry(provider, access_token, attempts=3, base_delay=1.5, max_delay=10.0)
  - Повторяет при YandexMusicProviderError; не повторяет при YandexMusicAuthError
- sync_favorite_artists(db, user_id, force=False) -> dict
  - Проверяет account; rate-limit (MIN_SYNC_INTERVAL); decrypt_token(); получает provider_artists с retry; создает Artist при необходимости; связывает с пользователем; обновляет last_synced_at/status; возвращает {'success': True, 'artists_added': [...], ...} или error-коды

10) backend/retry.py — декоратор retry_on_error
- retry_on_error(exceptions: Tuple[Type[BaseException],...], attempts=3, base_delay=1.0, max_delay=10.0)
- Использование: декоратор для повторных попыток при временных ошибках

11) frontend/templates и static/js
- HTML: index.html — UI (header, hero, auth modal, формы).
- main.js: AuthManager
  - handleLogin(), handleRegister() отправляют fetch('/api/login'|'/api/register')
  - saveToken(token, userId) -> localStorage
  - onAuthSuccess() -> закрывает модалку и показывает alert
  - showError(message)

12) tests/
- conftest.py: фикстуры db_session (SQLite in-memory), _encryption_key (подменяет YANDEX_TOKEN_ENCRYPTION_KEY) и user_factory
- test_yandex_music_service.py: тесты sync_favorite_artists (rate-limit, dedup, обработка ошибок)
- test_yandex_music_provider.py: тесты адаптера провайдера (artists_name, fallback, таймауты, ошибки auth)

Сценарии использования (быстро)

A) Регистрация и вход
1. POST /api/register с JSON {username,email,password,gender,...}
2. server -> register_user -> создание User -> возвращает access_token (JWT)
3. Клиент сохраняет token (localStorage) и использует для защищённых запросов

B) Подключение Яндекс.Музыки (Device Flow)
1. Клиент POST /api/yandex-music/connect (JWT)
2. Сервер вызывает auth_flow_manager.start(user_id) — запускает background thread
3. Сервер возвращает быстрый ответ со статусом (включая verification_url и user_code, когда они готовы)
4. Клиент показывает user_code и verification_url пользователю
5. Клиент опрашивает GET /api/yandex-music/connect/status пока статус не станет success
6. При success сервер забирает token через pop_token_if_ready и вызывает save_token(db,user_id,token)

C) Синхронизация любимых артистов
1. Клиент POST /api/yandex-music/sync (JWT)
2. Сервер вызывает sync_favorite_artists(db,user_id,force)
  - Дешифрует токен, вызывает provider.get_favorite_artists(access_token)
  - Добавляет новые Artist в БД и связывает их с User.favorite_artists
  - Обновляет last_synced_at и возвращает список добавленных артистов

Ошибки и обработка
- Невалидный токен -> YandexMusicAuthError -> фронтенду возвращается code 'reauth_required' (HTTP 409)
- Временные ошибки провайдера -> YandexMusicProviderError -> retry (с экспоненциальным backoff)
- Ошибки шифрования (ключа) -> EncryptionConfigError -> возвращается 'crypto_error'

Рекомендации и следующий шаг
- Документация: сохранить ARCHITECTURE.md (этот файл) в репозитории — сделано автоматически по запросу.
- Production:
  - Вынести auth flow state в Redis
  - Настроить Alembic-миграции
  - Хранить секреты в секрет-менеджере
- IDE (PyCharm): выбрать .venv как Project Interpreter и пометить папку backend как Sources Root

Хотите более детальный файл-по-файлу (с точными сигнатурами всех функций и примерами запросов/ответов для каждого эндпоинта) — создам отдельный документ API_REFERENCE.md. Напишите: "API_REFERENCE" чтобы я создал. Если всё подошло — закрою задачу.