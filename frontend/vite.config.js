import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, requests to /api are forwarded to the FastAPI server,
// so the frontend can call fetch("/api/...") with no CORS setup.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true, // also reachable from your phone on the same Wi-Fi
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
