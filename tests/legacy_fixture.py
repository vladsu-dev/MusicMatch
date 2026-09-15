from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

LEGACY_SCHEMA_SQL = """
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS decisions CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS genres CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS schema_migrations CASCADE;
CREATE TABLE schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE users (id uuid PRIMARY KEY, email varchar(254) NOT NULL UNIQUE, password_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT users_email_lower_check CHECK (email = lower(email)));
CREATE TABLE genres (name varchar(40) PRIMARY KEY);
INSERT INTO genres (name) VALUES ('Поп'), ('Рок'), ('Хип-хоп');
CREATE TABLE profiles (user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, name varchar(40) NOT NULL, genre varchar(40) NOT NULL REFERENCES genres(name), photo text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT profiles_name_length_check CHECK (char_length(name) BETWEEN 2 AND 40), CONSTRAINT profiles_photo_size_check CHECK (octet_length(photo) <= 1400000));
CREATE INDEX profiles_genre_idx ON profiles (genre);
CREATE TABLE sessions (id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, refresh_hash char(64) NOT NULL UNIQUE, expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX sessions_user_idx ON sessions (user_id);
CREATE INDEX sessions_expiry_idx ON sessions (expires_at);
CREATE TABLE decisions (user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, target_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, action varchar(4) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (user_id, target_id), CONSTRAINT decisions_action_check CHECK (action IN ('like', 'skip')), CONSTRAINT decisions_not_self_check CHECK (user_id <> target_id));
CREATE TABLE matches (id uuid PRIMARY KEY, user_low uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, user_high uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT matches_order_check CHECK (user_low < user_high), CONSTRAINT matches_pair_unique UNIQUE (user_low, user_high));
CREATE INDEX matches_high_idx ON matches (user_high);
CREATE TABLE messages (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, match_id uuid NOT NULL REFERENCES matches(id) ON DELETE CASCADE, sender_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE, text varchar(2000) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT messages_text_length_check CHECK (char_length(trim(text)) BETWEEN 1 AND 2000));
CREATE INDEX messages_match_id_idx ON messages (match_id, id DESC);
"""

USER_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
MATCH_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SESSION_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
PHOTO = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2w=="


def legacy_hash(password: str, salt_hex: str = "0123456789abcdef0123456789abcdef") -> str:
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt_hex.encode("utf-8"), n=16384, r=8, p=1, dklen=64)
    return f"{salt_hex}:{digest.hex()}"


def seed_sql() -> str:
    password_hash = legacy_hash("old-password")
    return f"""
    INSERT INTO users (id, email, password_hash) VALUES
      ('{USER_A}', 'old-a@example.com', '{password_hash}'),
      ('{USER_B}', 'old-b@example.com', '{password_hash}');
    INSERT INTO profiles (user_id, name, genre, photo) VALUES
      ('{USER_A}', 'Old Alice', 'Рок', '{PHOTO}'),
      ('{USER_B}', 'Old Bob', 'Рок', '{PHOTO}');
    INSERT INTO sessions (id, user_id, refresh_hash, expires_at) VALUES
      ('{SESSION_ID}', '{USER_A}', repeat('a', 64), now() + interval '30 days');
    INSERT INTO decisions (user_id, target_id, action) VALUES
      ('{USER_A}', '{USER_B}', 'like'),
      ('{USER_B}', '{USER_A}', 'like');
    INSERT INTO matches (id, user_low, user_high) VALUES ('{MATCH_ID}', '{USER_A}', '{USER_B}');
    INSERT INTO messages (match_id, sender_id, text) VALUES ('{MATCH_ID}', '{USER_A}', 'old hello');
    INSERT INTO schema_migrations (name) VALUES ('001_initial.sql');
    """
