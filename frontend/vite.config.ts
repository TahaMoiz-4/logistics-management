import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Dev: the app calls relative /v1/... paths; Vite proxies them to the FastAPI
// backend so there are no CORS surprises. In prod, serve the built app behind
// the same origin (or set up an equivalent reverse proxy).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: Number(process.env.FRONTEND_PORT ?? 5173),
    proxy: {
      "/v1": {
        // Override when :8000 is taken by something else:
        //   BACKEND_URL=http://localhost:8011 npm run dev
        target: process.env.BACKEND_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
