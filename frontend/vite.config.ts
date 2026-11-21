import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The backend (FastAPI) listens on 127.0.0.1:8010 during development.
// In production the backend serves frontend/dist itself, so no proxy is involved.
const apiProxy = {
  '/api': {
    target: 'http://127.0.0.1:8010',
    changeOrigin: false,
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: apiProxy,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    proxy: apiProxy,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2020',
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    restoreMocks: true,
    include: ['src/**/*.test.{ts,tsx}'],
  },
});
