import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs on :8000 and Vite proxies /api to it.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    watch: process.env.ACF_WATCH_POLL ? { usePolling: true, interval: 300 } : undefined,
    proxy: { "/api": { target: process.env.ACF_API ?? "http://127.0.0.1:8000", changeOrigin: false } },
  },
});
