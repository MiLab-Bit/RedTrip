# 12 · 前端架构（雷达落地）

> 选型依据：完整雷达清单 + `c:\Dev\frontend-radar` 本地镜像。  
> 产品视觉：[07-frontend-2.5d.md](./07-frontend-2.5d.md) · [2.5D 视图产品设计](../../产品设计/2.5D视图产品设计.md)

---

## 1. 分层（按状态所有权）

```
┌─────────────────────────────────────────────────────────┐
│ App Shell                                                │
│  海派 token · 字体 · 数据来源角标 · 单页阶段               │
└─────────────────────────────────────────────────────────┘
┌──────────────┬──────────────────────┬───────────────────┐
│ Brief        │ Map Surface          │ Walk / Cards      │
│ 6 slots      │ R3F | SVG schematic  │ story · timeline  │
│ assumptions  │ ribbon · markers     │ source drawer     │
└──────────────┴──────────────────────┴───────────────────┘
        │                  │                    │
   TripFSM(XState)   local R3F state      Zustand UI bits
        │
   TanStack Query ──► POST /v1/curate (skeleton/full)
        │
   Zod RouteEnvelope（packages/contracts）
```

---

## 2. TripFSM（XState）

```
brief → loading → map → walking → done
              ↘ failed / degraded
```

| 状态 | 允许 UI |
|---|---|
| brief | 出题、显示默认假设 |
| loading | 骨架进度；禁二次提交 |
| map | 总览 + 策展词；点选进入 walking |
| walking | 当前 stop；可断可续；溯源 |
| done | 收尾卡 |
| degraded | 展示 Gate reasons |

地图 camera **不属于** FSM context。

---

## 3. 目录（apps/web）

```
src/
  app/                 # providers: query, fsm, theme tokens
  features/
    brief/
    map/               # MapCanvas, Ribbon, Marker, SchematicFallback
    walk/              # StopCard, LayerTimeline, SourceDrawer
    trip/              # machine.ts, selectors
  shared/
    ui/                # 极简控件（或薄封装 Radix）
    lib/api.ts
    lib/geo.ts
  styles/tokens.css    # 仅 6 色 + 宣纸底
```

---

## 4. 渲染管线策略

| 模式 | 技术 | 触发 |
|---|---|---|
| Schematic（默认 v1） | SVG / Canvas2D 节点连线 | 无 OSM；满足 Q5 |
| Immersive 2.5D | R3F + Drei extrude | S1+ 或演示增强 |
| Degrade | 静态长图 | 裁剪序列第三档 |

同一 `stops[].geo` 输入；切换渲染器，不切换契约（NG-10）。

**英雄节点**：2–3 点加重；其余走廊不抢戏。

---

## 5. 从雷达 Adopt 的具体用法

| 库 | 用法 | 不要这样用 |
|---|---|---|
| Zod | `RouteEnvelope.parse(data)` 入口校验 | 在组件里手写松散 any |
| Zustand | `sourceOpen` / `visited` | 存 envelope 全量（用 Query + FSM） |
| XState | 阶段切换唯一真相 | 用布尔旗汤 |
| TanStack Query | curate mutation + 缓存上次成功线 | 自己写 loading 竞态 |
| R3F/Drei | 地图场景 | 用它做表单/文案页 |
| Motion | 卡片 enter/exit 2–3 处 | 粒子/炫光 |
| Fuse | 白名单点名客户端滤 | 替代后端取证 |
| React Flow | 可选 Identity 小图 | 替代城市地图 |

本地研读路径示例：

```
c:\Dev\frontend-radar\pmndrs__zustand
c:\Dev\frontend-radar\pmndrs__react-three-fiber
c:\Dev\frontend-radar\pmndrs__drei
c:\Dev\frontend-radar\colinhacks__zod
c:\Dev\frontend-radar\statelyai__xstate
c:\Dev\frontend-radar\TanStack__query
c:\Dev\frontend-radar\xyflow__xyflow
c:\Dev\frontend-radar\krisk__Fuse
```

完整清单副本（产品设计目录）：[`../../产品设计/frontend-research-radar.md`](../../产品设计/frontend-research-radar.md)

---

## 6. 线程与性能预算

| 工作 | 线程 |
|---|---|
| 文案 / FSM / Query | 主线程 |
| R3F 渲染 | 主线程 GPU；控制 DPR |
| 多边形简化（若 OSM） | Worker（后期） |
| 门禁色板扫描 | build 时 / CI，非每帧 |

移动端：关软阴影、降 DPR、ribbon→线段。

---

## 7. 无障碍与文案

- 溯源角标可键盘聚焦  
- 「示意」不止颜色编码  
- UI 微文案遵守 Q8：无「一键/省事」  

---

## 8. 与后端契约

只消费 `RouteEnvelope`。  
发现字段缺失 → 前端降级占位，**不**调用 LLM 补史实。
