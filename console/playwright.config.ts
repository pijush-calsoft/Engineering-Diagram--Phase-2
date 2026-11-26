import { defineConfig } from "@playwright/test";

// End-to-end tests of the console (plan §4.3: Playwright). They start their own console API on
// port 8766 with freshly generated synthetic samples, and use the installed Microsoft Edge, so
// no browser download is needed. Chat answers are mocked in the browser: no model calls.
const PORT = 8766;
const DATA = "var/e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: "msedge",
    headless: true,
    viewport: { width: 1600, height: 940 },
    launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] },
  },
  webServer: {
    cwd: "..",
    command: [
      `uv run python -m edp_eval.synth --out ${DATA}/golden --count 2 --seed 7 --uri-prefix s3://edp-fabric/e2e`,
      `uv run python -m edp_eval.synth --out ${DATA}/models --models 1 --seed 3 --uri-prefix s3://edp-fabric/e2e`,
      `uv run python -m edp_orchestrator.server --data-dir ${DATA}/console --golden ${DATA}/golden ${DATA}/models --port ${PORT}`,
    ].join(" && "),
    url: `http://127.0.0.1:${PORT}/api/blocks`,
    timeout: 180_000,
    reuseExistingServer: false,
  },
});
