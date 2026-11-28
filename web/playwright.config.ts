// End-to-end checks of the built site (CI, after `npm run build` with fixtures). The Worker is
// mocked per test; prepared answers come from a mocked file, so no model or key is involved.
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  testMatch: "*.e2e.ts",
  timeout: 30_000,
  use: { baseURL: "http://localhost:4173", ...devices["Desktop Chrome"] },
  webServer: { command: "node scripts/serve-out.mjs 4173", url: "http://localhost:4173/roshni-site/en/", reuseExistingServer: false },
});
