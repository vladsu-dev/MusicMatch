// Тонкая обёртка над fetch: подставляет токен и разворачивает ошибки сервера.

const TOKEN_KEY = 'accord.token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

async function request(path, { method = 'GET', body } = {}) {
  const token = getToken();
  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Не удалось связаться с сервером');
  return data;
}

export const api = {
  genres: () => request('/genres'),
  register: (email, password) => request('/register', { method: 'POST', body: { email, password } }),
  login: (email, password) => request('/login', { method: 'POST', body: { email, password } }),
  me: () => request('/me'),
  saveProfile: (profile) => request('/profile', { method: 'PUT', body: profile }),
  feed: () => request('/feed'),
  swipe: (targetId, action) => request('/swipe', { method: 'POST', body: { targetId, action } }),
  matches: () => request('/matches'),
};
