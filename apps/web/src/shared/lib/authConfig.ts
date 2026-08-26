/**
 * API 访问前缀。
 * - 开发：默认 `/redtrip`，由 vite 代理把 `/redtrip/v1`、`/redtrip/auth/v1`
 *   反代到本机 redtrip-api（8799，见 vite.config.ts）。
 * - 生产：构建时注入 VITE_API_BASE（如 https://sy-realm.ltd/redtrip），前端无需改源码。
 *   nginx 把 `/redtrip/v1` 与 `/redtrip/auth/v1` 反代到 redtrip-api(8799)。
 *   auth-core 已合并进 redtrip-api，不再独立部署于 8787。
 */
const API_ROOT: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/redtrip";

/** 认证相关（注册/登录/验证等）：<root>/auth/v1 */
export const AUTH_BASE = `${API_ROOT}/auth/v1`;
/** 业务 API（模型配置等）：<root>/v1 */
export const API_BASE = `${API_ROOT}/v1`;
