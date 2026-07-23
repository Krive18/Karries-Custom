import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const developerBuild = mode === "developer";
  return {
    plugins: [react()],
    base: "./",
    build: {
      outDir: developerBuild ? "dist/developer-renderer" : "dist/renderer",
      emptyOutDir: true,
      rollupOptions: {
        input: resolve(
          __dirname,
          developerBuild ? "developer.html" : "index.html"
        )
      }
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/renderer/test/setupTests.ts"
    }
  };
});
