import { useCallback, useEffect, useState } from 'react';
import Modal from './Modal.jsx';

export default function Deck({ feed, onDecide, onRestart }) {
  const [leaving, setLeaving] = useState(null);
  const [matched, setMatched] = useState(null);

  const current = feed[0];
  const next = feed[1];

  const decide = useCallback(
    (action) => {
      if (!current || leaving) return;
      setLeaving(action);
      setTimeout(() => {
        const match = onDecide(current, action);
        setLeaving(null);
        if (match) setMatched(match);
      }, 320);
    },
    [current, leaving, onDecide]
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

  return (
    <div className="deck-wrap">
      {current ? (
        <>
          <div className="deck">
            {next && <Card profile={next} className="behind" key={next.id} />}
            <Card profile={current} className={leaving ? `leave-${leaving}` : ''} key={current.id} />
          </div>

          <div className="deck-actions">
            {/* Пропуск текущей карточки. Запускает анимацию улёта влево,
                затем через decide -> onDecide убирает анкету из ленты без
                следа в matches. disabled на время анимации, чтобы нельзя
                было кликнуть дважды по одной карточке. */}
            <button
              className="action"
              onClick={() => decide('skip')}
              disabled={!!leaving}
              title="Пропустить (←)"
              aria-label="Пропустить"
            >
              ✕
            </button>
            {/* Лайк текущей карточки. Если у анкеты стоит likesYou: true
                (см. profiles.js), onDecide вернёт её, и ниже откроется
                окно "Взаимная симпатия". Иначе просто уходит в ленту. */}
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
          {/* Вызывает onRestart из App.jsx: очищает judged и matches,
              возвращая в ленту все анкеты заново. */}
          <button className="btn btn-ghost" onClick={onRestart}>
            Показать снова
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
            {/* Просто закрывает это окно (setMatched(null)) и возвращает
                к ленте — сама анкета уже убрана из feed предыдущим decide. */}
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
