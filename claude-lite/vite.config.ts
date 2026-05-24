import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig(async () => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: "es2022",
    minify: "esbuild",
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (id.includes("react-syntax-highlighter") || id.includes("refractor")) {
              return "vendor-syntax";
            }
            if (id.includes("react-markdown") || id.includes("remark") || id.includes("micromark")) {
              return "vendor-markdown";
            }
            if (id.includes("@xterm")) {
              return "vendor-xterm";
            }
            if (id.includes("react-dom") || id.includes("react/") || id.includes("scheduler")) {
              return "vendor-react";
            }
          }
        },
      },
    },
  },
}));
