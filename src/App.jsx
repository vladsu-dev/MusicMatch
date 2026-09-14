import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import { GENRES } from './data/genres.js';
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
  const [feed, setFeed] = useState([]);
  const [matches, setMatches] = useState([]);
  const [stats, setStats] = useState({ viewed: 0, matches: 0 });
  const [view, setView] = useState('deck');
  const [activeChat, setActiveChat] = useState(null);
  const [booting, setBooting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const epoch = useRef(0);
  const requestId = useRef(0);

  const reset = useCallback(() => {
    epoch.current++;
    requestId.current++;
    setSession(null); setProfile(null); setModal(null);
    setFeed([]); setMatches([]); setStats({ viewed: 0, matches: 0 });
    setView('deck'); setActiveChat(null);
  }, []);

  const loadData = useCallback(async () => {
    const generation = epoch.current;
    const id = ++requestId.current;
    const [nextFeed, nextMatches, nextStats] = await Promise.all([
      api('/feed'), api('/matches'), api('/me/stats'),
    ]);
    if (epoch.current !== generation || id !== requestId.current) return;
    setFeed(nextFeed.profiles); setMatches(nextMatches.matches); setStats(nextStats);
  }, []);

  const restore = useCallback(async () => {
    const generation = epoch.current;
    setBooting(true); setError('');
    try {
      const result = await api('/auth/session');
      if (generation !== epoch.current) return;
      setSession(result.user); setProfile(result.profile);
    } catch (err) {
      if (err.status !== 401) setError('Не удалось связаться с сервером: ' + err.message);
    } finally { setBooting(false); }
  }, []);

  useEffect(() => {
    const expired = () => { reset(); setError('Сессия завершена. Войдите снова.'); };
    window.addEventListener('musicmatch:unauthorized', expired);
    restore();
    return () => { epoch.current++; window.removeEventListener('musicmatch:unauthorized', expired); };
  }, [restore, reset]);

  useEffect(() => {
    if (!session || !profile) return;
    let cancelled = false;
    setBusy(true);
    loadData().catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [session?.id, profile, loadData]);

  // Pick up mutual likes made by another user without reloading the page.
  useEffect(() => {
    if (!session || !profile) return;
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const data = await api('/matches');
        if (!cancelled) setMatches(data.matches);
      } catch (err) { if (!cancelled && err.status !== 401) setError(err.message); }
      if (!cancelled) timer = setTimeout(poll, 10_000);
    };
    timer = setTimeout(poll, 10_000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [session?.id, Boolean(profile)]);

  async function logout() {
    setBusy(true); setError('');
    try { await api('/auth/logout', { method: 'POST' }); reset(); }
    catch (err) { setError('Не удалось выйти: ' + err.message); }
    finally { setBusy(false); }
  }
  function onAuthSuccess(result) {
    epoch.current++;
    setError(''); setSession(result.user); setProfile(result.profile);
    setModal(result.profile ? null : 'profile');
  }
  async function onProfileSaved(next) {
    const generation = epoch.current;
    const result = await api('/me/profile', { method: 'PUT', body: next });
    if (generation !== epoch.current) return;
    setProfile(result.profile); setModal(null); setError('');
  }
  async function onDecide(target, action) {
    const generation = epoch.current;
    const result = await api('/decisions/' + target.id, { method: 'POST', body: { action } });
    if (generation !== epoch.current) return null;
    setFeed((prev) => prev.filter((item) => item.id !== target.id));
    if (result.match) setMatches((prev) => [result.match, ...prev.filter((m) => m.matchId !== result.match.matchId)]);
    // The decision is committed even if the subsequent refresh is unavailable.
    try { await loadData(); }
    catch (err) { setError('Оценка сохранена, но лента не обновилась: ' + err.message); }
    return result.match;
  }
  async function restartFeed() {
    await api('/feed/reset', { method: 'POST' });
    await loadData();
  }
  async function retry() {
    setError('');
    if (!session) return restore();
    setBusy(true);
    try { if (profile) await loadData(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <>
      <header className="header">
        <div className="logo">Music Match</div>
        <div className="header-actions">
          {session ? (
            <>
              {profile && (
                <button className="header-user" aria-pressed={view === 'account'} onClick={() => setView('account')}>
                  <img className="avatar" src={profile.photo} alt="" /><span>{profile.name}</span>
                </button>
              )}
              {profile && (
                <button className="btn-plain" onClick={() => setModal('matches')}>
                  Совпадения{matches.length > 0 && <span className="badge">{matches.length}</span>}
                </button>
              )}
              <button className="btn-plain" onClick={() => setModal('profile')}>{profile ? 'Моя анкета' : 'Заполнить анкету'}</button>
              <button className="btn-plain" onClick={logout} disabled={busy}>Выйти</button>
            </>
          ) : (
            <button className="btn-plain" onClick={() => setModal('login')} disabled={booting}>Войти</button>
          )}
        </div>
      </header>
      <main>
        {error && (
          <div className="form-error" role="alert">
            {error} <button className="btn-plain" onClick={retry} disabled={busy || booting}>Повторить</button>
          </div>
        )}
        {booting ? <p className="hint">Проверяем вход…</p> : (
          <>
            {!session && <Banner genres={GENRES} onStart={() => setModal('auth')} />}
            {session && !profile && (
              <section className="banner">
                <h1>Остался один шаг — <em>ваша анкета</em></h1>
                <p>Имя, фото и любимый жанр. После этого откроются анкеты других участников.</p>
                <button className="btn btn-lg" onClick={() => setModal('profile')}>Заполнить анкету</button>
              </section>
            )}
            {session && profile && view === 'deck' && (
              busy ? <p className="hint">Загружаем анкеты…</p> :
                <Deck feed={feed} onDecide={onDecide} onRestart={restartFeed} keyboardEnabled={!modal && !activeChat} />
            )}
            {session && profile && view === 'account' && (
              <AccountPage profile={profile} stats={{ ...stats, matches: matches.length }}
                onBack={() => setView('deck')} onEdit={() => setModal('profile')} />
            )}
          </>
        )}
      </main>
      {(modal === 'auth' || modal === 'login') && (
        <AuthModal initialTab={modal === 'login' ? 'login' : 'register'} onClose={() => setModal(null)} onSuccess={onAuthSuccess} />
      )}
      {modal === 'profile' && session && (
        <ProfileModal profile={profile} genres={GENRES} onClose={() => setModal(null)} onSaved={onProfileSaved} />
      )}
      {modal === 'matches' && session && (
        <MatchesModal matches={matches} onClose={() => setModal(null)}
          onSelectMatch={(match) => { setModal(null); setActiveChat(match); }} />
      )}
      {activeChat && session && (
        <ChatWidget key={activeChat.matchId} match={activeChat} userId={session.id} onClose={() => setActiveChat(null)} />
      )}
    </>
  );
}
