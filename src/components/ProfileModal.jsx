import { useState } from 'react';
import Modal from './Modal.jsx';

const MAX_SIDE = 720;

function readAndResize(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Не удалось прочитать файл'));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => reject(new Error('Файл не похож на изображение'));
      image.onload = () => {
        const scale = Math.min(1, MAX_SIDE / Math.max(image.width, image.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(image.width * scale);
        canvas.height = Math.round(image.height * scale);
        canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.82));
      };
      image.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

export default function ProfileModal({ profile, genres, onClose, onSaved }) {
  const [name, setName] = useState(profile?.name || '');
  const [genre, setGenre] = useState(profile?.genre || '');
  const [photo, setPhoto] = useState(profile?.photo || '');
  const [error, setError] = useState('');

  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);

  async function pickPhoto(event) {
    const file = event.target.files?.[0];
    if (!file || busy || reading) return;
    if (!file.type.startsWith('image/') || file.size > 10 * 1024 * 1024) return setError('Выберите изображение размером до 10 МБ');
    setReading(true);
    setError('');
    try {
      setPhoto(await readAndResize(file));
    } catch (err) {
      setError(err.message);
    } finally { setReading(false); }
  }

  async function submit(event) {
    event.preventDefault();
    if (busy || reading) return;
    if (name.trim().length < 2) return setError('Укажите имя (минимум 2 символа)');
    if (!photo) return setError('Добавьте фото');
    if (!genre) return setError('Выберите музыкальный жанр');
    setError('');
    setBusy(true);
    try { await onSaved({ name: name.trim(), genre, photo }); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <Modal onClose={() => { if (!busy && !reading) onClose(); }} width={480}>
      <h2>{profile ? 'Моя анкета' : 'Заполните анкету'}</h2>
      <p className="subtitle">Так вас увидят другие пользователи.</p>

      <form onSubmit={submit}>
        {error && <p className="form-error">{error}</p>}

        <div className="field">
          <label htmlFor="profile-name">Имя</label>
          <input
            id="profile-name"
            type="text"
            placeholder="Как вас зовут"
            value={name}
            onChange={(e) => setName(e.target.value)}
            minLength={2}
            maxLength={40}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="profile-photo">Фото</label>
          <div className="photo-picker">
            {photo ? (
              <img className="photo-preview" src={photo} alt="Предпросмотр фото" />
            ) : (
              <div className="photo-preview empty">+</div>
            )}
            <div>
              <input
                id="profile-photo"
                type="file"
                accept="image/*"
                onChange={pickPhoto}
                style={{ display: 'none' }}
              />
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => document.getElementById('profile-photo').click()}
              >
                {photo ? 'Заменить фото' : 'Загрузить фото'}
              </button>
            </div>
          </div>
        </div>

        <div className="field">
          <label>Музыкальный жанр</label>
          <div className="genre-grid">
            {genres.map((item) => (
              <button
                key={item}
                type="button"
                className="chip"
                aria-pressed={genre === item}
                onClick={() => setGenre(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        <div className="form-footer">
          <button className="btn" type="submit" disabled={busy || reading}>
            {reading ? 'Обработка фото…' : busy ? 'Сохранение…' : 'Сохранить анкету'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
