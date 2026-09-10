import { useCallback, useEffect, useState } from 'react';
import { api, getToken, setToken } from './api.js';
import Banner from './components/Banner.jsx';
import AuthModal from './components/AuthModal.jsx';
import ProfileModal from './components/ProfileModal.jsx';
import MatchesModal from './components/MatchesModal.jsx';
import Deck from './components/Deck.jsx';

export default function App() {
  const [booting, setBooting] = useState(true);
  const [genres, setGenres] = useState([]);
  const [session, setSession] = useState(null); // { user, profile }
  const [modal, setModal] = useState(null); // 'auth' | 'login' | 'profile' | 'matches'
  const [matchCount, setMatchCount] = useState(0);

  const refreshMatches = useCallback(() => {
    api
      .matches()
      .then((data) => setMatchCount(data.matches.length))
      .catch(() => {});
  }, []);

  // Стартовая загрузка: список жанров и восстановление сессии по токену.
  useEffect(() => {
    api
      .genres()
      .then((data) => setGenres(data.genres))
      .catch(() => {});

    if (!getToken()) return setBooting(false);

    api
      .me()
      .then((data) => {
        setSession({ user: data.user, profile: data.profile });
        if (data.profile) refreshMatches();
      })
      .catch(() => setToken(null))
      .finally(() => setBooting(false));
  }, [refreshMatches]);

  function logout() {
    setToken(null);
    setSession(null);
    setMatchCount(0);
  }

  function onAuthSuccess(next) {
    setSession(next);
    // Сразу после регистрации предлагаем заполнить анкету.
    setModal(next.profile ? null : 'profile');
    if (next.profile) refreshMatches();
  }

  function onProfileSaved(profile) {
    setSession((prev) => ({ ...prev, profile }));
    setModal(null);
    refreshMatches();
  }

  const profile = session?.profile;

  if (booting) return <p className="center-note">Загрузка…</p>;

  return (
    <>
      <header className="header">
        <div className="logo">Music Match</div>

        <div className="header-actions">
          {session ? (
            <>
              {profile && (
                <div className="header-user">
                  <img className="avatar" src={profile.photo} alt="" />
                  <span>{profile.name}</span>
                </div>
              )}
              {profile && (
                <button className="btn-plain" onClick={() => setModal('matches')}>
                  Совпадения
                  {matchCount > 0 && <span className="badge">{matchCount}</span>}
                </button>
              )}
              <button className="btn-plain" onClick={() => setModal('profile')}>
                {profile ? 'Моя анкета' : 'Заполнить анкету'}
              </button>
              <button className="btn-plain" onClick={logout}>
                Выйти
              </button>
            </>
          ) : (
            <button className="btn-plain" onClick={() => setModal('login')}>
              Войти
            </button>
          )}
        </div>
      </header>

      <main>
        {!session && <Banner genres={genres} onStart={() => setModal('auth')} />}

        {session && !profile && (
          <section className="banner">
            <h1>
              Остался один шаг — <em>ваша анкета</em>
            </h1>
            <p>Имя, фото и любимый жанр. После этого откроются анкеты других участников.</p>
            <button className="btn btn-lg" onClick={() => setModal('profile')}>
              Заполнить анкету
            </button>
          </section>
        )}

        {session && profile && <Deck key={profile.updatedAt} onMatch={refreshMatches} />}
      </main>

      {(modal === 'auth' || modal === 'login') && (
        <AuthModal
          initialTab={modal === 'login' ? 'login' : 'register'}
          onClose={() => setModal(null)}
          onSuccess={onAuthSuccess}
        />
      )}
      {modal === 'profile' && session && (
        <ProfileModal
          profile={profile}
          genres={genres}
          onClose={() => setModal(null)}
          onSaved={onProfileSaved}
        />
      )}
      {modal === 'matches' && <MatchesModal onClose={() => setModal(null)} />}
    </>
  );
}
