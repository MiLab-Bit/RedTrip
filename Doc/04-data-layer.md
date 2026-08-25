# 04 · 数据层（完整版）

> MCP 参考实现：`<local-path>/shanghai-library-mcp/`  
> 详细接入：[11-mcp-integration.md](./11-mcp-integration.md)

---

## 1. 三类输入

| 层 | 来源 | v1 权威 |
|---|---|---|
| 事实层 | 上图 webapi / 快照 | 取证必经 |
| 关系层 | `buri`→event_list；红事 uri；纪年 | S0-4 实测层数 |
| 地理层 | **R-20 白名单** | v1 唯一；S1 可回填 |

---

## 2. 上图能力地图（与 MCP 对齐）

### 2.1 MCP 12 Tools

| Tool | Key | RedTrip 用途 |
|---|---|---|
| `slc_endpoints` | 否 | 发现 / Spike |
| `slc_api` | 是 | 通用分发（主推程序内直调等价 HTTP） |
| `slc_building` | 是 | 快捷：`building_list?freetext=` |
| `slc_red_event` | 是 | 快捷：`route_getEventList` |
| `slc_era` | 是 | 纪年锚定 |
| `slc_raw` | 是 | 兜底 GET |
| `souyun_poem` | 否 | 诗词叠层 |
| `souyun_rhyme` / `couplet` | 否 | 一般不用 |
| `slc_jiapu` | 是 | v1 非核心 |
| `slc_datasets` / `sparql` | 否 | sparql 竞赛 Key 被拦，勿依赖 |

### 2.2 策展核心 Endpoints（`slc_api`）

| id | 参数 | 家族 | 策展角色 |
|---|---|---|---|
| `building_list` | freetext | 武康路历史 | 灌库 / 名称召回 |
| `building_detail` | uri | 武康路历史 | 建筑层 |
| `event_list` | **buri** | 武康路历史 | **跨库事件层（ASCII 主键）** |
| `persons_list` / `persons_detail` | pname / uri | 武康路历史 | 人物故事卡素材 |
| `road_list` / `road_detail` | freetext / uri | 武康路历史 | 马路线索 |
| `route_getEventList` | eventfreetext / eventdate | 红色旅游事件 | 红事召回 |
| `route_getEventDetail` | uri | 红色旅游事件 | 红事详情 |
| `architecture_architectureDetail` | uri | 近代城市文化 | 备选建筑深挖 |
| `geonames_detail` | uri | 地名志 | 地名补充 |
| `data_jsonld` / era | uri / term | 纪年 | 时代层 |

Key 传递：query `key=` 或环境变量 `SLC_API_KEY`（优先序：调用参数 > 环境变量）。

---

## 3. 主键与 Join 图

```
                    ┌─────────────┐
                    │  R-20 Point │ whitelist_id, lat/lng, pitfalls
                    └──────┬──────┘
                           │ optional buri
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        building_detail  event_list   （无 buri）
              │            │         仅红事/核录
              ▼            ▼
           layers[]     layers[]
              │            │
              └──── GraphJoin ────► IdentityLayer[]
                           │
              route_getEvent* / era / poem（弱）
```

**规则**：

1. 在线上游查询优先 `uri` / `buri` / 年份等 ASCII。  
2. 中文只打本地倒排或 Fuse。  
3. 无出处 → `gaps` +「暂无数据支撑」，禁止补编。

---

## 4. 本地索引

```
scripts/build_index.py
  → 分页 building_list（谨慎中文；灌库阶段控网络）
  → SQLite: buildings(buri, name, aliases, raw_json)
  → FTS/倒排: name_zh
  → 视图: whitelist_join (whitelist_id ↔ buri)
```

运行时：

```
用户中文 → FTS → buri[] ∩ whitelist
        → event_list(buri) + building_detail(uri)
        → EvidencePack
```

---

## 5. R-20 资产

路径：`content/whitelist/points.json`

```json
{
  "id": "wl-001",
  "name": "示例",
  "buri": null,
  "lat": 31.22,
  "lng": 121.47,
  "coord_source": "manual",
  "precision": "schematic",
  "open_hours": "未收录",
  "enterable": "未收录",
  "need_reservation": "未收录",
  "photo_spot": null,
  "district_tag": "一大周边",
  "verified_at": "2026-08-06",
  "field_sources": { "lat": "人工核录" }
}
```

NG-10：渲染不读 `coord_source` 分叉；只读 lat/lng/precision。

---

## 6. EvidencePack

```ts
type EvidencePack = {
  buildings: Array<{
    whitelist_id: string
    buri: string | null
    name: string
    layers: Array<{
      kind: "building" | "event" | "era" | "poem" | "person"
      claim: string
      source: { dataset: string; record_id: string; excerpt?: string }
    }>
  }>
  gaps: Array<{ subject: string; note: "暂无数据支撑" }>
  fetched_at: string
  mode: "snapshot" | "indexed" | "mcp"
}
```

---

## 7. 网络环境（已知坑）

| 现象 | 根因 | 处理 |
|---|---|---|
| TLS EOF 到 library.sh.cn | 本机代理 7897 拦截 | `SlcClient` 默认 `ProxyHandler({})` 直连 + 设置 `NO_PROXY` |
| 中文参数崩溃 | Windows 编码 / surrogate | `PYTHONUTF8=1`；主路径用 `buri`/`uri` |
| 误判缺 Key | TLS 失败长得像鉴权 | 跑 `scripts/s0_spike.py` |

**W3 实测（2026-08-06）**：`building_list` / `building_detail` / `event_list` / `route_getEventList` 均 200；样本 URI 见 `content/fixtures/live-sample.json`（若已生成）。

---

## 8. 地理范围诚实声明

`building_*` = **武康路历史**家族。  
产品 v1 = **梧桐区 + 一大周边 30 点**。  

因此：

- 能映射 `buri` 的点 → 冲「多重人生」  
- 不能映射的点 → 红事 + R-20 + 诚实 gaps  
- 对外层数口径以 S0-4 白名单实测为准，不写「全市建筑库」
