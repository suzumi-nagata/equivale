import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// BASE_PATH é definido pelo GitHub Actions (actions/configure-pages).
// Localmente, o site roda em "/".
const rawBase = process.env.BASE_PATH || '/'
const base = rawBase.endsWith('/') ? rawBase : `${rawBase}/`

export default defineConfig({
  base,
  plugins: [react()],
})
