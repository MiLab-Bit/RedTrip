# 07 · 前端与 2.5D

> 产品设计全文：[`../../产品设计/2.5D视图产品设计.md`](../../产品设计/2.5D视图产品设计.md)  
> 前端工程分层 / FSM / 雷达采纳：[`12-frontend-architecture.md`](./12-frontend-architecture.md)

---

## 1. 职责

前端只做三件事：

1. **出题与假设展示**  
2. **消费 RouteEnvelope 渲染**（地图 / 卡片 / 漫步）  
3. **本地体验状态**（当前点、断点续走、溯源抽屉开关）

不做：取证、改史实、猜开放时间。

---

## 2. 页面信息架构

```
/                     出题（6 槽位，极简）
/route/:id            地图主视图 + 策展词
/route/:id/stop/:n    点位故事卡 / 时间轴层
（本地）              溯源抽屉、进度、收尾卡
```

竞赛可单页状态机，不必真路由——但逻辑分区按上表。

---

## 3. 渲染管线

```
RouteEnvelope
  → stops[].geo + order     → 路线 ribbon / 序号
  → curator_note            → 开篇
  → transition_to_next      → 点间文案
  → blocks.story_card       → 卡片轨
  → layers + source         → 时间轴 / 溯源
  → pitfalls                → 避坑条（未收录也展示）
```

### v1 演示版（当前默认）

- **R3F 2.5D 意象城景**：节点按真实 lat/lng 落位；英雄节点加重；走廊体量为意象填充  
- 高度一律标「示意」——**未接 OSM footprint 前不冒充测绘挤出**  
- WebGL 失败 → SVG `MapSchematic` 降级（序号/连线仍齐全）

### S1 真 footprint（下一刀）

```
Overpass OSM building → 简化 → 挤出
R3F: toon + 海派 6 色；走廊真实轮廓替换意象方块
英雄节点 2–3 个加重；高度缺省标示意
```

---

## 4. 组件边界（建议）

| 组件 | 输入 | 说明 |
|---|---|---|
| `BriefForm` | slots | 出题；缺槽显示假设 |
| `MapCanvas` | route.stops | 示意图或 R3F；只读 geo |
| `CuratorLead` | curator_note | 开篇 |
| `StopCard` | story_card / stop | 漫步主卡片 |
| `LayerTimeline` | layers | 「多重人生」 |
| `SourceDrawer` | SourceRef | 原文片段 |
| `ProgressDock` | local progress | 可断可续 |

---

## 5. 美学实现清单

- [ ] CSS 变量写入 6 色，扫样式禁止硬编码第七色  
- [ ] 标签衬线体  
- [ ] `precision !== exact` → 角标「示意」  
- [ ] 固定数据来源角标：上海图书馆 ·（OSM）· 人工核录  
- [ ] 禁用效率话术文案进 UI 微文案库  

---

## 6. 性能

- 只渲染当前路线走廊  
- 移动端：关软阴影、降 DPR、ribbon 降级线段  
- 首屏：先画骨架，再挂卡片  

---

## 7. 状态

建议 Zustand：

```ts
type TripUIState = {
  phase: "brief" | "loading" | "map" | "walk" | "done"
  envelope: RouteEnvelope | null
  currentStop: number
  visited: number[]
  sourceOpen: SourceRef | null
}
```

断点续走：`localStorage` 存 `routeId + currentStop`；任意点终止都有收尾态。
