import { randomBytes, scrypt as scryptCallback, timingSafeEqual, createHash } from 'node:crypto';
import { promisify } from 'node:util';
import jwt from 'jsonwebtoken';

const scrypt = promisify(scryptCallback);
export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export function fail(status, message) { throw Object.assign(new Error(message), { status }); }
export function hashToken(token) { return createHash('sha256').update(token).digest('hex'); }
export function refreshToken() { return randomBytes(32).toString('hex'); }

export async function hashPassword(password) {
  const salt = randomBytes(16).toString('hex');
  const key = await scrypt(password, salt, 64);
  return salt + ':' + key.toString('hex');
}
export async function verifyPassword(password, stored) {
  const [salt, hex] = stored.split(':');
  const key = await scrypt(password, salt, 64);
  const expected = Buffer.from(hex, 'hex');
  return key.length === expected.length && timingSafeEqual(key, expected);
}
export function credentials(body) {
  const email = typeof body?.email === 'string' ? body.email.trim().toLowerCase() : '';
  const password = body?.password;
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) fail(400, 'Введите корректный email');
  if (typeof password !== 'string' || password.length < 8 || password.length > 128) fail(400, 'Пароль должен содержать от 8 до 128 символов');
  return { email, password };
}
export function createSecurity(secret) {
  if (!secret || Buffer.byteLength(secret) < 32 || secret.startsWith('replace-')) {
    throw new Error('JWT_SECRET должен быть случайным секретом длиной не менее 32 байт');
  }
  return {
    sign(userId, sessionId) {
      return jwt.sign({ sid: sessionId }, secret, {
        algorithm: 'HS256', subject: userId, issuer: 'musicmatch',
        audience: 'musicmatch-web', expiresIn: '15m',
      });
    },
    verify(token) {
      const claims = jwt.verify(token, secret, {
        algorithms: ['HS256'], issuer: 'musicmatch', audience: 'musicmatch-web',
      });
      if (!UUID_RE.test(claims.sub) || !UUID_RE.test(claims.sid)) throw new Error('Invalid claims');
      return claims;
    },
  };
}
