from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
EXAMPLE_PATH = ROOT / ".env.example"


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def render(values: dict[str, str]) -> str:
    order = ["DATABASE_URL", "DB_PORT", "DJANGO_SECRET_KEY", "JWT_SECRET", "DJANGO_DEBUG", "APP_ORIGIN", "ALLOWED_HOSTS"]
    lines = []
    for key in order:
        if key in values:
            lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(order)):
        lines.append(f"{key}={values[key]}")
    return "\n".join(lines) + "\n"


def random_secret() -> str:
    return secrets.token_urlsafe(48)


def main() -> None:
    base = parse_env(EXAMPLE_PATH.read_text(encoding="utf-8")) if EXAMPLE_PATH.exists() else {}
    current = parse_env(ENV_PATH.read_text(encoding="utf-8")) if ENV_PATH.exists() else {}
    values = {**base, **current}

    values.setdefault("DATABASE_URL", "postgres://musicmatch:musicmatch_password@127.0.0.1:5433/musicmatch")
    parsed = urlparse(values["DATABASE_URL"])
    if parsed.port:
        values["DB_PORT"] = str(parsed.port)
    else:
        values.setdefault("DB_PORT", "5433")
    if values.get("APP_ORIGIN") == "http://127.0.0.1:5173":
        values["APP_ORIGIN"] = "http://127.0.0.1:8000"
    values.setdefault("APP_ORIGIN", "http://127.0.0.1:8000")
    values.setdefault("ALLOWED_HOSTS", "127.0.0.1,localhost")
    values.setdefault("DJANGO_DEBUG", "1")

    for key in ["DJANGO_SECRET_KEY", "JWT_SECRET"]:
        if len(values.get(key, "")) < 32 or values[key].startswith("replace-with"):
            values[key] = random_secret()

    ENV_PATH.write_text(render(values), encoding="utf-8")
    print(".env готов")
    print(f"DB_PORT={values['DB_PORT']}")
    print(f"APP_ORIGIN={values['APP_ORIGIN']}")


if __name__ == "__main__":
    main()
