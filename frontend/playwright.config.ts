import { defineConfig } from "@playwright/test"

const port = Number(process.env.E2E_PORT || 4173)

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${port}`,
    port,
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
