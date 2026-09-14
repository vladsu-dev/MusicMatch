import { useState } from 'react';
import { api } from '../api.js';
import Modal from './Modal.jsx';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AuthModal({ onClose, onSuccess, initialTab = 'register' }) {
  const [tab, setTab] = useState(initialTab);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const [busy, setBusy] = useState(false);

  const isRegister = tab === 'register';

  const switchTab = (next) => {
    if (busy) return;
    setTab(next);
    setError('');
  };

  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (!EMAIL_RE.test(email.trim())) return setError('Введите корректный email');
    if (password.length < 8 || password.length > 128) return setError('Пароль должен содержать от 8 до 128 символов');
    setError('');
    setBusy(true);
    try {
      const result = await api(isRegister ? '/auth/register' : '/auth/login', {
        method: 'POST', body: { email: email.trim(), password },
      });
      onSuccess(result);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <Modal onClose={() => { if (!busy) onClose(); }}>
      <div className="tabs">
        <button aria-selected={isRegister} onClick={() => switchTab('register')}>
          Регистрация
        </button>
        <button aria-selected={!isRegister} onClick={() => switchTab('login')}>
          Вход
        </button>
      </div>

      <h2>{isRegister ? 'Создать аккаунт' : 'С возвращением'}</h2>
      <p className="subtitle">
        {isRegister
          ? 'Создайте аккаунт, чтобы сохранить анкету и знакомиться.'
          : 'Введите данные вашего аккаунта.'}
      </p>

      <form onSubmit={submit}>
        {error && <p className="form-error">{error}</p>}

        <div className="field">
          <label htmlFor="auth-email">Email</label>
          <input
            id="auth-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
        </div>

        <div className="field">
          <label htmlFor="auth-password">Пароль</label>
          <input
            id="auth-password"
            type="password"
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            placeholder={isRegister ? 'от 8 до 128 символов' : '••••••••'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            maxLength={128}
            required
          />
        </div>

        <div className="form-footer">
          <button className="btn" type="submit" disabled={busy}>
            {busy ? 'Подождите…' : isRegister ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </div>
      </form>

      <p className="hint">
        {isRegister ? 'Уже есть аккаунт? ' : 'Ещё нет аккаунта? '}
        <button className="btn-plain" onClick={() => switchTab(isRegister ? 'login' : 'register')}>
          {isRegister ? 'Войти' : 'Зарегистрироваться'}
        </button>
      </p>
    </Modal>
  );
}
