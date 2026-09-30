import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: false,
      },
      // MCP tool server (JSON-RPC + GET /mcp/manifest) lives outside /api
      "/mcp": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: false,
      },
    },
  },
});
