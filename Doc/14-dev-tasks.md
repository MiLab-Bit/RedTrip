# 14 · 代码任务规划（W0–W7）

> 目标：可演示的 `apps/web`。按依赖排序，不按页面平铺。

---

## 总览

```
W0 契约+假数据
 → W1 Web 可点通（假 API）
 → W2 真 API 壳
 → W3 library-client
 → W4 Curator
 → W5 Gate
 → W6 R-20/快照
 → W7 演示打磨
```

---

## W0 · 契约与脚手架（当前）

- [x] pnpm workspace + `apps/web` Vite React TS（源码已落盘）
- [x] `packages/contracts`：IntentSlots / GeoPoint / RouteEnvelope Zod
- [x] `content/fixtures/demo-route.json` 一条可渲染假线（一大周边意象）
- [x] `packages/contracts` 导出类型给 web（Vite alias 直指 src）
- [x] 根 README 补充 `pnpm dev`
- [x] Node 22.18 已安装到 `%LOCALAPPDATA%\RedTripToolchain\node`；`pnpm install` 完成

**完成定义**：`import { RouteEnvelopeSchema } from '@redtrip/contracts'` 能 parse 假数据。

---

## W1 · Web 演示壳（假数据）

- [x] TripFSM：brief → loading → map → walking → done / degraded
- [x] BriefForm 6 槽位 + 默认假设条
- [x] MapSchematic：序号/连线/示意坐标
- [x] StopPanel：故事卡 + 多重身份层 + 溯源抽屉 + 避坑
- [x] 海派 6 色 tokens.css
- [x] 先读 fixture，不依赖后端
- [x] `pnpm typecheck` 通过；dev server 已可启

**完成定义**：不启动 API 也能完整点完一条演示线。

---

## W2 · API 薄层

- [x] FastAPI `GET /v1/health` `POST /v1/curate` `GET /v1/whitelist`
- [x] 先返回 fixture envelope（mode=snapshot）
- [x] web 改打 `/v1/curate`；Vite proxy → 8787；CORS 本机
- [x] `.env` 加载（gitignored）；工具链 Python + venv
- [x] 冒烟：直连 API + 经 Vite 代理均 `status=ok` / 6 stops

**完成定义**：`pnpm dev` + `uvicorn` 联调成功。

---

## W3 · library-client

- [x] 策展核心 endpoints 注册（对齐 MCP）
- [x] `SlcClient.call` + building/event/red_event + 默认绕过代理
- [x] `scripts/s0_spike.py`；API `GET /v1/slc/probe`、`/v1/health?probe=true`
- [x] 实测：`building_list` / `building_detail` / `event_list` / `route_getEventList` 均 200

**完成定义**：脚本能拉到至少 1 条 building_detail 或明确降级。  
**实测样本 URI**：`http://data.library.sh.cn/entity/architecture/sm4repfu8n3ga66j`

---

## W4 · Curator

- [x] Intent → Evidence → Join → Plan → Narrative（模板叙事，无瞎编）
- [x] Narrative 仅引用 EvidencePack + gate_lite
- [x] LLM stub（W4 不接模型；结构已预留）
- [x] API `REDTRIP_MODE=indexed` 走 Curator，失败回退 snapshot
- [x] 冒烟：`ok=True` / 6 stops / sources=building_list+detail+event_list；样本 `content/fixtures/curated-live.json`

**完成定义**：白名单内生成 1 条可溯路线（或 snapshot 等价）。

---

## W5 · Gate

- [x] `packages/gate`：Q2/Q6/Q7/Q8/R19 + A1/A5 + 告警项
- [x] 红队 12 条（`cases.json`）全通过
- [x] Curator 出口改接 `evaluate_envelope`；重试封顶 1
- [x] API：`POST /v1/gate/check`；health 标记 `gate: true`

**完成定义**：故意注入口号体被拦截。

---

## W6 · 内容资产

- [x] `content/whitelist/points.json`：30 点（一大周边 + 梧桐区）
- [x] `content/whitelist/buri-map.json`：能连的 buri 已映射；未映射诚实留空
- [x] Curator 优先 R-20 buri 取证；geo/pitfalls 读白名单（NG-10）
- [x] API `GET /v1/whitelist` 读 points.json；health 标记 whitelist
- [x] fixtures：`demo-route` 仍为 snapshot 演示线；`scripts/build_whitelist.py` 可重刷

---

## W7 · 演示打磨

- [x] 90 秒脚本：`Doc/15-demo-script.md`
- [x] 备份录屏路径：`%USERPROFILE%\Videos\RedTrip\`（主片 + snapshot 备片）
- [x] 移动端：≤860px 顶栏堆叠、触控按钮、单列地图/步行
- [x] degraded UI：可读原因 + snapshot / 录屏备援提示

---

## 并行规则

- W1 不阻塞等 W3；先假数据  
- W3/W4 与 W1 视觉可并行  
- 任何新增 P0 必须自带对冲（PRD 纪律）
