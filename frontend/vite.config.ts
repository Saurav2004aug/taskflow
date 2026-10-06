import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, Vite serves the UI on :5173 and forwards /api to Flask on :5000,
// so the browser sees one origin (no CORS), exactly like production.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:5000",
      "/health": "http://127.0.0.1:5000",
    },
  },
});
