import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return;
          }
          if (
            id.includes("/react/") ||
            id.includes("/react-dom/") ||
            id.includes("react/jsx-runtime") ||
            id.includes("react/jsx-dev-runtime") ||
            id.includes("scheduler")
          ) {
            return "react-vendor";
          }
          if (id.includes("react-router-dom")) {
            return "router";
          }
          if (id.includes("@tanstack/react-query")) {
            return "react-query";
          }
          if (id.includes("recharts")) {
            return "charts";
          }
          if (id.includes("framer-motion")) {
            return "motion";
          }
          if (id.includes("@radix-ui")) {
            return "radix";
          }
          return "vendor";
        },
      },
    },
  },
}));
