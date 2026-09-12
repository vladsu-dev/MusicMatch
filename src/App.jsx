import { useMemo, useState } from 'react';
import { GENRES } from './data/genres.js';
import { DEMO_PROFILES } from './data/profiles.js';
import Banner from './components/Banner.jsx';
import AuthModal from './components/AuthModal.jsx';
import ProfileModal from './components/ProfileModal.jsx';
import MatchesModal from './components/MatchesModal.jsx';
import Deck from './components/Deck.jsx';

export default function App() {
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [modal, setModal] = useState(null);
  const [judged, setJudged] = useState([]);
  const [matches, setMatches] = useState([]);

  const feed = useMemo(() => {
    const rest = DEMO_PROFILES.filter((item) => !judged.includes(item.id)).map((item) => ({
      ...item,
      sameGenre: item.genre === profile?.genre,
    }));
    return rest.sort((a, b) => Number(b.sameGenre) - Number(a.sameGenre));
  }, [judged, profile]);

  function logout() {
    setSession(null);
    setProfile(null);
    setModal(null);
    setJudged([]);
    setMatches([]);
  }

  function onAuthSuccess(user) {
    setSession(user);
    setModal('profile');
  }

  function onProfileSaved(next) {
    setProfile(next);
    setModal(null);
  }

  function onDecide(target, action) {
    setJudged((prev) => [...prev, target.id]);
    if (action === 'like' && target.likesYou) {
      setMatches((prev) => [target, ...prev]);
      return target;
    }
    return null;
  }

  function restartFeed() {
    setJudged([]);
    setMatches([]);
  }

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
              {/* Открывает окно "Совпадения" (MatchesModal). Бейдж с числом
                  показывается, только если есть хотя бы один взаимный лайк. */}
              {profile && (
                <button className="btn-plain" onClick={() => setModal('matches')}>
                  Совпадения
                  {matches.length > 0 && <span className="badge">{matches.length}</span>}
                </button>
              )}
              {/* Открывает окно анкеты (ProfileModal): создать её, если ещё
                  нет, либо отредактировать уже заполненную — надпись меняется
                  в зависимости от наличия profile. */}
              <button className="btn-plain" onClick={() => setModal('profile')}>
                {profile ? 'Моя анкета' : 'Заполнить анкету'}
              </button>
              {/* Сбрасывает всё состояние приложения и возвращает на баннер
                  для гостя — полноценного выхода с сервера здесь нет. */}
              <button className="btn-plain" onClick={logout}>
                Выйти
              </button>
            </>
          ) : (
            /* Открывает AuthModal сразу на вкладке "Вход". */
            <button className="btn-plain" onClick={() => setModal('login')}>
              Войти
            </button>
          )}
        </div>
      </header>

      <main>
        {!session && <Banner genres={GENRES} onStart={() => setModal('auth')} />}

        {session && !profile && (
          <section className="banner">
            <h1>
              Остался один шаг — <em>ваша анкета</em>
            </h1>
            <p>Имя, фото и любимый жанр. После этого откроются анкеты других участников.</p>
            {/* Тот же переход, что и кнопка "Заполнить анкету" в шапке, —
                просто более заметный призыв к действию на этом экране. */}
            <button className="btn btn-lg" onClick={() => setModal('profile')}>
              Заполнить анкету
            </button>
          </section>
        )}

        {session && profile && (
          <Deck feed={feed} onDecide={onDecide} onRestart={restartFeed} />
        )}
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
          genres={GENRES}
          onClose={() => setModal(null)}
          onSaved={onProfileSaved}
        />
      )}
      {modal === 'matches' && <MatchesModal matches={matches} onClose={() => setModal(null)} />}
    </>
  );
}
