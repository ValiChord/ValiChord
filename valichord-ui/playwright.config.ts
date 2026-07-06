import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

const isCI = !!process.env.CI;
const UI_PORT = process.env.E2E_UI_PORT ?? '5178';

export default defineConfig({
  testDir: './tests/e2e/specs',

  // One conductor for the whole run (globalSetup) → shared DHT state.
  // Serial by design; see the header comment in core-flow.spec.ts.
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  // One CI retry absorbs conductor-startup flakes on loaded 2-core runners;
  // locally a failure should fail immediately for fast iteration.
  retries: isCI ? 1 : 0,

  // Holochain is slow on cold start: first zome call after install can hit
  // WASM JIT (minutes on a Codespace). Individual expects set their own
  // tighter timeouts once the app is warm.
  timeout: 240_000,
  expect: { timeout: 15_000 },

  reporter: [['list', { printSteps: true }], ...(isCI ? [['github'] as const] : [])],

  globalSetup: join(__dirname, 'tests/e2e/setup/global-setup.ts'),
  globalTeardown: join(__dirname, 'tests/e2e/setup/global-teardown.ts'),

  use: {
    // Specs always navigate via holochainUrl(), which carries the
    // #APP_PORT=&TOKEN=&CREDS= hash params; baseURL is a fallback only.
    baseURL: `http://localhost:${UI_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 720 } },
    },
  ],

  // Starts only the Vite dev server (on a port distinct from `npm run dev`).
  // The conductor is managed by globalSetup/globalTeardown, not here.
  webServer: {
    command: `npm run dev -- --port ${UI_PORT} --strictPort`,
    url: `http://localhost:${UI_PORT}`,
    reuseExistingServer: !isCI,
    timeout: 120_000,
  },

  outputDir: 'test-results',
});
