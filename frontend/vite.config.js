import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const BACKEND_PORT = process.env.VITE_BACKEND_PORT || "8000";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
      },
      "/ocr": {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
      },
    },
  },
});
