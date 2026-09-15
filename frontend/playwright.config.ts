import { defineConfig, devices } from '@playwright/test';

const API_PORT = Number(process.env.E2E_API_PORT ?? 8010);
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5180);
const API_URL = `http://127.0.0.1:${String(API_PORT)}`;

export const E2E_API_KEY = process.env.E2E_API_KEY ?? 'e2e-key';

/*
 * Runs the real stack: FastAPI (against a test database) + the Vite app proxying /api to it.
 * Each test uses its own uniquely named game, so tests are isolated without truncating tables.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  timeout: 30_000,
  expect: { timeout: 7_500 },
  use: {
    baseURL: `http://127.0.0.1:${String(WEB_PORT)}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      name: 'api',
      cwd: '../backend',
      command: `uv run alembic upgrade head && uv run uvicorn app.main:app --host 127.0.0.1 --port ${String(API_PORT)} --log-level warning`,
      url: `${API_URL}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        DATABASE_URL:
          process.env.E2E_DATABASE_URL ?? 'postgresql://postgres:postgres@localhost:5432/lbserv_test',
        API_KEY: E2E_API_KEY,
        SENTRY_DSN: '',
        CORS_ORIGINS: '[]',
      },
    },
    {
      name: 'web',
      command: `npx vite --host 127.0.0.1 --port ${String(WEB_PORT)} --strictPort`,
      url: `http://127.0.0.1:${String(WEB_PORT)}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: { API_PROXY_TARGET: API_URL, VITE_SENTRY_DSN: '' },
    },
  ],
});
