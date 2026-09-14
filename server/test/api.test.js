import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes, randomUUID } from 'node:crypto';
import jwt from 'jsonwebtoken';
import { createPool } from '../db.js';
import { migrate } from '../migrate.js';
import { createApp } from '../app.js';

test('PostgreSQL + JWT + matching + message permissions', { timeout: 60_000 }, async (t) => {
  assert.ok(process.env.TEST_DATABASE_URL, 'Задайте TEST_DATABASE_URL отдельной тестовой БД');
  const pool = createPool(process.env.TEST_DATABASE_URL);
  await migrate(pool);
  await migrate(pool); // migrations are repeatable
  const secret = randomBytes(32).toString('hex');
  const origin = 'http://127.0.0.1:5173';
  const server = createApp({ pool, secret, origin }).listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  const url = 'http://127.0.0.1:' + server.address().port;
  const created = [];
  t.after(async () => {
    for (const id of created) await pool.query('DELETE FROM users WHERE id=$1', [id]);
    await new Promise((resolve) => server.close(resolve));
    await pool.end();
  });
  function agent() { return { cookies: new Map() }; }
  async function call(who, path, { method = 'GET', body, requestOrigin = origin, cookie } = {}) {
    const headers = { Origin: requestOrigin };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    headers.Cookie = cookie ?? [...who.cookies].map(([k,v]) => k + '=' + v).join('; ');
    const response = await fetch(url + '/api' + path, {
      method, headers, body: body === undefined ? undefined : JSON.stringify(body),
    });
    for (const entry of response.headers.getSetCookie()) {
      const [name, value] = entry.split(';')[0].split('=');
      if (value) who.cookies.set(name, value); else who.cookies.delete(name);
    }
    const data = response.status === 204 ? null : await response.json();
    return { status: response.status, data, response };
  }
  const password = 'MusicMatch-test-123';
  const suffix = randomUUID();
  const a = agent(), b = agent(), stranger = agent();
  async function register(who, label) {
    const result = await call(who, '/auth/register', { method: 'POST', body: { email: label + suffix + '@example.com', password } });
    assert.equal(result.status, 201);
    who.user = result.data.user; created.push(who.user.id);
    return result;
  }
  await t.test('registration, secure cookie flags, password hash, duplicate email', async () => {
    const result = await register(a, 'a');
    assert.match(result.response.headers.getSetCookie()[0], /HttpOnly/);
    assert.match(result.response.headers.getSetCookie()[0], /SameSite=Strict/);
    const row = (await pool.query('SELECT password_hash FROM users WHERE id=$1', [a.user.id])).rows[0];
    assert.notEqual(row.password_hash, password);
    const duplicate = await call(a, '/auth/register', { method: 'POST', body: { email: a.user.email.toUpperCase(), password } });
    assert.equal(duplicate.status, 409);
    assert.equal((await call(a, '/auth/register', { method: 'POST', body: { email: 'invalid', password: 'short' } })).status, 400);
    await register(b, 'b'); await register(stranger, 'c');
  });
  await t.test('invalid credentials, JWT signature, algorithm, expiry and origin', async () => {
    assert.equal((await call(agent(), '/auth/login', { method: 'POST', body: { email: a.user.email, password: 'incorrect-password' } })).status, 401);
    assert.equal((await call(agent(), '/feed')).status, 401);
    const claims = jwt.decode(a.cookies.get('mm_access'));
    for (const token of [
      jwt.sign({ sub: claims.sub, sid: claims.sid }, 'wrong-secret'),
      jwt.sign({ sub: claims.sub, sid: claims.sid }, secret, { algorithm: 'HS384', issuer: 'musicmatch', audience: 'musicmatch-web', expiresIn: '15m' }),
      jwt.sign({ sub: claims.sub, sid: claims.sid }, secret, { algorithm: 'HS256', issuer: 'musicmatch', audience: 'musicmatch-web', expiresIn: -1 }),
    ]) {
      assert.equal((await call(agent(), '/auth/session', { cookie: 'mm_access=' + token })).status, 401);
    }
    assert.equal((await call(a, '/auth/logout', { method: 'POST', requestOrigin: 'https://evil.example' })).status, 403);
    assert.equal((await call(a, '/auth/session')).status, 200);
  });
  // Only a signature fixture is needed here; the browser test uploads and resizes a real image.
  const photo = 'data:image/jpeg;base64,' + Buffer.from([255,216,255,224,0,2,255,217]).toString('base64');
  await t.test('profile validation and persistence across login', async () => {
    assert.equal((await call(a, '/feed')).status, 409);
    for (const who of [a,b,stranger]) {
      const result = await call(who, '/me/profile', { method: 'PUT', body: { name: who === a ? 'Влад' : 'Участник', genre: 'Рок', photo } });
      assert.equal(result.status, 200);
    }
    assert.equal((await call(a, '/me/profile', { method: 'PUT', body: { name: 'Влад', genre: 'unknown', photo } })).status, 400);
    assert.equal((await call(a, '/me/profile', { method: 'PUT', body: { name: 'Влад', genre: 'Рок', photo: 'data:image/svg+xml,<svg/>' } })).status, 400);
    const login = await call(agent(), '/auth/login', { method: 'POST', body: { email: a.user.email.toUpperCase(), password } });
    assert.equal(login.status, 200);
    assert.equal(login.data.profile.name, 'Влад');
    assert.equal(login.data.user.id, a.user.id);
    const feed = await call(a, '/feed');
    assert.ok(feed.data.profiles.every((p) => p.id !== a.user.id && p.sameGenre));
    assert.ok(feed.data.profiles.some((p) => p.id === b.user.id));
  });
  await t.test('refresh rotation, hash storage and replay rejection', async () => {
    const previous = a.cookies.get('mm_refresh');
    assert.equal((await call(a, '/auth/refresh', { method: 'POST' })).status, 200);
    assert.notEqual(a.cookies.get('mm_refresh'), previous);
    assert.equal((await call(agent(), '/auth/refresh', { method: 'POST', cookie: 'mm_refresh=' + previous })).status, 401);
    const claims = jwt.decode(a.cookies.get('mm_access'));
    const row = (await pool.query('SELECT refresh_hash FROM sessions WHERE id=$1', [claims.sid])).rows[0];
    assert.notEqual(row.refresh_hash, a.cookies.get('mm_refresh'));
  });
  let matchId;
  await t.test('concurrent reciprocal likes create one match; retries are idempotent', async () => {
    const results = await Promise.all([
      call(a, '/decisions/' + b.user.id, { method: 'POST', body: { action: 'like' } }),
      call(b, '/decisions/' + a.user.id, { method: 'POST', body: { action: 'like' } }),
    ]);
    assert.ok(results.every((r) => r.status === 200));
    const matches = (await call(a, '/matches')).data.matches;
    assert.equal(matches.length, 1); matchId = matches[0].matchId;
    const retry = await call(a, '/decisions/' + b.user.id, { method: 'POST', body: { action: 'like' } });
    assert.equal(retry.data.match.matchId, matchId);
    assert.equal((await call(b, '/matches')).data.matches[0].matchId, matchId);
    assert.equal((await call(a, '/decisions/' + a.user.id, { method: 'POST', body: { action: 'like' } })).status, 400);
    assert.equal((await call(a, '/decisions/not-a-uuid', { method: 'POST', body: { action: 'like' } })).status, 400);
  });
  await t.test('chat membership, sender identity, validation and persistence', async () => {
    const path = '/matches/' + matchId + '/messages';
    assert.equal((await call(stranger, path)).status, 404);
    assert.equal((await call(stranger, path, { method: 'POST', body: { text: 'intrusion' } })).status, 404);
    const sent = await call(a, path, { method: 'POST', body: { text: 'Привет!', senderId: stranger.user.id } });
    assert.equal(sent.status, 201);
    assert.equal(sent.data.message.senderId, a.user.id);
    assert.equal((await call(b, path)).data.messages[0].text, 'Привет!');
    assert.equal((await call(a, path, { method: 'POST', body: { text: ' ' } })).status, 400);
    assert.equal((await call(a, path, { method: 'POST', body: { text: 'x'.repeat(2001) } })).status, 400);
    // A second pool verifies that storage is PostgreSQL, not application memory.
    const second = createPool(process.env.TEST_DATABASE_URL);
    try { assert.equal((await second.query('SELECT text FROM messages WHERE id=$1', [sent.data.message.id])).rows[0].text, 'Привет!'); }
    finally { await second.end(); }
    await pool.query("INSERT INTO messages(match_id,sender_id,text) SELECT $1,$2,'history-' || n FROM generate_series(1,55) n", [matchId, b.user.id]);
    const latest = (await call(a, path)).data;
    assert.equal(latest.messages.length, 50); assert.equal(latest.hasMore, true);
    const older = (await call(a, path + '?before=' + latest.messages[0].id)).data;
    assert.equal(older.messages.length, 6); assert.equal(older.hasMore, false);
    const after = (await call(a, path + '?after=' + sent.data.message.id)).data;
    assert.equal(after.messages.length, 50); assert.equal(after.hasMore, true);
    assert.equal((await call(a, path + '?before=9999999999999999999')).status, 400);
  });
  await t.test('reset revisits skips and preserves matches and messages', async () => {
    await call(a, '/decisions/' + stranger.user.id, { method: 'POST', body: { action: 'skip' } });
    assert.equal((await call(a, '/feed/reset', { method: 'POST' })).status, 204);
    assert.equal((await call(a, '/matches')).data.matches[0].matchId, matchId);
    assert.ok((await call(a, '/feed')).data.profiles.some((p) => p.id === stranger.user.id));
    assert.equal((await call(a, '/me/stats')).data.viewed, 1);
  });
  await t.test('logout revokes access and refresh even if cookies are copied', async () => {
    const copy = [...a.cookies].map(([k,v]) => k + '=' + v).join('; ');
    assert.equal((await call(a, '/auth/logout', { method: 'POST' })).status, 204);
    assert.equal((await call(agent(), '/auth/session', { cookie: copy })).status, 401);
    assert.equal((await call(agent(), '/auth/refresh', { method: 'POST', cookie: copy })).status, 401);
  });
});
