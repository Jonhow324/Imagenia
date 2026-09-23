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
  build: {
    outDir: "dist/app",
    emptyOutDir: true,
  },
})
