import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';

export default function ChatWidget({ match, userId, onClose }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const listRef = useRef(null);
  const alive = useRef(true);
  const cursor = useRef(null);
  const didLoad = useRef(false);
  const path = '/matches/' + match.matchId + '/messages';

  function merge(incoming) {
    setMessages((prev) => {
      const byId = new Map([...prev, ...incoming].map((msg) => [msg.id, msg]));
      return [...byId.values()].sort((a, b) => BigInt(a.id) < BigInt(b.id) ? -1 : 1);
    });
  }
  useEffect(() => {
    alive.current = true;
    let stopped = false;
    let timer;
    const controller = new AbortController();
    async function poll() {
      try {
        const result = await api(path + (cursor.current ? '?after=' + cursor.current : ''), { signal: controller.signal });
        if (stopped) return;
        merge(result.messages);
        if (result.messages.length) cursor.current = result.messages.at(-1).id;
        if (!didLoad.current) { setHasMore(result.hasMore); didLoad.current = true; }
        setError('');
      } catch (err) {
        if (!stopped) setError(err.message);
      } finally {
        if (!stopped) { setLoading(false); timer = setTimeout(poll, 3000); }
      }
    }
    poll();
    return () => { alive.current = false; stopped = true; clearTimeout(timer); controller.abort(); };
  }, [path]);

  const lastId = messages.at(-1)?.id;
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [lastId]);

  async function older() {
    if (loadingOlder || !messages.length) return;
    setLoadingOlder(true);
    try {
      const result = await api(path + '?before=' + messages[0].id);
      if (!alive.current) return;
      merge(result.messages); setHasMore(result.hasMore); setError('');
    } catch (err) { if (alive.current) setError(err.message); }
    finally { if (alive.current) setLoadingOlder(false); }
  }
  async function submit(event) {
    event.preventDefault();
    const value = text.trim();
    if (!value || sending) return;
    setSending(true); setError('');
    try {
      const result = await api(path, { method: 'POST', body: { text: value } });
      if (alive.current) { merge([result.message]); setText(''); }
    } catch (err) { if (alive.current) setError(err.message); }
    finally { if (alive.current) setSending(false); }
  }

  return (
    <div className="chat-widget" role="dialog" aria-label={`Сообщения с ${match.name}`}>
      <div className="chat-widget-header">
        <img src={match.photo} alt={match.name} />
        <div className="info"><strong>{match.name}</strong><span>♪ {match.genre}</span></div>
        <button className="chat-widget-close" onClick={onClose} aria-label="Закрыть чат">×</button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="chat-widget-messages" ref={listRef}>
        {hasMore && <button className="btn-plain" onClick={older} disabled={loadingOlder}>Загрузить предыдущие</button>}
        {loading && <p className="chat-widget-empty">Загрузка сообщений…</p>}
        {!loading && !messages.length && <p className="chat-widget-empty">Сообщений пока нет — напишите первым.</p>}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-bubble-row ${msg.senderId === userId ? 'me' : 'them'}`}>
            <div className="chat-bubble">{msg.text}</div>
          </div>
        ))}
      </div>
      <form className="chat-widget-form" onSubmit={submit}>
        <input type="text" placeholder="Написать сообщение..." value={text}
          onChange={(e) => setText(e.target.value)} maxLength={2000} disabled={sending} />
        <button className="chat-widget-send" type="submit" disabled={sending || !text.trim()} aria-label="Отправить">→</button>
      </form>
    </div>
  );
}
