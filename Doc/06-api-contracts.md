# 06 · API 与数据契约

> 契约是前后端唯一交界。改字段必须同步 `packages/contracts` 与本文。

---

## 1. HTTP API（v1）

### `POST /v1/curate`

请求：

```json
{
  "message": "想和对象走 90 分钟，梧桐区，不要说教",
  "slots": {
    "audience": null,
    "scene": "梧桐区",
    "duration_min": 90,
    "tone": "轻社交",
    "delivery": "路线",
    "companions": "2人"
  },
  "retry_count": 0
}
```

响应（成功）：

```json
{
  "status": "ok",
  "phase": "full",
  "envelope": { "...": "见 §2 RouteEnvelope" },
  "meta": {
    "latency_ms": 42000,
    "assumptions": ["默认人群=成人"],
    "gate": { "passed": true, "warnings": [] }
  }
}
```

响应（门禁失败且不可再试）：

```json
{
  "status": "degraded",
  "reasons": ["Q8: 出现效率话术"],
  "envelope": null
}
```

### `GET /v1/health`

数据源可达性、索引版本、白名单点数。

### `GET /v1/whitelist`

返回 30 点位公开字段（供地图预热；不含内部备注）。

---

## 2. RouteEnvelope（核心）

```ts
type RouteEnvelope = {
  intent: string
  theme: string
  logic_line: string
  aesthetic: string
  scenario: string
  why_visit: string
  curator_note: string          // R-19 开篇
  assumptions: string[]
  companions: "solo" | "duo" | "small_group"
  sources: string[]             // 调用过的数据集/工具名
  route: {
    duration_min: number
    walk_meters_est: number
    stops: RouteStop[]
  }
  blocks: Block[]               // 故事卡等
}

type RouteStop = {
  order: number
  whitelist_id: string
  buri: string | null
  name: string
  minutes: number
  meaning: string
  transition_to_next: string | null  // 史实衔接；最后一站 null
  layers: IdentityLayer[]
  geo: GeoPoint
  pitfalls: {
    open_hours: string
    enterable: string
    need_reservation: string
  }
}

type IdentityLayer = {
  kind: "building" | "event" | "era" | "poem"
  label: string
  claim: string
  source: SourceRef
}

type SourceRef = {
  dataset: string
  record_id: string
  excerpt?: string
}

type GeoPoint = {
  lat: number
  lng: number
  /** manual | upstream | none */
  coord_source: "manual" | "upstream" | "none"
  /** exact | approximate | schematic */
  precision: "exact" | "approximate" | "schematic"
}

type Block =
  | {
      type: "story_card"
      stop_order: number
      title: string
      body: string              // 第二人称
      age_parallel?: string     // 年龄对照句
      sources: SourceRef[]
    }
  | {
      type: "scene"
      stop_order: number
      place: string
      era_desc: string
      figures: string
      city_thread: string
      today: string
      visual_note: string
    }
  | {
      type: "card"
      title: string
      lead: string
      keywords: string[]
      body: string
      coda: string
    }
```

---

## 3. NG-10 契约约束

1. `GeoPoint` 字段集合在示意图版与真坐标版**完全一致**。  
2. S1 回填只允许：改 `lat/lng` + 改 `coord_source` / `precision`。  
3. **禁止**新增「schematic_lat」之类平行字段。  
4. 前端渲染函数签名：`render(stop.geo)`，不得 `if (coord_source === 'manual')` 分叉业务逻辑。  
5. `precision !== 'exact'` 时 UI 必须显示「示意」。

验收：Given 已渲染示意图路线，When 只回填坐标并翻转标记，Then 无需改代码即可出真坐标版。

---

## 4. 首屏 vs 全量

| 字段 | 首屏骨架（≤60s） | 全量（≤180s） |
|---|---|---|
| theme / route.stops 基础 | ✅ | ✅ |
| geo / 序号 / 距离估 | ✅ | ✅ |
| curator_note / transitions | ✅ 优先 | ✅ |
| story_card blocks | 可延迟 | ✅ |
| scene / 导出素材 | 可延迟 | ✅ |

API 可用 `phase: "skeleton" | "full"`，或同连接分块返回（实现自定，契约字段稳定）。

---

## 5. 版本策略

- 契约版本字段：`envelope_version: "1.0"`（实现时加上）  
- 破坏性变更：升主版本，旧前端不接新后端  
- 文档与 Zod schema 同 PR 修改
