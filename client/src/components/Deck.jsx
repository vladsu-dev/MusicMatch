import { useCallback, useEffect, useState } from 'react';
import Modal from './Modal.jsx';
import { api } from '../api.js';

// Колода чужих анкет: лайк или пропуск, стрелками с клавиатуры тоже.
export default function Deck({ onMatch }) {
  const [feed, setFeed] = useState([]);
  const [index, setIndex] = useState(0);
  const [leaving, setLeaving] = useState(null); // 'like' | 'skip'
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [matched, setMatched] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.feed();
      setFeed(data.feed);
      setIndex(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const current = feed[index];
  const next = feed[index + 1];

  const decide = useCallback(
    async (action) => {
      if (!current || busy) return;
      setBusy(true);
      setLeaving(action);
      try {
        const data = await api.swipe(current.userId, action);
        // Даём карточке уехать за экран, потом показываем следующую.
        await new Promise((resolve) => setTimeout(resolve, 320));
        setIndex((value) => value + 1);
        setLeaving(null);
        if (data.match) {
          setMatched(data.profile);
          onMatch?.();
        }
      } catch (err) {
        setError(err.message);
        setLeaving(null);
      } finally {
        setBusy(false);
      }
    },
    [current, busy, onMatch]
  );

  useEffect(() => {
    const onKey = (event) => {
      if (matched) return;
      if (event.key === 'ArrowRight') decide('like');
      if (event.key === 'ArrowLeft') decide('skip');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [decide, matched]);

  if (loading) return <p className="center-note">Загружаем анкеты…</p>;

  return (
    <div className="deck-wrap">
      {error && <p className="form-error">{error}</p>}

      {current ? (
        <>
          <div className="deck">
            {next && <Card profile={next} className="behind" key={next.userId} />}
            <Card profile={current} className={leaving ? `leave-${leaving}` : ''} key={current.userId} />
          </div>

          <div className="deck-actions">
            <button
              className="action"
              onClick={() => decide('skip')}
              disabled={busy}
              title="Пропустить (←)"
              aria-label="Пропустить"
            >
              ✕
            </button>
            <button
              className="action like"
              onClick={() => decide('like')}
              disabled={busy}
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
          <p>Вы просмотрели всех, кто уже зарегистрирован. Загляните позже — появятся новые.</p>
          <button className="btn btn-ghost" onClick={load}>
            Обновить
          </button>
        </div>
      )}

      {matched && (
        <Modal onClose={() => setMatched(null)} width={360}>
          <div className="match-toast">
            <img src={matched.photo} alt={matched.name} />
            <h2>Взаимная симпатия</h2>
            <p className="subtitle">
              {matched.name} тоже поставил(а) вам лайк. Общий жанр — {matched.genre}.
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
