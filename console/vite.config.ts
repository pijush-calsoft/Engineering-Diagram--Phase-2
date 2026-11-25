import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The console API runs on 127.0.0.1:8765 (python -m edp_orchestrator.server).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
});
