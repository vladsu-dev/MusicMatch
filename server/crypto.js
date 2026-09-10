// Криптография приложения: хеширование паролей, шифрование данных в БД,
// слепой индекс для поиска по email и подпись сессионных токенов.
// Используется только встроенный модуль node:crypto — внешних зависимостей нет.

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const KEY_FILE = path.join(DIR, 'data', 'master.key');

// Мастер-ключ: берётся из переменной окружения либо генерируется один раз
// и сохраняется на диск (в реальном проекте — секрет-менеджер, не файл).
function loadMasterKey() {
  if (process.env.MASTER_KEY) return Buffer.from(process.env.MASTER_KEY, 'hex');
  if (fs.existsSync(KEY_FILE)) return Buffer.from(fs.readFileSync(KEY_FILE, 'utf8').trim(), 'hex');
  const key = crypto.randomBytes(32);
  fs.mkdirSync(path.dirname(KEY_FILE), { recursive: true });
  fs.writeFileSync(KEY_FILE, key.toString('hex'), { mode: 0o600 });
  return key;
}

const MASTER_KEY = loadMasterKey();
// Из мастер-ключа выводим отдельные ключи под каждую задачу.
const derive = (info) => crypto.hkdfSync('sha256', MASTER_KEY, Buffer.alloc(0), Buffer.from(info), 32);
const DATA_KEY = Buffer.from(derive('data-encryption'));
const INDEX_KEY = Buffer.from(derive('blind-index'));
const TOKEN_KEY = Buffer.from(derive('session-token'));

/* ---------- Пароли: scrypt + случайная соль ---------- */

const SCRYPT = { N: 16384, r: 8, p: 1, keylen: 64 };

export function hashPassword(password) {
  const salt = crypto.randomBytes(16);
  const hash = crypto.scryptSync(password, salt, SCRYPT.keylen, SCRYPT);
  return `scrypt$${SCRYPT.N}$${salt.toString('hex')}$${hash.toString('hex')}`;
}

export function verifyPassword(password, stored) {
  try {
    const [scheme, N, saltHex, hashHex] = String(stored).split('$');
    if (scheme !== 'scrypt') return false;
    const hash = Buffer.from(hashHex, 'hex');
    const candidate = crypto.scryptSync(password, Buffer.from(saltHex, 'hex'), hash.length, {
      ...SCRYPT,
      N: Number(N),
    });
    return crypto.timingSafeEqual(hash, candidate);
  } catch {
    return false;
  }
}

/* ---------- Шифрование полей анкеты: AES-256-GCM ---------- */

export function encrypt(plain) {
  if (plain === null || plain === undefined) return null;
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', DATA_KEY, iv);
  const data = Buffer.concat([cipher.update(String(plain), 'utf8'), cipher.final()]);
  // формат: iv.tag.ciphertext (base64)
  return [iv, cipher.getAuthTag(), data].map((b) => b.toString('base64')).join('.');
}

export function decrypt(blob) {
  if (!blob) return null;
  try {
    const [ivB64, tagB64, dataB64] = String(blob).split('.');
    const decipher = crypto.createDecipheriv('aes-256-gcm', DATA_KEY, Buffer.from(ivB64, 'base64'));
    decipher.setAuthTag(Buffer.from(tagB64, 'base64'));
    return Buffer.concat([
      decipher.update(Buffer.from(dataB64, 'base64')),
      decipher.final(),
    ]).toString('utf8');
  } catch {
    return null;
  }
}

// Слепой индекс: email в БД лежит зашифрованным, а искать по нему нужно.
// Детерминированный HMAC позволяет найти запись, не храня открытый адрес.
export function blindIndex(value) {
  return crypto.createHmac('sha256', INDEX_KEY).update(String(value).trim().toLowerCase()).digest('hex');
}

/* ---------- Сессионные токены (подписанные HMAC-SHA256) ---------- */

const b64url = (buf) => Buffer.from(buf).toString('base64url');
const TOKEN_TTL_MS = 7 * 24 * 60 * 60 * 1000;

export function signToken(payload) {
  const body = b64url(JSON.stringify({ ...payload, exp: Date.now() + TOKEN_TTL_MS }));
  const sig = crypto.createHmac('sha256', TOKEN_KEY).update(body).digest('base64url');
  return `${body}.${sig}`;
}

export function verifyToken(token) {
  try {
    const [body, sig] = String(token).split('.');
    if (!body || !sig) return null;
    const expected = crypto.createHmac('sha256', TOKEN_KEY).update(body).digest('base64url');
    const a = Buffer.from(sig);
    const b = Buffer.from(expected);
    if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
    const payload = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'));
    if (!payload.exp || payload.exp < Date.now()) return null;
    return payload;
  } catch {
    return null;
  }
}
