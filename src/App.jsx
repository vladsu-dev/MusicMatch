import { useMemo, useState } from 'react';
import { GENRES } from './data/genres.js';
import { DEMO_PROFILES } from './data/profiles.js';
import Banner from './components/Banner.jsx';
import AuthModal from './components/AuthModal.jsx';
import ProfileModal from './components/ProfileModal.jsx';
import MatchesModal from './components/MatchesModal.jsx';
import Deck from './components/Deck.jsx';
import AccountPage from './components/AccountPage.jsx';
import ChatWidget from './components/ChatWidget.jsx';

export default function App() {
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [modal, setModal] = useState(null);
  const [judged, setJudged] = useState([]);
  const [matches, setMatches] = useState([]);

  // Какой экран показан в <main>: лента анкет или личный кабинет.
  // Это настоящая навигация внутри приложения, а не модальное окно.
  const [view, setView] = useState('deck');

  // Совпадение, с которым сейчас открыт мини-чат (ChatWidget) в правом
  // нижнем углу экрана. null — виджет не показан.
  const [activeChat, setActiveChat] = useState(null);

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
    setView('deck');
    setActiveChat(null);
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
              {/* Фото + ник — теперь кнопка. Клик переключает view на
                  'account' (настоящий переход в личный кабинет, не
                  модалка). Обратно ведёт кнопка "Назад к анкетам"
                  внутри AccountPage. */}
              {profile && (
                <button
                  className="header-user"
                  aria-pressed={view === 'account'}
                  onClick={() => setView('account')}
                >
                  <img className="avatar" src={profile.photo} alt="" />
                  <span>{profile.name}</span>
                </button>
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

            <button className="btn btn-lg" onClick={() => setModal('profile')}>
              Заполнить анкету
            </button>
          </section>
        )}

        {session && profile && view === 'deck' && (
          <Deck feed={feed} onDecide={onDecide} onRestart={restartFeed} />
        )}

        {session && profile && view === 'account' && (
          <AccountPage
            profile={profile}
            stats={{ viewed: judged.length, matches: matches.length }}
            onBack={() => setView('deck')}
            onEdit={() => setModal('profile')}
          />
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
      {modal === 'matches' && (
        <MatchesModal
          matches={matches}
          onClose={() => setModal(null)}
          onSelectMatch={(match) => setActiveChat(match)}
        />
      )}

      {/* Плавающий мини-чат в правом нижнем углу экрана. Рендерится
          независимо от modal/view, поэтому остаётся на экране поверх
          и ленты анкет, и личного кабинета, и окна "Совпадения". */}
      {activeChat && <ChatWidget match={activeChat} onClose={() => setActiveChat(null)} />}
    </>
  );
}
