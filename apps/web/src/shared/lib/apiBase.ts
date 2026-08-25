/**
 * API 基址（构建期注入）。
 *
 * - 默认 `/redtrip`：与 authConfig 的 API_ROOT 统一，dev 由 vite 代理
 *   （/redtrip/v1 → 8799，见 vite.config.ts）重写为 /v1，prod 由 nginx
 *   （location /redtrip/v1/ 剥前缀后转 8799）承接——零环境依赖。
 *   修复：此前默认留空（"/v1" 根相对），prod 构建未注入 VITE_API_BASE 时
 *   会打到 nginx 没有路由的 /v1/*，导致策展/足迹/热词请求 404。
 * - Cloudflare Pages 部署：构建时注入
 *   `VITE_API_BASE=https://www.abc-ai.cn/redtrip`（或 https://redtrip.pages.dev 的反代地址），
 *   浏览器直接跨域（同源 HTTPS）调用，无需经 Pages Function 反代
 *   （Cloudflare 不允许 Worker 向自身橙色代理的主机发子请求）。
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/+$/, "") ??
  "/redtrip";
