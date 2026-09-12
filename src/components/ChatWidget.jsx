import { useEffect, useRef, useState } from 'react';

export default function ChatWidget({ match, onClose }) {
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const listRef = useRef(null);


  useEffect(() => {
    setMessages([]);
  }, [match.id]);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  function submit(event) {
    event.preventDefault();
    const value = text.trim();
    if (!value) return;
    setMessages((prev) => [...prev, { from: 'me', text: value }]);
    setText('');
  }

  return (
    <div className="chat-widget" role="dialog" aria-label={`Сообщения с ${match.name}`}>
      <div className="chat-widget-header">
        <img src={match.photo} alt={match.name} />
        <div className="info">
          <strong>{match.name}</strong>
          <span>♪ {match.genre}</span>
        </div>
        <button className="chat-widget-close" onClick={onClose} aria-label="Закрыть чат">
          ×
        </button>
      </div>

      <div className="chat-widget-messages" ref={listRef}>
        {messages.length === 0 && (
          <p className="chat-widget-empty">Сообщений пока нет — напишите первым.</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-bubble-row ${msg.from}`}>
            <div className="chat-bubble">{msg.text}</div>
          </div>
        ))}
      </div>

      <form className="chat-widget-form" onSubmit={submit}>
        <input
          type="text"
          placeholder="Написать сообщение..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          className="chat-widget-send"
          type="submit"
          disabled={!text.trim()}
          aria-label="Отправить"
        >
          →
        </button>
      </form>
    </div>
  );
}
