import { defineConfig } from "vite";

export default defineConfig({
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
