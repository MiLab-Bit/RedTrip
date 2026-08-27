# 05 · Curator Agent 流水线

> 产品原则见 [`../../产品设计/总Prompt_v2_文化策展Agent.md`](../../产品设计/总Prompt_v2_文化策展Agent.md)。  
> 取证数据源见 [`04-data-layer.md`](./04-data-layer.md) · [`11-mcp-integration.md`](./11-mcp-integration.md)。  
> 本文描述**可编码的阶段与接口**。

---

## 1. 阶段总览

```
IntentParse
  → EvidenceFetch
  → GraphJoin
  → RoutePlan
  → NarrativeGen   # 含 R-19 策展说明 + R-06 故事卡
  → QualityGate
  → RouteEnvelope
```

每一阶段输入输出类型化；失败可降级的在阶段内声明，不可降级的抛给 Gate。

---

## 2. 阶段说明

### 2.1 IntentParse（R-01）

**输入**：用户自然语言或表单槽位  
**输出**：`IntentSlots`

| 槽位 | 说明 | 默认 |
|---|---|---|
| audience | 人群 | 成人 |
| scene | 场景（含出发点） | 梧桐区 / 一大周边 |
| duration_min | 时长 | 90 |
| tone | 文艺 / 硬核 / 轻社交 | 轻松（轻社交） |
| delivery | 交付形态 | 路线 |
| companions | 独自 / 2人 / 3–4人 | 2人 |

**补全协议**：缺 ≥3 项才追问 **1** 问；否则用默认并在 `assumptions[]` 显式声明。

### 2.2 EvidenceFetch（R-02）

- 仅在白名单 30 点内取证  
- 本地索引 → `buri` → 详情/事件  
- 产出 `EvidencePack`；空结果进 `gaps`  
- **禁止**在本阶段调用 LLM 编史实

### 2.3 GraphJoin（R-03）

对候选建筑堆叠身份层：

| 层 | 最低要求 |
|---|---|
| building | 必有 |
| event | 保底：路线中 ≥1 点具备 |
| era / poem | 尽力；无则不声称 |

对外层数口径跟随 S0-4 / M0 拍板（两重或三重）。

### 2.4 RoutePlan（R-04）

约束：

- 点数 5–8  
- 总时长 ≤120min（默认目标 90）  
- 步行顺序合理（可用直线距离启发式；v1 不做完整导航）  
- 同参不同兴趣 → 点位差异目标 ≥40%（可用兴趣标签加权）

输出：有序 `stops[]` + 预估分钟。

### 2.5 NarrativeGen（R-06 / R-19）

必须产出：

1. **开篇策展词**：回答「为什么是这几个点」  
2. **点间衔接**：100% 史实线索（出现「步行可达」当主理由 → Gate 失败）  
3. **故事卡**：第二人称 + 年龄对照；每点 ≥1；路线 ≥3 条非通识细节且带出处  

文案红线（阻断）：

- ❌ 一键 / 省事 / 省时  
- ❌ 口号、表态引导、神剧化、编队隐喻  
- ✅ 具体细节 + 人的处境

### 2.6 QualityGate（R-07）

见 [08-quality-gates.md](./08-quality-gates.md)。  
FAIL → 结构化 reasons；API 最多重生成 1 次。

---

## 3. LLM 使用边界

| 可用 LLM | 禁止 LLM |
|---|---|
| 槽位理解、叙事润色、策展词组织 | 生成无 source 的事实句 |
| 在已取证 claims 上改写语气 | 「合理补全」开放时间/坐标 |
| 从 EvidencePack 选句 | 伪造 dataset / record_id |

提示词资产：复用总 Prompt v2；润色落地为 `packages/curator/prompts/polish_narrative.txt`。  
环境变量：`LLM_API_BASE` + `LLM_API_KEY`（+ 可选 `LLM_MODEL`）。未配置则始终模板叙事。

---

## 4. 伪代码

```python
def curate(req: CurateRequest) -> CurateResult:
    intent = parse_intent(req)                  # IntentParse
    evidence = fetch_evidence(intent)           # EvidenceFetch — 禁止 LLM
    graph = join_layers(evidence)               # GraphJoin
    plan = plan_route(intent, graph)            # RoutePlan
    draft = narrate(intent, plan, graph)        # NarrativeGen（模板，证据绑定）
    polished = polish(draft) if LLM else draft  # 仅润色语气
    envelope = polished if gate(polished).ok else draft
    verdict = gate(envelope)                    # QualityGate 终检
    if verdict.failed:
        if req.retry_count < 1:
            return curate(req.with_retry())
        return degrade(envelope, verdict.reasons)
    return ok(envelope)
```

---

## 5. 与前端的分工

| Agent | 前端 |
|---|---|
| 取证、缝合、选点、叙事 JSON | 地图渲染、卡片模板、断点续走 |
| source 标注 | 溯源抽屉展示 |
| 机位文案（P1） | 机位卡版式 |
| 不渲染 2.5D | 不编史实 |
