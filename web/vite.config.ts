import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API_URL is set in docker-compose; locally the API runs on :8000.
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {}

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': env.API_URL ?? 'http://localhost:8000' } },
})
