# sy-realm.ltd 应用挂载

同一 SWAS + Cloudflare 命名隧道，统一挂在 `https://sy-realm.ltd/` 子路径：

| 路径 | 应用 | 静态目录 | 后端 |
|------|------|----------|------|
| `/` | 入口页 | `/www/wwwroot/sy-realm.ltd/index.html` | — |
| `/redtrip/` | 红鸢 RedTrip | `.../redtrip/` | `127.0.0.1:8799`（`/redtrip/v1/`） |
| `/vesta/` | Vesta｜迹与寻 | `.../vesta/` | 纯前端 |
| `/cardio/` | Card.io | `.../cardio/` | `127.0.0.1:8010`（`/cardio/api/`） |
| `/bizatlas/` | BizAtlas | `.../bizatlas/` | `127.0.0.1:8000`（`/bizatlas/v1/`） |

Nginx：`/etc/nginx/conf.d/sy-realm.ltd.conf` 与 `00-redtrip-default.conf`（隧道 Host 兜底）。

BizAtlas 前端需 `base=/bizatlas/`、`BrowserRouter basename=/bizatlas`、`VITE_API_BASE=/bizatlas`。
Cardio 前端已按 `/cardio` 构建；API 默认同源 `/cardio`。
