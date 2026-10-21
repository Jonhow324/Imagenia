import path from "node:path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The SPA is a separate document with its own React tree and CSS scope.
export default defineConfig({
  base: "./",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api/imagenia": "http://127.0.0.1:8765",
    },
  },
  build: {
    outDir: "dist/app",
    emptyOutDir: true,
  },
})
