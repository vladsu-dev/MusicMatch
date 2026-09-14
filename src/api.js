export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
async function request(path, { method = 'GET', body, signal } = {}) {
  const response = await fetch('/api' + path, {
    method, credentials: 'same-origin', signal,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error || 'Ошибка запроса', response.status);
  return data;
}
let refreshing;
async function refresh() {
  if (!refreshing) {
    const perform = () => request('/auth/refresh', { method: 'POST' });
    // Serialize cookie rotation between tabs when Web Locks are available.
    refreshing = (navigator.locks
      ? navigator.locks.request('musicmatch-refresh', perform)
      : perform()).finally(() => { refreshing = null; });
  }
  return refreshing;
}
export async function api(path, options) {
  try { return await request(path, options); }
  catch (error) {
    if (error.status !== 401 || ['/auth/login', '/auth/register', '/auth/logout', '/auth/refresh'].includes(path)) throw error;
    try {
      await refresh();
      return await request(path, options);
    } catch (next) {
      if (next.status === 401) window.dispatchEvent(new Event('musicmatch:unauthorized'));
      throw next;
    }
  }
}
