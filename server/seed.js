// Демо-данные: несколько готовых анкет, чтобы ленту было чем листать.
// Запуск: npm run seed. Пароль у всех демо-аккаунтов — demo1234.
// Фото рисуются прямо здесь (виниловая пластинка в PNG) — интернет не нужен.

import zlib from 'node:zlib';
import { db, now } from './db.js';
import { hashPassword, encrypt, blindIndex } from './crypto.js';

/* ---------- минимальный генератор PNG ---------- */

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

const crc32 = (buf) => {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
};

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

// pixel(x, y) -> [r, g, b]
function makePng(width, height, pixel) {
  const raw = Buffer.alloc(height * (width * 3 + 1));
  let offset = 0;
  for (let y = 0; y < height; y++) {
    raw[offset++] = 0; // тип фильтра строки
    for (let x = 0; x < width; x++) {
      const [r, g, b] = pixel(x, y);
      raw[offset++] = r;
      raw[offset++] = g;
      raw[offset++] = b;
    }
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // 8 бит на канал
  ihdr[9] = 2; // truecolor RGB

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const mix = (a, b, t) => a.map((value, i) => Math.round(value + (b[i] - value) * t));

// Пластинка на цветном фоне — заглушка вместо реальной фотографии.
function vinylPhoto(color) {
  const W = 600;
  const H = 750;
  const cx = W / 2;
  const cy = H * 0.45;
  const png = makePng(W, H, (x, y) => {
    const dx = x - cx;
    const dy = y - cy;
    const distance = Math.hypot(dx, dy);
    const backdrop = mix(color, [255, 255, 255], (x / W) * 0.25 + (y / H) * 0.35);
    if (distance > 235) return backdrop;
    if (distance < 22) return [242, 239, 234]; // отверстие
    if (distance < 78) return mix(color, [0, 0, 0], 0.15); // этикетка
    const groove = Math.sin(distance / 3.4) * 0.5 + 0.5;
    return mix([26, 24, 22], [64, 60, 56], groove * 0.75);
  });
  return `data:image/png;base64,${png.toString('base64')}`;
}

/* ---------- сами анкеты ---------- */

const DEMO = [
  { name: 'Аня', genre: 'Инди', color: [232, 118, 92] },
  { name: 'Марк', genre: 'Рок', color: [78, 96, 148] },
  { name: 'Лиза', genre: 'Электроника', color: [104, 168, 160] },
  { name: 'Тимур', genre: 'Хип-хоп', color: [176, 140, 84] },
  { name: 'Соня', genre: 'Джаз', color: [140, 108, 168] },
  { name: 'Женя', genre: 'Классика', color: [120, 144, 96] },
  { name: 'Ким', genre: 'Инди', color: [204, 132, 132] },
  { name: 'Олег', genre: 'Метал', color: [92, 92, 100] },
];

let created = 0;

for (const [i, person] of DEMO.entries()) {
  const email = `demo${i + 1}@accord.local`;
  const index = blindIndex(email);
  if (db.prepare('SELECT 1 FROM users WHERE email_index = ?').get(index)) continue;

  const info = db
    .prepare(
      'INSERT INTO users (email_index, email_enc, password_hash, created_at) VALUES (?, ?, ?, ?)'
    )
    .run(index, encrypt(email), hashPassword('demo1234'), now());

  db.prepare(
    'INSERT INTO profiles (user_id, name_enc, photo_enc, genre, updated_at) VALUES (?, ?, ?, ?, ?)'
  ).run(
    info.lastInsertRowid,
    encrypt(person.name),
    encrypt(vinylPhoto(person.color)),
    person.genre,
    now()
  );
  created++;
}

console.log(
  created ? `Добавлено демо-анкет: ${created} (пароль demo1234)` : 'Демо-анкеты уже в базе'
);
