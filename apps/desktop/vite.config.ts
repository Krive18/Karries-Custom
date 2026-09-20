import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { resolve } from "node:path";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const proxyTarget = (
    env.VITE_API_PROXY_TARGET || env.BACKEND_API_URL || ""
  ).trim();
  if (command === "serve" && mode !== "test" && !proxyTarget) {
    throw new Error(
      "VITE_API_PROXY_TARGET must be set for local development API proxying"
    );
  }
  const portalBuilds = {
    customer: {
      input: "index.html",
      outDir: "dist/customer-renderer"
    },
    manager: {
      input: "manager.html",
      outDir: "dist/manager-renderer"
    },
    developer: {
      input: "developer.html",
      outDir: "dist/developer-renderer"
    }
  } as const;
  const portal =
    mode === "manager" || mode === "developer" ? mode : "customer";
  const portalBuild = portalBuilds[portal];
  return {
    plugins: [tailwindcss(), react()],
    base: "./",
    server: proxyTarget ? {
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true
        }
      }
    } : undefined,
    build: {
      outDir: portalBuild.outDir,
      emptyOutDir: true,
      rollupOptions: {
        input: resolve(__dirname, portalBuild.input)
      }
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/renderer/test/setupTests.ts"
    }
  };
});
