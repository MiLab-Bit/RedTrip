# 红鸢 RedTrip · 微信小程序

AppID：`wxc7953007477c1980`

原生微信小程序，对接与 Web 版相同的 RedTrip API（`https://sy-realm.ltd/redtrip`）。

## 功能（MVP）

| 页面 | 路径 | 说明 |
|------|------|------|
| 出题 | `pages/brief` | 城市、起点联想、时长/调性/同伴等 chip，演示线秒开 |
| 装订 | `pages/loading` | 提交策展 + 轮询进度（L1/L2/L3 印章） |
| 序章 | `pages/intro` | 主题、人物、章节脉络 |
| 阅读 | `pages/reader` | 逐站故事正文 + 行前提示 |
| 失败 | `pages/fail` | 友好失败页 |

## 本地打开（微信开发者工具）

1. 打开 **微信开发者工具**
2. **导入项目** → 目录选本仓库的 `apps/miniprogram`
3. AppID 填 `wxc7953007477c1980`（已在 `project.config.json` 写好）
4. 开发阶段可在 **详情 → 本地设置** 勾选 **不校验合法域名**（或保持 `project.private.config.json` 里 `urlCheck: false`）
5. 编译运行即可

## 上线前必做

### 1. 服务器域名（微信公众平台）

在 [微信公众平台](https://mp.weixin.qq.com/) → 开发 → 开发管理 → 开发设置 → **服务器域名**：

| 类型 | 域名 |
|------|------|
| request 合法域名 | `https://sy-realm.ltd` |

### 2. API 轮询接口

小程序无 `EventSource`，使用：

- `POST /v1/curate/start` 提交任务
- `GET /v1/curate/status/{task_id}` 轮询进度（需 API 已部署含此路由的版本）

联调 API 地址在 `utils/config.js` 的 `API_BASE` 修改。

### 3. 上传代码

开发者工具 → **上传** → 在微信公众平台提交审核。

## 目录

```
apps/miniprogram/
  app.js / app.json / app.wxss
  project.config.json      # AppID 与编译设置
  project.private.config.json
  utils/                   # API、story 视图、默认值
  pages/brief|loading|intro|reader|fail/
  assets/kite.png
```

## 与 Web 的差异

- 无 Three.js 地图、无 PDF/EPUB 导出、无登录/BYOK（访客策展）
- 策展进度用 **HTTP 轮询** 替代 SSE
- 视觉延续纸面 + 朱砂配色，适配手机窄屏
