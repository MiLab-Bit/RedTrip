# RedTrip 技术文档索引

本目录是**工程落地文档**，回答「怎么建」。  
产品「建什么、为什么」见 [`../../产品设计/`](../../产品设计/)。

---

## 阅读顺序（新人 / 开工）

| 顺序 | 文档 | 读完应知道 |
|---|---|---|
| 1 | [01-product-scope.md](./01-product-scope.md) | v1 范围、Non-goals、不可砍需求 |
| 2 | [02-architecture.md](./02-architecture.md) | **完整系统架构**、三模式、模块边界 |
| 3 | [03-tech-stack.md](./03-tech-stack.md) | 雷达 Adopt 表与本地镜像路径 |
| 4 | [04-data-layer.md](./04-data-layer.md) | 上图 endpoints、join、R-20 |
| 5 | [11-mcp-integration.md](./11-mcp-integration.md) | Key、HTTP 优先、Spike |
| 6 | [05-agent-pipeline.md](./05-agent-pipeline.md) | 策展六阶段 |
| 7 | [06-api-contracts.md](./06-api-contracts.md) | RouteEnvelope、NG-10 |
| 8 | [12-frontend-architecture.md](./12-frontend-architecture.md) | 前端分层 / FSM / R3F |
| 9 | [07-frontend-2.5d.md](./07-frontend-2.5d.md) | 2.5D 视觉与降级 |
| 10 | [08-quality-gates.md](./08-quality-gates.md) | 门禁、红队 |
| 11 | [09-directory-layout.md](./09-directory-layout.md) | 代码树 |
| 12 | [10-milestones.md](./10-milestones.md) | S0–S4 |
| 13 | [13-architecture-freeze.md](./13-architecture-freeze.md) | 演示版冻结结论 |
| 14 | [14-dev-tasks.md](./14-dev-tasks.md) | W0–W7 代码任务 |
| 15 | [15-demo-script.md](./15-demo-script.md) | 90 秒演示口播 + 录屏备援 |

---

## ADR

| ADR | 主题 |
|---|---|
| [001](./adr/001-no-human-guide.md) | 不配真人领队 |
| [002](./adr/002-coordinate-swappable.md) | 坐标源可替换（NG-10） |
| [003](./adr/003-offline-first-index.md) | 离线索引优先 |
| [004](./adr/004-http-first-mcp.md) | HTTP 直调优先于 MCP 子进程 |

---

## 外部参考（本机）

| 资源 | 路径 |
|---|---|
| 前端雷达镜像 | `<local-path>/frontend-radar/` |
| 雷达完整清单 | [`../../产品设计/frontend-research-radar.md`](../../产品设计/frontend-research-radar.md) |
| 上图 MCP | `<local-path>/shanghai-library-mcp/` |
| 环境变量模板 | [`../.env.example`](../.env.example) |

---

## 文档与 PRD 的关系

```
产品设计/PRD          →  需求、验收、口径（权威）
RedTrip/Doc/          →  架构、契约、实现约束（工程权威）
RedTrip/apps|packages →  代码（实现）
```

冲突时：**验收口径以 PRD 为准；实现细节以本目录 ADR + 契约为准。**
