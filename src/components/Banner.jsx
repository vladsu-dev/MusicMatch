export default function Banner({ genres, onStart }) {
  return (
    <section className="banner">
      <h1>
        Знакомьтесь с теми, кто слушает <em>то же, что и вы</em>
      </h1>
      <p>
        Заполните анкету, укажите любимый жанр — и листайте анкеты людей с похожим музыкальным
        вкусом.
      </p>
      {/* Единственное действие для гостя: открывает AuthModal (onStart
          передан из App.jsx и ставит modal в 'auth', т.е. вкладку
          "Регистрация"). */}
      <button className="btn btn-lg" onClick={onStart}>
        Зарегистрироваться
      </button>

      <div className="genre-marquee">
        {genres.slice(0, 10).map((genre) => (
          <span key={genre}>{genre}</span>
        ))}
      </div>
    </section>
  );
}
