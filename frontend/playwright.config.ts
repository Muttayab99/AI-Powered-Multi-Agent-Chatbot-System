import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

// End-to-end tests run against a real gateway serving the built app (npm run build first).
// It uses its own port so it doesn't clash with a server you already have running on 8000.
const PORT = Number(process.env.E2E_PORT ?? 8010)
const root = path.resolve(import.meta.dirname, '..')
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

export default defineConfig({
  testDir: './e2e',
  timeout: 120_000,
  expect: { timeout: 60_000 },
  // Every test shares one gateway (and its CPU-heavy model loading), so run them one at a time.
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: `"${python}" -m servers.unified`,
    cwd: root,
    url: `http://localhost:${PORT}/api/health`,
    env: { GATEWAY_PORT: String(PORT) },
    timeout: 300_000,
    reuseExistingServer: !process.env.CI,
  },
})
