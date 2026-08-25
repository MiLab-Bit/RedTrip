import { defineConfig } from "vitest/config";

// 前端基础测试配置。
// 默认 node 环境（当前覆盖纯函数/契约校验，不引入 jsdom）。
// 后续若加组件测试，可在对应 *.test.tsx 顶部用 `// @vitest-environment jsdom` 覆盖。
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    globals: false,
  },
});
