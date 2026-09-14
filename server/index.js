import { resolve } from 'node:path';
import { createPool } from './db.js';
import { createApp } from './app.js';

const pool = createPool(process.env.DATABASE_URL);
const production = process.env.NODE_ENV === 'production';
const app = createApp({
  pool, secret: process.env.JWT_SECRET,
  origin: process.env.APP_ORIGIN || 'http://127.0.0.1:5173',
  production, staticDir: production ? resolve('dist') : undefined,
});
await pool.query('SELECT 1 FROM schema_migrations LIMIT 1');
const server = app.listen(Number(process.env.PORT || 3001), '127.0.0.1', () => {
  console.log('MusicMatch API запущен на http://127.0.0.1:' + (process.env.PORT || 3001));
});
const cleanup = setInterval(() => {
  pool.query('DELETE FROM sessions WHERE expires_at <= now()').catch((error) => console.error('Session cleanup:', error.code));
}, 60 * 60 * 1000);
cleanup.unref();
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => {
    clearInterval(cleanup);
    server.close(async () => { await pool.end(); process.exit(0); });
    setTimeout(() => process.exit(1), 10_000).unref();
  });
}
