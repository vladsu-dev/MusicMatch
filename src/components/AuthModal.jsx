import { useState } from 'react';
import Modal from './Modal.jsx';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AuthModal({ onClose, onSuccess, initialTab = 'register' }) {
  const [tab, setTab] = useState(initialTab);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const isRegister = tab === 'register';

  const switchTab = (next) => {
    setTab(next);
    setError('');
  };

  function submit(event) {
    event.preventDefault();
    if (!EMAIL_RE.test(email.trim())) return setError('Введите корректный email');
    if (password.length < 6) return setError('Пароль должен быть не короче 6 символов');
    setError('');
    onSuccess({ email: email.trim() });
  }

  return (
    <Modal onClose={onClose}>
      {/* Переключатели вкладок внутри этого же окна: никуда не ведут,
          только меняют локальный tab и, соответственно, текст формы ниже. */}
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
          ? 'Демонстрационный интерфейс: данные никуда не отправляются.'
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
          {/* Отправляет форму (submit сработает через onSubmit формы).
              При успешной проверке вызывает onSuccess из App.jsx, а тот
              закрывает это окно и открывает анкету (ProfileModal). */}
          <button className="btn" type="submit">
            {isRegister ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </div>
      </form>

      <p className="hint">
        {isRegister ? 'Уже есть аккаунт? ' : 'Ещё нет аккаунта? '}
        {/* Второй способ переключить вкладку, тот же switchTab, что и
            кнопки сверху — просто продублирован рядом с формой. */}
        <button className="btn-plain" onClick={() => switchTab(isRegister ? 'login' : 'register')}>
          {isRegister ? 'Войти' : 'Зарегистрироваться'}
        </button>
      </p>
    </Modal>
  );
}
