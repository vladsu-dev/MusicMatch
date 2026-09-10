// HTTP API приложения «Аккорд».
// Запуск: npm run server (или npm run dev вместе с клиентом).

import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { db, now } from './db.js';
import { GENRES } from './genres.js';
import {
  hashPassword,
  verifyPassword,
  encrypt,
  decrypt,
  blindIndex,
  signToken,
  verifyToken,
} from './crypto.js';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.PORT || 3001;

const app = express();
app.use(express.json({ limit: '8mb' })); // фото приходит как data URL

/* ---------- вспомогательное ---------- */

const fail = (res, code, message) => res.status(code).json({ error: message });

// Достаёт пользователя из заголовка Authorization: Bearer <token>.
function auth(req, res, next) {
  const token = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  const payload = verifyToken(token);
  if (!payload) return fail(res, 401, 'Требуется вход в аккаунт');
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(payload.uid);
  if (!user) return fail(res, 401, 'Аккаунт не найден');
  req.user = user;
  next();
}

const publicUser = (user) => ({
  id: user.id,
  email: decrypt(user.email_enc),
  createdAt: user.created_at,
});

function getProfile(userId) {
  const row = db.prepare('SELECT * FROM profiles WHERE user_id = ?').get(userId);
  if (!row) return null;
  return {
    userId: row.user_id,
    name: decrypt(row.name_enc),
    photo: decrypt(row.photo_enc),
    genre: row.genre,
    updatedAt: row.updated_at,
  };
}

const isValidEmail = (v) => typeof v === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
const isValidPhoto = (v) =>
  typeof v === 'string' &&
  /^data:image\/(png|jpe?g|webp|gif);base64,/.test(v) &&
  v.length < 6000000;

/* ---------- справочник ---------- */

app.get('/api/genres', (_req, res) => res.json({ genres: GENRES }));

/* ---------- регистрация и вход ---------- */

app.post('/api/register', (req, res) => {
  const { email, password } = req.body || {};
  if (!isValidEmail(email)) return fail(res, 400, 'Введите корректный email');
  if (typeof password !== 'string' || password.length < 6)
    return fail(res, 400, 'Пароль должен быть не короче 6 символов');

  const index = blindIndex(email);
  if (db.prepare('SELECT 1 FROM users WHERE email_index = ?').get(index))
    return fail(res, 409, 'Такой email уже зарегистрирован');

  const info = db
    .prepare(
      'INSERT INTO users (email_index, email_enc, password_hash, created_at) VALUES (?, ?, ?, ?)'
    )
    .run(index, encrypt(email.trim()), hashPassword(password), now());

  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(info.lastInsertRowid);
  res
    .status(201)
    .json({ token: signToken({ uid: user.id }), user: publicUser(user), profile: null });
});

app.post('/api/login', (req, res) => {
  const { email, password } = req.body || {};
  if (!isValidEmail(email) || typeof password !== 'string')
    return fail(res, 400, 'Введите email и пароль');

  const user = db.prepare('SELECT * FROM users WHERE email_index = ?').get(blindIndex(email));
  if (!user || !verifyPassword(password, user.password_hash))
    return fail(res, 401, 'Неверный email или пароль');

  res.json({
    token: signToken({ uid: user.id }),
    user: publicUser(user),
    profile: getProfile(user.id),
  });
});

/* ---------- текущий пользователь и анкета ---------- */

app.get('/api/me', auth, (req, res) => {
  res.json({ user: publicUser(req.user), profile: getProfile(req.user.id) });
});

app.put('/api/profile', auth, (req, res) => {
  const { name, genre, photo } = req.body || {};
  if (typeof name !== 'string' || name.trim().length < 2)
    return fail(res, 400, 'Укажите имя (минимум 2 символа)');
  if (!GENRES.includes(genre)) return fail(res, 400, 'Выберите музыкальный жанр из списка');
  if (!isValidPhoto(photo)) return fail(res, 400, 'Загрузите фото (изображение до 6 МБ)');

  db.prepare(
    `INSERT INTO profiles (user_id, name_enc, photo_enc, genre, updated_at)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(user_id) DO UPDATE SET
       name_enc = excluded.name_enc,
       photo_enc = excluded.photo_enc,
       genre = excluded.genre,
       updated_at = excluded.updated_at`
  ).run(req.user.id, encrypt(name.trim()), encrypt(photo), genre, now());

  res.json({ profile: getProfile(req.user.id) });
});

/* ---------- лента анкет ---------- */

app.get('/api/feed', auth, (req, res) => {
  const me = getProfile(req.user.id);
  if (!me) return fail(res, 403, 'Сначала заполните свою анкету');

  // Показываем тех, кого пользователь ещё не оценивал.
  // Совпадение по жанру поднимает анкету выше — в этом и смысл приложения.
  const rows = db
    .prepare(
      `SELECT p.* FROM profiles p
       WHERE p.user_id != ?
         AND p.user_id NOT IN (SELECT to_user FROM swipes WHERE from_user = ?)
       ORDER BY (p.genre = ?) DESC, p.updated_at DESC`
    )
    .all(req.user.id, req.user.id, me.genre);

  res.json({
    feed: rows.map((row) => ({
      userId: row.user_id,
      name: decrypt(row.name_enc),
      photo: decrypt(row.photo_enc),
      genre: row.genre,
      sameGenre: row.genre === me.genre,
    })),
  });
});

/* ---------- лайк / пропуск ---------- */

app.post('/api/swipe', auth, (req, res) => {
  const { targetId, action } = req.body || {};
  if (!['like', 'skip'].includes(action)) return fail(res, 400, 'Некорректное действие');
  if (!Number.isInteger(targetId) || targetId === req.user.id)
    return fail(res, 400, 'Некорректная анкета');
  if (!db.prepare('SELECT 1 FROM profiles WHERE user_id = ?').get(targetId))
    return fail(res, 404, 'Анкета не найдена');

  db.prepare(
    `INSERT INTO swipes (from_user, to_user, action, created_at) VALUES (?, ?, ?, ?)
     ON CONFLICT(from_user, to_user) DO UPDATE SET
       action = excluded.action, created_at = excluded.created_at`
  ).run(req.user.id, targetId, action, now());

  // Взаимный лайк — совпадение.
  const mutual =
    action === 'like' &&
    !!db
      .prepare("SELECT 1 FROM swipes WHERE from_user = ? AND to_user = ? AND action = 'like'")
      .get(targetId, req.user.id);

  res.json({ match: mutual, profile: mutual ? getProfile(targetId) : null });
});

app.get('/api/matches', auth, (req, res) => {
  const rows = db
    .prepare(
      `SELECT p.* FROM swipes mine
       JOIN swipes theirs ON theirs.from_user = mine.to_user AND theirs.to_user = mine.from_user
       JOIN profiles p ON p.user_id = mine.to_user
       WHERE mine.from_user = ? AND mine.action = 'like' AND theirs.action = 'like'
       ORDER BY theirs.created_at DESC`
    )
    .all(req.user.id);

  res.json({
    matches: rows.map((row) => ({
      userId: row.user_id,
      name: decrypt(row.name_enc),
      photo: decrypt(row.photo_enc),
      genre: row.genre,
    })),
  });
});

/* ---------- собранный клиент (после npm run build) ---------- */

const dist = path.join(DIR, '..', 'client', 'dist');
if (fs.existsSync(dist)) {
  app.use(express.static(dist));
  app.get(/^(?!\/api).*/, (_req, res) => res.sendFile(path.join(dist, 'index.html')));
}

app.listen(PORT, () => console.log(`API готов: http://localhost:${PORT}`));
