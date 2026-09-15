from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg
from django.test import Client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.legacy_fixture import LEGACY_SCHEMA_SQL, MATCH_ID, seed_sql


def snapshot(conn):
    queries = {
        "users": "SELECT id, email, password_hash, created_at FROM users ORDER BY id",
        "profiles": "SELECT user_id, name, genre, photo, updated_at FROM profiles ORDER BY user_id",
        "sessions": "SELECT id, user_id, refresh_hash, expires_at, created_at FROM sessions ORDER BY id",
        "decisions": "SELECT user_id, target_id, action, created_at FROM decisions ORDER BY user_id, target_id",
        "matches": "SELECT id, user_low, user_high, created_at FROM matches ORDER BY id",
        "messages": "SELECT id, match_id, sender_id, text, created_at FROM messages ORDER BY id",
        "schema_migrations": "SELECT name, applied_at FROM schema_migrations ORDER BY name",
    }
    data = {}
    with conn.cursor() as cur:
        for table, query in queries.items():
            cur.execute(query)
            data[table] = cur.fetchall()
    return data


def main() -> None:
    db_url = os.environ.get("LEGACY_DATABASE_URL")
    if not db_url:
        print("LEGACY_DATABASE_URL is not set; skipping")
        return
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env.setdefault("DJANGO_SECRET_KEY", "legacy-test-secret-key-000000000000000")
    env.setdefault("JWT_SECRET", "legacy-jwt-secret-key-000000000000000000")
    env.setdefault("DJANGO_DEBUG", "1")
    env.setdefault("APP_ORIGIN", "http://127.0.0.1:8000")
    env.setdefault("ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(LEGACY_SCHEMA_SQL)
        conn.execute(seed_sql())
        before = snapshot(conn)

    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=env, check=True)
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=env, check=True)

    with psycopg.connect(db_url) as conn:
        after = snapshot(conn)
    for table in before:
        assert before[table] == after[table], f"{table} changed during migration"

    os.environ.update(env)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    client = Client()
    response = client.post("/login/", {"email": "old-a@example.com", "password": "old-password"})
    assert response.status_code == 302, response.content[:200]
    response = client.get("/matches/")
    assert b"Old Bob" in response.content
    response = client.post(f"/chat/{MATCH_ID}/", {"text": "new python hello", "submission_id": "55555555-5555-5555-5555-555555555555"})
    assert response.status_code == 302
    print("legacy upgrade passed")


if __name__ == "__main__":
    main()
