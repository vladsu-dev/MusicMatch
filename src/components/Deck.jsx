import { useCallback, useEffect, useState } from 'react';
import Modal from './Modal.jsx';

export default function Deck({ feed, onDecide, onRestart, keyboardEnabled = true }) {
  const [leaving, setLeaving] = useState(null);
  const [matched, setMatched] = useState(null);

  const [error, setError] = useState('');
  const [restarting, setRestarting] = useState(false);

  const current = feed[0];
  const next = feed[1];

  const decide = useCallback(
    async (action) => {
      if (!current || leaving) return;
      setLeaving(action);
      setError('');
      try {
        const match = await onDecide(current, action);
        if (match) setMatched(match);
      } catch (err) { setError(err.message); }
      finally { setLeaving(null); }
    },
    [current, leaving, onDecide]
  );

  async function restart() {
    if (restarting) return;
    setRestarting(true);
    setError('');
    try { await onRestart(); }
    catch (err) { setError(err.message); }
    finally { setRestarting(false); }
  }

  useEffect(() => {
    const onKey = (event) => {
      if (matched || !keyboardEnabled || event.repeat || event.target.closest('input, textarea, select, button, [contenteditable="true"]')) return;
      if (event.key === 'ArrowRight') decide('like');
      if (event.key === 'ArrowLeft') decide('skip');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [decide, matched, keyboardEnabled]);

  return (
    <div className="deck-wrap">
      {error && <p className="form-error" role="alert">{error}</p>}
      {current ? (
        <>
          <div className="deck">
            {next && <Card profile={next} className="behind" key={next.id} />}
            <Card profile={current} className={leaving ? `leave-${leaving}` : ''} key={current.id} />
          </div>

          <div className="deck-actions">
            <button
              className="action"
              onClick={() => decide('skip')}
              disabled={!!leaving}
              title="Пропустить (←)"
              aria-label="Пропустить"
            >
              ✕
            </button>
            <button
              className="action like"
              onClick={() => decide('like')}
              disabled={!!leaving}
              title="Лайк (→)"
              aria-label="Лайк"
            >
              ♥
            </button>
          </div>
          <p className="hint">Стрелки ← и → работают так же</p>
        </>
      ) : (
        <div className="empty-state">
          <h3>Анкеты закончились</h3>
          <p>Вы просмотрели всех участников.</p>
          <button className="btn btn-ghost" onClick={restart} disabled={restarting}>
            {restarting ? 'Загрузка…' : 'Показать пропущенные'}
          </button>
        </div>
      )}

      {matched && (
        <Modal onClose={() => setMatched(null)} width={360}>
          <div className="match-toast">
            <img src={matched.photo} alt={matched.name} />
            <h2>Взаимная симпатия</h2>
            <p className="subtitle">
              {matched.name} тоже поставил(а) вам лайк. Любимый жанр — {matched.genre}.
            </p>
            <button className="btn" onClick={() => setMatched(null)}>
              Листать дальше
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Card({ profile, className = '' }) {
  return (
    <article className={`card ${className}`}>
      <img src={profile.photo} alt={profile.name} />
      <div className="card-info">
        <h3>{profile.name}</h3>
        <span className={`card-genre ${profile.sameGenre ? 'same' : ''}`}>
          ♪ {profile.genre}
          {profile.sameGenre && ' · совпадает с вашим'}
        </span>
      </div>
    </article>
  );
}
