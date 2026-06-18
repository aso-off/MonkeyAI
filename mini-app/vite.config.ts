import { fileURLToPath, URL } from 'node:url'
import { readFileSync } from 'node:fs'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import mkcert from 'vite-plugin-mkcert'

const pkg = JSON.parse(readFileSync(fileURLToPath(new URL('./package.json', import.meta.url)), 'utf-8'))

// https://vite.dev/config/
export default defineConfig(({ command }) => ({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  // GitHub Pages: https://aso-off.github.io/mini-app/
  base: '/mini-app/',
  // Read .env from mini-app/ (contains only VITE_API_URL - safe to keep local)
  envDir: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [
    vue(),
    command === 'serve' ? vueDevTools() : undefined,
    command === 'serve' && process.env.HTTPS ? mkcert() : undefined,
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  publicDir: './public',
  build: {
    target: 'esnext',
  },
  server: {
    host: true,
    allowedHosts: true,
  },
}))
