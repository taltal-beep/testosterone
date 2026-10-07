import { defineConfig } from "vite";

export default defineConfig({
  // "/" for local dev and the API-served build; the GitLab Pages job sets
  // VITE_BASE to the project subpath the site is published under (e.g. "/testosterone/").
  base: process.env.VITE_BASE || "/",
  server: {
    port: Number(process.env.PORT) || 5173,
    strictPort: false
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"]
  }
});
