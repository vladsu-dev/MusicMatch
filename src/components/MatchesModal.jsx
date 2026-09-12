import Modal from './Modal.jsx';

export default function MatchesModal({ matches, onClose, onSelectMatch }) {
  return (
    <Modal onClose={onClose} width={400}>
      <h2>Совпадения</h2>
      <p className="subtitle">Взаимные лайки. Нажмите на профиль, чтобы открыть переписку.</p>

      {matches.length === 0 && (
        <p className="hint">Пока пусто. Лайкайте анкеты — совпадения появятся здесь.</p>
      )}

      <ul className="match-list">
        {matches.map((match) => (
          <li key={match.id}>
            {/* Открывает ChatWidget в правом нижнем углу экрана
                (onSelectMatch -> setActiveChat в App.jsx). Само окно
                "Совпадения" при этом не закрывается — оба остаются на
                экране одновременно. */}
            <button className="match-row" onClick={() => onSelectMatch(match)}>
              <img src={match.photo} alt={match.name} />
              <div>
                <strong>{match.name}</strong>
                <span>♪ {match.genre}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
