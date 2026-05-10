import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  clearScreen: false,

  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
    watch: {
      ignored: [
        "**/src-tauri/**",
        "**/target/**",
        "**/.git/**",
        "**/node_modules/**",
        "**/.venv/**",
        "**/__pycache__/**",
        "../../backend/**",
        "../../workspace/**",
        "../../docker/**",
      ],
    },
  },

  envPrefix: ["VITE_", "TAURI_"],
});
