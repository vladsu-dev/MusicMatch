import { useEffect, useState } from 'react';
import Modal from './Modal.jsx';
import { api } from '../api.js';

// Список тех, с кем лайки оказались взаимными.
export default function MatchesModal({ onClose }) {
  const [matches, setMatches] = useState(null);

  useEffect(() => {
    api
      .matches()
      .then((data) => setMatches(data.matches))
      .catch(() => setMatches([]));
  }, []);

  return (
    <Modal onClose={onClose} width={400}>
      <h2>Совпадения</h2>
      <p className="subtitle">Взаимные лайки.</p>

      {matches === null && <p className="hint">Загружаем…</p>}
      {matches?.length === 0 && (
        <p className="hint">Пока пусто. Лайкайте анкеты — совпадения появятся здесь.</p>
      )}

      <ul className="match-list">
        {matches?.map((match) => (
          <li key={match.userId}>
            <img src={match.photo} alt={match.name} />
            <div>
              <strong>{match.name}</strong>
              <span>♪ {match.genre}</span>
            </div>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
