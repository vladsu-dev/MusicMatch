from datetime import timedelta

GENRES = [
    "Поп",
    "Рок",
    "Хип-хоп",
    "Электронная",
    "Инди",
    "Джаз",
    "Классика",
    "R&B",
    "Метал",
    "Панк",
    "Фолк",
    "Кантри",
    "Латина",
    "K-pop",
    "Саундтреки",
    "Регги",
    "Блюз",
    "Другое",
]

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
ACCESS_COOKIE = "mm_py_access"
REFRESH_COOKIE = "mm_py_refresh"
JWT_ISSUER = "musicmatch-python"
JWT_AUDIENCE = "musicmatch-web"
