import { defineConfig } from 'vite';

// Browser-first: the app lives in app/ and imports shared logic from src/.
// `npm run dev` serves it; `npm run build` emits a static bundle to dist/.
export default defineConfig({
  root: 'app',
  publicDir: false,
  server: {
    // app/ imports shared logic from ../src — allow serving one level up.
    fs: { allow: ['..'] },
  },
  resolve: {
    alias: {
      // Allow `import ... from '@/gcode/generator.js'` from app code.
      '@': new URL('./src/', import.meta.url).pathname,
    },
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
  test: {
    // Vitest config lives here so tests run from the repo root.
    root: '.',
    environment: 'node',
    include: ['tests/**/*.test.js'],
  },
});
