import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

const isPagesBuild = process.env.GITHUB_ACTIONS === 'true';

export default defineConfig({
  site: isPagesBuild ? 'https://airtonlira.github.io' : 'http://localhost:4321',
  base: isPagesBuild ? '/boostprompt' : '/',
  integrations: [react()],
  vite: {
    build: {
      // Three.js stays in the lazily imported desktop-only canvas chunk.
      chunkSizeWarningLimit: 900,
    },
  },
});
