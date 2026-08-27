# 13 · 架构冻结（演示版 apps/web）

> 状态：**冻结** · 2026-08-06  
> 变更须更新本文 + ADR；禁止静默改主路径。

---

## 1. 冻结结论

| 项 | 决定 |
|---|---|
| 演示载体 | **`apps/web`**（Vite + React + TS） |
| 后端 | `apps/api`（FastAPI），Web 只打自家 API |
| 数据 | HTTP 直调上图（对齐 MCP）；默认可 `snapshot` 演示 |
| 契约 | `packages/contracts` Zod · `RouteEnvelope` |
| 地图 v1 | 示意图（SVG）优先；R3F 为增强轨 |
| 状态 | XState 管阶段；Zustand 管 UI 碎片；Query 管请求 |
| Key | 仅 API 进程 `.env`；Web 永不持有 |

---

## 2. 演示主路径（不可砍）

```
出题 → 策展 → 地图总览+策展词 → 漫步故事卡 → 多重人生 → 溯源 → 收尾
```

对应功能：F1–F9（见对话规划）；P1 加分项不挡封版。

---

## 3. 调用面（冻结）

| 调用 | 归属 |
|---|---|
| `building_detail` / `event_list(buri)` / `route_getEvent*` | library-client |
| `slc_era` / `souyun_poem` | 可选叠层 |
| R-20 whitelist | content/ |
| LLM | curator Narrative 阶段 only |
| Gate | packages/gate |

Web → 仅 `POST /v1/curate` + `GET /v1/health` +（可选）`GET /v1/whitelist`。

---

## 4. 质量 harness

项目 Skill：`.cursor/skills/redtrip-harness/SKILL.md`  
开发时自动约束：契约优先、取证铁律、海派 token、演示可跑。
