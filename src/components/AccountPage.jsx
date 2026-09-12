export default function AccountPage({ profile, stats, onBack, onEdit }) {
  return (
    <section className="account">
      <button className="back-link" onClick={onBack}>
        ← Назад к анкетам
      </button>

      <div className="account-header">
        <img className="account-avatar" src={profile.photo} alt={profile.name} />
        <div>
          <h1 className="account-name">{profile.name}</h1>
          <span className="account-genre">♪ {profile.genre}</span>
        </div>
      </div>

      <div className="account-stats">
        <div className="account-stat">
          <b>{stats.viewed}</b>
          <span>анкет просмотрено</span>
        </div>
        <div className="account-stat">
          <b>{stats.matches}</b>
          <span>совпадений</span>
        </div>
      </div>

      <div className="account-actions">
        <button className="btn btn-ghost" onClick={onEdit}>
          Редактировать анкету
        </button>
      </div>
    </section>
  );
}
