// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

// Env-aware config:
//   - Default (no env)  → GitHub Pages (hugomiralles-manta.github.io/el-camino-site)
//   - ASTRO_BASE + ASTRO_SITE set → FTP deployment (preview or root)
// The FTP workflow sets these variables at build time.
const site = process.env.ASTRO_SITE ?? 'https://hugomiralles-manta.github.io';
const base = process.env.ASTRO_BASE ?? '/el-camino-site';

// https://astro.build/config
export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  vite: {
    plugins: [tailwindcss()]
  }
});
