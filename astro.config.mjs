// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  site: 'https://hugomiralles-manta.github.io',
  base: '/el-camino-site',
  vite: {
    plugins: [tailwindcss()]
  }
});
