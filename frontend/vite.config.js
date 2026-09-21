import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Local dev: proxy API calls to the container/laptop API so the origin matches production.
    proxy: {
      "/chat": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/ui": "http://127.0.0.1:8000",
    },
  },
});
