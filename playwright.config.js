import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/browser',
  timeout: 120000,
  expect: { timeout: 60000 },
  workers: 1,
  use: { baseURL: process.env.OPENSWING_BASE_URL || 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 }, headless: true,
         launchOptions: { executablePath: process.env.OPENSWING_CHROMIUM_EXECUTABLE,
                          args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } },
  // The static-app fixture owns its HTTP server; it must not also start Vite.
  webServer: process.env.OPENSWING_BASE_URL || process.env.OPENSWING_STATIC_APP ? undefined : { command: 'npm run dev -- --port 5173', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 30000 },
});
