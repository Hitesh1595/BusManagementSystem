/// <reference types="vitest/config" />
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev: proxy API + Socket.IO to the FastAPI backend on :8000 so the SPA runs
// same-origin. This sidesteps CORS and makes the httpOnly SameSite=Strict
// refresh cookie (path /api/v1/auth) and the WebSocket upgrade work transparently.
const BACKEND = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/socket.io": { target: BACKEND, ws: true, changeOrigin: true },
      "/health": { target: BACKEND, changeOrigin: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("leaflet")) return "maps";
          if (id.includes("socket.io") || id.includes("engine.io")) return "realtime";
          return "vendor";
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
