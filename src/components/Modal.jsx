import { useEffect } from 'react';

export default function Modal({ onClose, children, width }) {
  useEffect(() => {
    const onKey = (event) => event.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={width ? { maxWidth: width } : undefined} role="dialog" aria-modal="true">
        {/* Крестик есть в каждом модальном окне приложения, потому что
            рисуется здесь, в общей оболочке. Просто вызывает onClose,
            который каждый вызывающий компонент передаёт по-своему
            (обычно — setModal(null) или setMatched(null)). */}
        <button className="modal-close" onClick={onClose} aria-label="Закрыть">
          ×
        </button>
        {children}
      </div>
    </div>
  );
}
