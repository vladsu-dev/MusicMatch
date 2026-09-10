// База данных: SQLite через встроенный модуль node:sqlite (Node 22+).
// Файл БД лежит в server/data/app.db и создаётся при первом запуске.

import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(DIR, 'data');
fs.mkdirSync(DATA_DIR, { recursive: true });

export const db = new DatabaseSync(path.join(DATA_DIR, 'app.db'));

db.exec('PRAGMA journal_mode = WAL');
db.exec('PRAGMA foreign_keys = ON');

db.exec(`
  -- Аккаунты. Открытого email в базе нет: хранится шифротекст (email_enc)
  -- и слепой индекс (email_index) для поиска при входе.
  CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email_index   TEXT NOT NULL UNIQUE,
    email_enc     TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
  );

  -- Анкеты: имя и фото шифруются, жанр хранится открытым (нужен для подбора).
  CREATE TABLE IF NOT EXISTS profiles (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    name_enc   TEXT NOT NULL,
    photo_enc  TEXT NOT NULL,
    genre      TEXT NOT NULL,
    updated_at TEXT NOT NULL
  );

  -- Оценки анкет: одна строка на пару «кто → кого».
  CREATE TABLE IF NOT EXISTS swipes (
    from_user  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action     TEXT NOT NULL CHECK (action IN ('like', 'skip')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (from_user, to_user)
  );

  CREATE INDEX IF NOT EXISTS idx_swipes_to ON swipes(to_user, action);
`);

export const now = () => new Date().toISOString();
