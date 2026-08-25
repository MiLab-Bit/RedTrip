# RedTrip 前端（Vite + React）-> 静态产物由 nginx 托管
# 构建上下文（context）必须是 RedTrip 仓库根目录。
# ---- 构建阶段 ----
FROM node:20-slim AS build
WORKDIR /app
# 安装与 packageManager 一致的 pnpm
RUN npm install -g pnpm@9.15.0
# 复制 workspace 清单与源码（web 依赖 @redtrip/contracts workspace 包）
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY packages/contracts ./packages/contracts
COPY apps/web ./apps/web
RUN pnpm install --frozen-lockfile || pnpm install
# 先构建 contracts（web 的类型/契约来源），再构建 web
RUN pnpm --filter @redtrip/contracts build
RUN pnpm --filter @redtrip/web build
# 构建产物：apps/web/dist

# ---- 运行阶段 ----
FROM nginx:alpine AS runtime
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 5173
CMD ["nginx", "-g", "daemon off;"]
