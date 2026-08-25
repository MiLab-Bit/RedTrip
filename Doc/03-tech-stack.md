# 03 · 技术选型（雷达采纳版）

> 完整雷达清单：`frontend-research-radar.md`（微信文件 / 产品设计副本）  
> 本地源码镜像：`<local-path>/frontend-radar/`（`owner__repo` 命名）  
> 原则：按**状态所有权 / 渲染管线 / 执行位置**选型，不按页面堆库。

---

## 1. 总表（Adopt）

| 层 | 选型 | 本地参考 | 理由 |
|---|---|---|---|
| 语言 | TypeScript + Python | — | Web 强类型；MCP/取证 Python 成熟 |
| Web 框架 | React 19 + Vite | — | R3F 生态默认 |
| Schema | **Zod** | `colinhacks__zod` | 前后端契约运行时校验 |
| UI 状态 | **Zustand** | `pmndrs__zustand` | 轻量，不抢画布状态 |
| 行程状态机 | **XState** | `statelyai__xstate` | brief→load→map→walk→done 显式化 |
| 服务端态 | **TanStack Query** | `TanStack__query` | curate 请求、骨架/全量 |
| 表单 | TanStack Form 或受控轻表单 | `TanStack__form` | 6 槽位足够简单，可先手写 |
| 2.5D | **R3F + Drei** | `pmndrs__react-three-fiber` / `pmndrs__drei` | extruded 示意；可降级 SVG |
| 手势 | `@use-gesture/react` | 雷达 1.3 | 地图旋转缩放 |
| 动效 | Motion（原 Framer） | 雷达 3.2 | 卡片进场 2–3 处，忌堆特效 |
| 模糊搜 | Fuse.js（可选） | `krisk__Fuse` | 前端白名单点名检索 |
| 关系示意（可选） | React Flow | `xyflow__xyflow` | 「多重人生」层关系小图，非主地图 |
| API | **FastAPI** | — | 与 library-client 同语言 |
| 数据客户端 | 自研 library-client | 参考桌面 MCP | HTTP 直调 + 可选 MCP stdio |
| 本地索引 | SQLite | — | 倒排 + buri |
| 质检 | Zod + Python rules | 产品设计 redteam | 阻断自动化 |
| 包管理 | pnpm workspaces + uv/pip | — | JS/Python 分治 |

---

## 2. 雷达分层 → RedTrip 映射

### Layer 0 横切（Adopt 精简）

| 雷达项 | RedTrip |
|---|---|
| Zustand | UI：抽屉、当前点、主题偏好 |
| XState | TripFSM（唯一流程权威） |
| TanStack Query | `useCurateMutation` / skeleton poll |
| Zod | `packages/contracts` |

**Hold**：Redux、Jotai（除非出现细粒度订阅瓶颈）、Yjs/Liveblocks（P2 协同）。

### Layer 1 原语

| 雷达项 | RedTrip |
|---|---|
| R3F + Drei | MapCanvas 主路径 |
| use-gesture | 地图交互 |
| React Flow | 可选：单点 Identity 层小图 |
| Radix / shadcn | **Trial**：只要海派视觉不被默认组件污染；竞赛可自研基础控件 |

**Hold**：Docking/Dashboard Grid、tldraw、Konva 主路径、Babylon（过重）。

### Layer 2 领域

| 雷达项 | RedTrip |
|---|---|
| vis-timeline | Trial：点位时间轴（多重人生） |
| Fuse / Orama | 白名单本地搜 |
| Vercel AI SDK / LangGraph | **Hold v1**：策展流水线自研六阶段，避免黑盒 |

### Layer 3 美学

| 雷达项 | RedTrip |
|---|---|
| Tailwind | Adopt：仅承载 **海派 6 色 token**，禁止默认紫系模板 |
| Motion | Adopt：有限叙事动效 |
| Lenis / 粒子 / Shader | Hold：与明信片气质冲突 |

### Layer 4 邻接服务端

| 雷达项 | RedTrip |
|---|---|
| tRPC | Hold（Python API） |
| BullMQ / Temporal | Hold（竞赛无队列需求） |

---

## 3. 后端 / 数据栈

| 组件 | 选型 |
|---|---|
| API | FastAPI + uvicorn |
| Curator | 纯 Python 包，阶段函数可单测 |
| LLM | OpenAI 兼容 HTTP（环境变量） |
| 上图 | `data1.library.sh.cn` webapi + `SLC_API_KEY` |
| 搜韵 | `api.sou-yun.cn/open` 免 Key |
| MCP 参考实现 | `<local-path>/shanghai-library-mcp/slc_mcp_server.py` |

---

## 4. 美学技术锁

| Token | 值 |
|---|---|
| ink | `#33333A` |
| ochre | `#B9824F` |
| slate | `#7C8A8D` |
| rice | `#EDE4D3` |
| vermilion | `#A8322A` |
| xuan | `#F2EBDD` |

超出 6 色 = Gate Q6 失败。标签衬线（思源宋体）。flat + toon outline。

---

## 5. 环境变量（见 `.env.example`）

```
SLC_API_KEY=
SLC_MCP_SERVER=          # 可选：slc_mcp_server.py 绝对路径
NO_PROXY=*.library.sh.cn,library.sh.cn,sou-yun.cn,api.sou-yun.cn
PYTHONUTF8=1
LLM_API_BASE=
LLM_API_KEY=
LLM_MODEL=
REDTRIP_MODE=indexed     # snapshot | indexed | mcp
```

---

## 6. 不选清单（写明以免回潮）

- 实景三维上海 / 测绘院底板  
- 浏览器内持有竞赛 Key  
- 为抬客单引入真人调度  
- 主界面 Ant Design / Material 默认皮肤  
- 运行时中文关键词直打上游作主路径  
