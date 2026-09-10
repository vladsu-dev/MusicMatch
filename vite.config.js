import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'client',
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    host: '127.0.0.1', // иначе Vite слушает только IPv6 и не открывается на части машин
    port: 5173,
    // Запросы к /api уходят на Express, поэтому CORS не нужен.
    proxy: { '/api': 'http://localhost:3001' },
  },
});
