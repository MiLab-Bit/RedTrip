import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

/**
 * 部署基路径。
 *
 * RedTrip 有两个部署目标，base 不同，历史上靠人工在命令行补 `--base`，
 * 一旦忘记，子路径部署会因为 index.html 里写成 `/assets/...` 而白屏。
 * 现改为读环境变量，并把两个目标的构建命令固化到 package.json：
 *   - Cloudflare Pages（https://redtrip.pages.dev，站点根）→ base "/"
 *   - 自建 nginx 子路径（https://abc-ai.cn/redtrip/）→ base "/redtrip/"
 */
const BASE = process.env.VITE_BASE ?? "/";

export default defineConfig({
  base: BASE,
  plugins: [react()],
  resolve: {
    alias: {
      "@redtrip/contracts": path.resolve(
        __dirname,
        "../../packages/contracts/src/index.ts",
      ),
    },
  },
  build: {
    // 3D 场景 chunk 天生较大，750KB 的默认告警只会制造噪音；
    // 真正的约束是「首屏 chunk 要小」，已由 manualChunks + lazy 保证。
    chunkSizeWarningLimit: 1600,
    rollupOptions: {
      output: {
        /**
         * 手动分包：把首屏必需与地图专用彻底分开。
         *
         * 关键收益——three/@react-three 约 1.2MB，只有 `map` 状态用得到。
         * 独立成 chunk 后配合 App.tsx 里的 lazy(MapStage)，这 1.2MB 从
         * 首屏关键路径上摘掉，首屏只需 react-core（约 150KB）。
         */
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          // three 生态自成一体，独立成懒加载 chunk（仅 map 状态用）
          if (
            id.includes("three") ||
            id.includes("@react-three") ||
            id.includes("react-reconciler")
          ) {
            return "three-scene";
          }
          // 状态层：zustand/xstate 及 zustand 依赖的 use-sync-external-store 聚在一处，
          // 消除 vendor↔state-core 循环；@xstate/* 显式归入，避免被下方 /react/ 规则误抓
          if (
            id.includes("@xstate") ||
            id.includes("xstate") ||
            id.includes("zustand") ||
            id.includes("use-sync-external-store")
          ) {
            return "state-core";
          }
          if (
            id.includes("react-dom") ||
            id.includes("scheduler") ||
            id.includes("react-is") ||
            id.includes("/react/")
          ) {
            return "react-core";
          }
          return "vendor";
        },
      },
    },
  },
  server: {
    port: 5173,
    fs: {
      allow: [path.resolve(__dirname, "../..")],
    },
    proxy: {
      "/v1": {
        // Dev API (see .env API_PORT; default 8799)
        target: "http://127.0.0.1:8799",
        changeOrigin: true,
      },
      // 生产路径（与 nginx /redtrip/* 对齐）；dev 默认 authConfig API_ROOT=/redtrip
      "/redtrip/v1": {
        target: "http://127.0.0.1:8799",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/redtrip\/v1/, "/v1"),
      },
      "/redtrip/auth/v1": {
        target: "http://127.0.0.1:8799",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/redtrip\/auth\/v1/, "/v1"),
      },
      // 兼容旧前缀（auth-core 已合并进 redtrip-api，8787 不再独立部署）
      "/auth/v1": {
        target: "http://127.0.0.1:8799",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/auth\/v1/, "/v1"),
      },
    },
  },
});
