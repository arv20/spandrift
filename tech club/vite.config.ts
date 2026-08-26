/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// For GitHub Pages project-site deployment:
// Set the VITE_BASE_PATH env var to your repo name, e.g. "/find-your-tech-path/"
// Or edit the fallback string below to match your repository name.
const base = process.env.VITE_BASE_PATH || '/opensourceproject/';

export default defineConfig({
  plugins: [react()],
  base,
  build: {
    outDir: 'dist',
  },
  css: {
    modules: {
      localsConvention: 'camelCase',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
});
