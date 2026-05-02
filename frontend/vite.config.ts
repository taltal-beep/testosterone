import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"]
  }
});
