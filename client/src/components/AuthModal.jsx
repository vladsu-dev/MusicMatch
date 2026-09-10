import { useState } from 'react';
import Modal from './Modal.jsx';
import { api, setToken } from '../api.js';

// Одно окно с двумя вкладками: регистрация нового аккаунта и вход в существующий.
export default function AuthModal({ onClose, onSuccess, initialTab = 'register' }) {
  const [tab, setTab] = useState(initialTab);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const isRegister = tab === 'register';

  const switchTab = (next) => {
    setTab(next);
    setError('');
  };

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const data = isRegister
        ? await api.register(email, password)
        : await api.login(email, password);
      setToken(data.token);
      onSuccess({ user: data.user, profile: data.profile });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal onClose={onClose}>
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
          ? 'Пароль хранится в виде необратимого хеша, email — в зашифрованном виде.'
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
            placeholder={isRegister ? 'минимум 6 символов' : '••••••••'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            required
          />
        </div>

        <div className="form-footer">
          <button className="btn" type="submit" disabled={busy}>
            {busy ? 'Секунду…' : isRegister ? 'Зарегистрироваться' : 'Войти'}
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
