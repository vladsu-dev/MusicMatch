function vinylPhoto(from, to, label) {
  const rings = Array.from(
    { length: 9 },
    (_, i) => `<circle r="${96 + i * 16}" fill="none" stroke="#3b3835" stroke-width="3"/>`
  ).join('');

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 750">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${from}"/>
        <stop offset="1" stop-color="${to}"/>
      </linearGradient>
    </defs>
    <rect width="600" height="750" fill="url(#bg)"/>
    <g transform="translate(300,335)">
      <circle r="238" fill="#211f1d"/>
      ${rings}
      <circle r="80" fill="${label}"/>
      <circle r="22" fill="#f4f1ec"/>
    </g>
  </svg>`;

  return `data:image/svg+xml,${encodeURIComponent(svg.replace(/\s+/g, ' '))}`;
}

export const DEMO_PROFILES = [
  { id: 1, name: 'Аня', genre: 'Инди', likesYou: true, photo: vinylPhoto('#e8765c', '#f2b49f', '#c75840') },
  { id: 2, name: 'Марк', genre: 'Рок', likesYou: false, photo: vinylPhoto('#4e6094', '#93a2c9', '#3b4a75') },
  { id: 3, name: 'Лиза', genre: 'Электроника', likesYou: true, photo: vinylPhoto('#68a8a0', '#a9d5cf', '#4d8880') },
  { id: 4, name: 'Тимур', genre: 'Хип-хоп', likesYou: false, photo: vinylPhoto('#b08c54', '#d9bf93', '#8e6f3d') },
  { id: 5, name: 'Соня', genre: 'Джаз', likesYou: true, photo: vinylPhoto('#8c6ca8', '#c0a9d3', '#6f5288') },
  { id: 6, name: 'Женя', genre: 'Классика', likesYou: false, photo: vinylPhoto('#789060', '#b3c69b', '#5c7047') },
  { id: 7, name: 'Ким', genre: 'Инди', likesYou: true, photo: vinylPhoto('#cc8484', '#e8b9b9', '#a96565') },
  { id: 8, name: 'Олег', genre: 'Метал', likesYou: false, photo: vinylPhoto('#5c5c64', '#9b9ba4', '#43434a') },
];
