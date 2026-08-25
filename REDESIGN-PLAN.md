# RedTrip 产品重构规划（吸收 Gemini 愿景 + 两轮 code review 落地）

> 目标：把 RedTrip 从「机械地理串联 / 模板电子垃圾」升级为「数据筛选驱动的策展型城市指南」。
> 本规划只落地**有价值的**部分，明确拒绝过度设计（GraphRAG / 纯 Agent 重命名）。
> 所有判断均经活仓库代码核验，不重复造轮子。

---

## 0. 现状基线（已落地，无需重做）

| 模块 | 状态 | 说明 |
|---|---|---|
| RAG 全量 POI 过滤层 | ✅ 已建 | `rag.py` 合并 OSM(1406) + amap(1235)，按场景/类别/时段预筛候选，纯本地无网络 |
| P0-1 门禁/润色误杀 | ✅ 已修 | `envelope.py` 统一阈值，长路线不再被误杀→回退模板 |
| P0-2 展览白名单 | ✅ 已修 | `points.json` 30 → 180 点（原锚点保留，新增诚实标记 `buri=None`）|
| Python 测试 + lint | ✅ 26 passed / ruff 0 | `tests/`（gate / plan / artifacts / rag / evidence / p0_2）|
| 质检门禁 Gate | ✅ 已有 | G4 溯源覆盖率 / Q2 source / Q7 pitfalls / Q8 禁用词 / R19 物理衔接 |
| 句子级溯源 | ✅ 已有 | `sentence_provenance.py`（本会话修过 F821）|
| 红队测试 | ✅ 已有 | `packages/gate/redteam/runner.py` + `cases.json` |
| 红鸢三层 Agentic RAG | ✅ 已有 | L1 取证 / L2 词库抽签 / L3 小红书周热词（`hongyuan.py`）|
| 前端双模组件 | ✅ 已存在 | `BookShell` / `MapScene25D` / `EventTimelineRail` / `StopPanel` / `SentenceProvenance` |

---

## 1. 端到端验证结论（2026-08-14，FastToken 网关 www.abc-ai.cn / Qwen-flash）

`scripts/e2e_validate.py` 跑通完整 `curate()` 管线（无 SLC key → 走 RAG 兜底 + 真实 LLM 润色）：

- **耗时 36.8s**，8 站路线，**`narrative=llm_polish`** —— 润色**真实生效**（P0-1 静默降级已根除）
- **Gate 通过**："叙事：红鸢润色已过 Gate"
- **幻觉防线生效**：`拒绝 story.5.body：未取证年份 ['1917']` —— 未查证年份被安全拦截
- 产出示例（stop.1 故事卡）：

  > 你站在中山东一路18号2层，脚下是1923年公和洋行建起的新古典主义穹顶。这栋楼原是英国渣打银行上海分行……托玛斯·杰克逊的名字没有刻在牌匾上，但他的手曾在这里写下第一道注脚——不是作为主人，而是作为那个让建筑开始「被照看」的人。

**验证同时暴露的真实缺口（直接转为重构任务）：**

1. **OSM 噪声 POI 入线**：北外滩「小巨蛋」「标识牌及黄浦江打卡位」「外滩轮渡口」等无叙事价值的原始 OSM 点被选中 → 需语料去噪。
2. **缺 event/person 实体层**：Gate 告警 `路线缺少多重身份点（building+event/person）` —— 正是 Gemini 报告点名的「无实体层」。
3. **展讯时效缺失**：无展览/活动数据源，路线无法绑定当下特展。

---

## 2. 吸收 Gemini 愿景：采纳 / 拒绝 清单

| 愿景项 | 判定 | 落地方式（不重复造轮子）|
|---|---|---|
| 套话黑名单 + 负向约束（融汇中西 / 值得一提的是 / 仿佛穿越回老上海 / 充满浓厚生活气息）| ✅ 采纳 | 扩 `gate.FORBIDDEN_COPY` + `polish.py` 负向提示，零新依赖 |
| 四段式叙事（序厅-焦点-暗线-尾厅）| ✅ 采纳 | `plan.py` 给每站打 `act` 标签，前端 `BookShell` 据此高亮节奏 |
| 动态展讯时效 API | ⚠️ 部分采纳 | 先建 `content/curated/exhibitions.json` 占位 + Gate 时效校验维度；待 amap key 接入实时 |
| 工业级 Quality Gates 量化矩阵 | ✅ 采纳方向 | 已有 gate，补「套话重叠率 / 事实匹配率 / 一次过率」量化指标 + `eval/` 脚本 |
| 多 Agent 重构（4 Agent 表）| ❌ 拒绝纯重命名 | 现有 `intent/evidence/plan/join/narrative/polish/hongyuan` 已是分解管线，改名不增值 |
| GraphRAG 知识图谱（Neo4j/networkx）| ❌ 拒绝 | 单城 ~2600 POI 用图库过度设计；保留现有 RAG 过滤层（更轻，已建且验证有效）|
| 前端双模联动 / 纸张质感 / 时间轴滤镜 | ✅ 采纳（组件已存在）| 接 `plan.act` 标签做 `flyTo` + 接 `sentence_provenance` 浮层 |

**核心原则**：Gemini 报告是**北极星叙事稿**（适合对外汇报/PPT），不是逐项立项清单。凡现有模块已覆盖的（Gate / 溯源 / 前端组件 / 三层 RAG），只**接线增强**，不重写。

---

## 3. 重构路线图（分阶段，可验收）

### Phase A — 数据层提质（1~2 周，收益最高、零新依赖）
- **A1 语料去噪**：`rag.py` 增加噪声过滤——剔除 `标识牌/无名绿地/轮渡口/小巨蛋` 等低叙事价值 OSM 点；用「类别白名单 + 名称/地址信号评分」保留建筑/博物馆/历史点。e2e 暴露的噪声直接消除。
- **A2 实体层注入**：在 RAG 语料 + `evidence` 阶段补 `event/person` 边（对接 SLC `landmark-facts` / 海派人物词条），消 Gate「缺多重身份点」告警，路线从「建筑串联」升维到「建筑×人物×事件」。
- **A3 展讯时效占位**：建 `content/curated/exhibitions.json`（博物馆/美术馆当前展），Gate 增加时效校验维度（Q 维度），先占位后接实时。

### Phase B — 生成质量升维（2~3 周）
- **B1 套话治理**：`FORBIDDEN_COPY` 扩 Gemini 那批文学套话；`polish.py` 注入负向约束（替代词表已在其报告中给出，直接复用）。
- **B2 四段式叙事**：`plan.py` 标注每站 `act ∈ {prologue,focus,transit,epilogue}`；前端 `BookShell` 高亮节奏。
- **B3 量化评估**：建 `eval/` 脚本，测「套话重叠率 / 事实匹配率 / 一次过率」，设基线 + 目标（套话 0%、事实 >98%、一次过 >95%）。
- **B4 红队扩例**：把 e2e 暴露的「噪声 POI / 无实体层」做成 `redteam/cases.json` 新用例。

### Phase C — 体验沉浸（3~4 周，组件已存在，主要是接线）
- **C1 双模联动**：`BookShell × MapScene25D` 接 `plan.act` 标签做 `flyTo` 高亮。
- **C2 时空滤镜**：`EventTimelineRail` 接 OSM/光影模型做 1930/正午/黄昏切换。
- **C3 溯源浮层**：`SentenceProvenance` 接 `sentence_provenance.py` 输出，点句看考据。

---

## 4. 量化验收指标

| 指标 | 当前 | 目标 |
|---|---|---|
| 套话出现率 | 未量化 | 0% |
| 事实幻觉率 | 未量化 | < 2% |
| 路线一次过率（Gate 首过）| 未量化 | > 95% |
| POI 噪声占比（入线）| e2e 显示 ~50% 北外滩点为噪声 | < 5% |
| 路线含有效特展率 | 0%（无数据源）| > 90%（接入后）|
| e2e 耗时 | 37s | < 60s |

---

## 5. 明确不做 / 阻塞项

- **不做** GraphRAG / Neo4j（单城数据量不值得）。
- **不做** 纯 Agent 重命名（管线已分解）。
- **阻塞**：`REDTRIP_AMAP_KEY` / `SLC_API_KEY` 本地缺失 → 影响 A2/A3 实时部分（占位可先行）。
- **阻塞**：`wrangler` 装不上 → Cloudflare Pages 部署；`purge_cache` 报 `method_not_allowed` → 缓存清理需手动。

---

## 6. 建议下一步（由本会话成果自然延伸）

立即落地 **A1 语料去噪 + B1 套话治理**：收益最高、零新依赖、可用现有 FastToken 网关直接 e2e 复验。
完成后重跑 `scripts/e2e_validate.py`，对比 `content/e2e/last_run.json` 验证噪声下降、套话归零。
