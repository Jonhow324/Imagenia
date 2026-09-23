import { defineConfig } from "vite"

// Run after the SPA build. Do not remove dist/app when writing the host entry.
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: false,
    lib: {
      entry: "src/index.ts",
      formats: ["es"],
      fileName: () => "index.js",
    },
  },
})
