import express from 'express';
import cookieParser from 'cookie-parser';
import helmet from 'helmet';
import { rateLimit } from 'express-rate-limit';
import { randomUUID } from 'node:crypto';
import { resolve } from 'node:path';
import { transaction } from './db.js';
import { credentials, createSecurity, fail, hashPassword, verifyPassword, hashToken, refreshToken, UUID_RE } from './security.js';
import { GENRES } from '../src/data/genres.js';

const REFRESH_MS = 30 * 24 * 60 * 60 * 1000;
const uuid = (value) => { if (!UUID_RE.test(value)) fail(400, 'Некорректный идентификатор'); return value.toLowerCase(); };
const profileSQL = 'SELECT user_id AS id, name, genre, photo FROM profiles WHERE user_id=$1';

export function createApp({ pool, secret, origin, production = false, staticDir }) {
  const security = createSecurity(secret);
  if (!origin || new URL(origin).origin !== origin) throw new Error('APP_ORIGIN должен содержать точный origin без завершающего /');
  if (production && !origin.startsWith('https://')) throw new Error('В production APP_ORIGIN должен использовать HTTPS');
  const app = express();
  app.disable('x-powered-by');
  app.use(helmet({
    contentSecurityPolicy: { directives: { 'img-src': ["'self'", 'data:'], 'upgrade-insecure-requests': production ? [] : null } },
  }));
  app.use('/api', (req, res, next) => {
    res.set('Cache-Control', 'no-store');
    // Every browser mutation must originate from the configured UI.
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method) && req.get('Origin') !== origin) {
      return res.status(403).json({ error: 'Недопустимый источник запроса' });
    }
    next();
  });
  const rateError = { error: 'Слишком много запросов. Попробуйте позже.' };
  app.use('/api', rateLimit({ windowMs: 60_000, limit: 300, standardHeaders: 'draft-8', legacyHeaders: false, message: rateError }));
  app.use(express.json({ limit: '2mb' }));
  app.use(cookieParser());
  const authLimit = rateLimit({ windowMs: 15 * 60_000, limit: 30, standardHeaders: 'draft-8', legacyHeaders: false, message: rateError });
  const cookieOptions = { httpOnly: true, secure: production, sameSite: 'strict', path: '/api' };
  function setCookies(res, userId, sessionId, refresh, expiresAt) {
    res.cookie('mm_access', security.sign(userId, sessionId), { ...cookieOptions, maxAge: 15 * 60_000 });
    res.cookie('mm_refresh', refresh, { ...cookieOptions, expires: new Date(expiresAt) });
  }
  function clearCookies(res) {
    res.clearCookie('mm_access', cookieOptions);
    res.clearCookie('mm_refresh', cookieOptions);
  }
  async function newSession(client, userId) {
    const sessionId = randomUUID();
    const refresh = refreshToken();
    const expiresAt = new Date(Date.now() + REFRESH_MS);
    await client.query('INSERT INTO sessions(id,user_id,refresh_hash,expires_at) VALUES ($1,$2,$3,$4)', [sessionId, userId, hashToken(refresh), expiresAt]);
    return { sessionId, refresh, expiresAt };
  }
  async function identity(userId) {
    const user = (await pool.query('SELECT id,email FROM users WHERE id=$1', [userId])).rows[0];
    const profile = (await pool.query(profileSQL, [userId])).rows[0] || null;
    return { user, profile };
  }
  async function auth(req, res, next) {
    let claims;
    try { claims = security.verify(req.cookies.mm_access); }
    catch { return res.status(401).json({ error: 'Войдите в аккаунт' }); }
    const session = await pool.query('SELECT 1 FROM sessions WHERE id=$1 AND user_id=$2 AND expires_at>now()', [claims.sid, claims.sub]);
    if (!session.rowCount) return res.status(401).json({ error: 'Сессия завершена. Войдите снова.' });
    req.userId = claims.sub;
    req.sessionId = claims.sid;
    next();
  }
  async function requireProfile(req, res, next) {
    if (!(await pool.query('SELECT 1 FROM profiles WHERE user_id=$1', [req.userId])).rowCount) fail(409, 'Сначала заполните анкету');
    next();
  }
  async function member(req) {
    const matchId = uuid(req.params.id);
    const found = await pool.query('SELECT 1 FROM matches WHERE id=$1 AND (user_low=$2 OR user_high=$2)', [matchId, req.userId]);
    if (!found.rowCount) fail(404, 'Совпадение не найдено');
    return matchId;
  }

  app.get('/api/health', async (req, res) => {
    await pool.query('SELECT 1');
    res.json({ status: 'ok' });
  });
  app.post('/api/auth/register', authLimit, async (req, res) => {
    const { email, password } = credentials(req.body);
    const passwordHash = await hashPassword(password);
    const userId = randomUUID();
    let session;
    try {
      session = await transaction(pool, async (client) => {
        await client.query('INSERT INTO users(id,email,password_hash) VALUES ($1,$2,$3)', [userId, email, passwordHash]);
        return newSession(client, userId);
      });
    } catch (error) {
      if (error.code === '23505') fail(409, 'Аккаунт с таким email уже существует');
      throw error;
    }
    setCookies(res, userId, session.sessionId, session.refresh, session.expiresAt);
    res.status(201).json({ user: { id: userId, email }, profile: null });
  });
  // A fixed dummy hash keeps unknown-user password checks comparable in cost.
  const dummyHash = '00000000000000000000000000000000:' + '00'.repeat(64);
  app.post('/api/auth/login', authLimit, async (req, res) => {
    const { email, password } = credentials(req.body);
    const user = (await pool.query('SELECT id,password_hash FROM users WHERE email=$1', [email])).rows[0];
    const valid = await verifyPassword(password, user?.password_hash || dummyHash);
    if (!user || !valid) fail(401, 'Неверный email или пароль');
    const session = await transaction(pool, (client) => newSession(client, user.id));
    setCookies(res, user.id, session.sessionId, session.refresh, session.expiresAt);
    res.json(await identity(user.id));
  });
  app.post('/api/auth/refresh', async (req, res) => {
    const token = req.cookies.mm_refresh;
    if (typeof token !== 'string' || !/^[0-9a-f]{64}$/.test(token)) fail(401, 'Войдите снова');
    const session = await transaction(pool, async (client) => {
      const old = (await client.query('SELECT * FROM sessions WHERE refresh_hash=$1 AND expires_at>now() FOR UPDATE', [hashToken(token)])).rows[0];
      if (!old) fail(401, 'Сессия завершена. Войдите снова.');
      const refresh = refreshToken();
      await client.query('UPDATE sessions SET refresh_hash=$1 WHERE id=$2', [hashToken(refresh), old.id]);
      return { ...old, refresh };
    });
    setCookies(res, session.user_id, session.id, session.refresh, session.expires_at);
    res.json({ ok: true });
  });
  app.post('/api/auth/logout', async (req, res) => {
    // Also revoke via the refresh cookie when the access JWT has expired.
    let claims;
    try { claims = security.verify(req.cookies.mm_access); } catch {}
    const token = req.cookies.mm_refresh;
    await pool.query('DELETE FROM sessions WHERE id=$1 OR refresh_hash=$2', [claims?.sid || null, typeof token === 'string' ? hashToken(token) : null]);
    clearCookies(res);
    res.status(204).end();
  });
  app.get('/api/auth/session', auth, async (req, res) => res.json(await identity(req.userId)));
  app.get('/api/genres', (req, res) => res.json({ genres: GENRES }));
  app.put('/api/me/profile', auth, async (req, res) => {
    const name = typeof req.body?.name === 'string' ? req.body.name.trim() : '';
    const genre = req.body?.genre;
    const photo = req.body?.photo;
    if (name.length < 2 || name.length > 40) fail(400, 'Имя должно содержать от 2 до 40 символов');
    if (!GENRES.includes(genre)) fail(400, 'Выберите жанр из списка');
    if (typeof photo !== 'string' || photo.length > 1_400_000 || !/^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(photo)) fail(400, 'Загрузите JPEG-фото размером до 1 МБ');
    const bytes = Buffer.from(photo.split(',')[1], 'base64');
    if (bytes.length > 1_048_576 || bytes[0] !== 255 || bytes[1] !== 216 || bytes[2] !== 255 || bytes.at(-2) !== 255 || bytes.at(-1) !== 217) fail(400, 'Некорректное JPEG-фото');
    await pool.query('INSERT INTO profiles(user_id,name,genre,photo) VALUES ($1,$2,$3,$4) ON CONFLICT(user_id) DO UPDATE SET name=EXCLUDED.name,genre=EXCLUDED.genre,photo=EXCLUDED.photo,updated_at=now()', [req.userId, name, genre, photo]);
    res.json({ profile: (await pool.query(profileSQL, [req.userId])).rows[0] });
  });
  app.get('/api/me/stats', auth, async (req, res) => {
    const viewed = (await pool.query('SELECT count(*)::int AS count FROM decisions WHERE user_id=$1', [req.userId])).rows[0].count;
    const matches = (await pool.query('SELECT count(*)::int AS count FROM matches WHERE user_low=$1 OR user_high=$1', [req.userId])).rows[0].count;
    res.json({ viewed, matches });
  });
  app.get('/api/feed', auth, requireProfile, async (req, res) => {
    const result = await pool.query(`
      SELECT p.user_id AS id,p.name,p.genre,p.photo,(p.genre=me.genre) AS "sameGenre"
      FROM profiles p JOIN profiles me ON me.user_id=$1
      WHERE p.user_id<>$1 AND NOT EXISTS (
        SELECT 1 FROM decisions d WHERE d.user_id=$1 AND d.target_id=p.user_id
      )
      ORDER BY (p.genre=me.genre) DESC,p.user_id LIMIT 20`, [req.userId]);
    res.json({ profiles: result.rows });
  });
  app.post('/api/feed/reset', auth, requireProfile, async (req, res) => {
    // Keep likes, matches and conversations; only revisit skipped profiles.
    await pool.query("DELETE FROM decisions WHERE user_id=$1 AND action='skip'", [req.userId]);
    res.status(204).end();
  });
  app.post('/api/decisions/:id', auth, requireProfile, async (req, res) => {
    const targetId = uuid(req.params.id);
    const action = req.body?.action;
    if (targetId === req.userId || !['like', 'skip'].includes(action)) fail(400, 'Некорректная оценка анкеты');
    const pair = [req.userId, targetId].sort();
    const match = await transaction(pool, async (client) => {
      // Serialize both directions of a pair so simultaneous likes cannot miss a match.
      await client.query('SELECT pg_advisory_xact_lock(hashtextextended($1,0))', [pair.join(':')]);
      if (!(await client.query('SELECT 1 FROM profiles WHERE user_id=$1', [targetId])).rowCount) fail(404, 'Анкета не найдена');
      await client.query('INSERT INTO decisions(user_id,target_id,action) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING', [req.userId, targetId, action]);
      const likes = await client.query("SELECT 1 FROM decisions WHERE user_id=$1 AND target_id=$2 AND action='like' UNION ALL SELECT 1 FROM decisions WHERE user_id=$2 AND target_id=$1 AND action='like'", pair);
      if (likes.rowCount !== 2) return null;
      await client.query('INSERT INTO matches(id,user_low,user_high) VALUES ($1,$2,$3) ON CONFLICT(user_low,user_high) DO NOTHING', [randomUUID(), ...pair]);
      return (await client.query('SELECT p.user_id AS id,p.name,p.genre,p.photo,m.id AS "matchId" FROM matches m JOIN profiles p ON p.user_id=$3 WHERE m.user_low=$1 AND m.user_high=$2', [...pair, targetId])).rows[0];
    });
    res.json({ match });
  });
  app.get('/api/matches', auth, async (req, res) => {
    const result = await pool.query(`
      SELECT p.user_id AS id,p.name,p.genre,p.photo,m.id AS "matchId"
      FROM matches m JOIN profiles p ON p.user_id=CASE WHEN m.user_low=$1 THEN m.user_high ELSE m.user_low END
      WHERE m.user_low=$1 OR m.user_high=$1 ORDER BY m.created_at DESC,m.id`, [req.userId]);
    res.json({ matches: result.rows });
  });
  app.get('/api/matches/:id/messages', auth, async (req, res) => {
    const matchId = await member(req);
    const before = req.query.before;
    const after = req.query.after;
    if (after !== undefined && (typeof after !== 'string' || !/^[1-9][0-9]{0,18}$/.test(after) || BigInt(after) > 9223372036854775807n)) fail(400, 'Некорректный курсор');
    if (before !== undefined && after !== undefined) fail(400, 'Укажите только один курсор');
    if (before !== undefined && (typeof before !== 'string' || !/^[1-9][0-9]{0,18}$/.test(before) || BigInt(before) > 9223372036854775807n)) fail(400, 'Некорректный курсор');
    if (after) {
      const rows = (await pool.query('SELECT id,sender_id AS "senderId",text,created_at AS "createdAt" FROM messages WHERE match_id=$1 AND id>$2 ORDER BY id LIMIT 51', [matchId, after])).rows;
      return res.json({ messages: rows.slice(0,50), hasMore: rows.length > 50 });
    }
    const rows = (await pool.query(`
      SELECT id,sender_id AS "senderId",text,created_at AS "createdAt"
      FROM messages WHERE match_id=$1 AND ($2::bigint IS NULL OR id<$2)
      ORDER BY id DESC LIMIT 51`, [matchId, before || null])).rows;
    res.json({ messages: rows.slice(0,50).reverse(), hasMore: rows.length > 50 });
  });
  app.post('/api/matches/:id/messages', auth, async (req, res) => {
    const matchId = await member(req);
    const text = typeof req.body?.text === 'string' ? req.body.text.trim() : '';
    if (!text || text.length > 2000) fail(400, 'Сообщение должно содержать от 1 до 2000 символов');
    const message = (await pool.query('INSERT INTO messages(match_id,sender_id,text) VALUES ($1,$2,$3) RETURNING id,sender_id AS "senderId",text,created_at AS "createdAt"', [matchId, req.userId, text])).rows[0];
    res.status(201).json({ message });
  });
  app.use('/api', (req, res) => res.status(404).json({ error: 'Маршрут не найден' }));
  if (staticDir) {
    app.use(express.static(staticDir));
    app.get('/{*path}', (req, res) => res.sendFile(resolve(staticDir, 'index.html')));
  }
  app.use((error, req, res, next) => {
    if (res.headersSent) return next(error);
    if (error.type === 'entity.too.large') return res.status(413).json({ error: 'Размер запроса слишком большой' });
    if (error.type === 'entity.parse.failed') return res.status(400).json({ error: 'Некорректный JSON' });
    const status = error.status >= 400 && error.status < 500 ? error.status : 500;
    if (status === 500) console.error('API error:', error.code || error.name);
    res.status(status).json({ error: status === 500 ? 'Ошибка сервера. Попробуйте позже.' : error.message });
  });
  return app;
}
