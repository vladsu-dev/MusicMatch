import Modal from './Modal.jsx';

export default function MatchesModal({ matches, onClose }) {
  return (
    <Modal onClose={onClose} width={400}>
      <h2>Совпадения</h2>
      <p className="subtitle">Взаимные лайки.</p>

      {matches.length === 0 && (
        <p className="hint">Пока пусто. Лайкайте анкеты — совпадения появятся здесь.</p>
      )}

      <ul className="match-list">
        {matches.map((match) => (
          <li key={match.id}>
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
