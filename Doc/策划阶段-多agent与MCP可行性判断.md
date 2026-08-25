# 策划阶段「多 agent / MCP」可行性判断（基于代码）

> 范围：策划阶段 = 意图理解（`intent.py`）+ 命题策划（`proposition.py`），不含用户研究。
> 原则：基于代码事实判断，不拍脑袋；不需要的，直接否决。

---

## 结论先行

| 议题 | 判断 | 一句话理由 |
|---|---|---|
| 意图理解多 agent 化 | **否决** | 现状是规则填槽，唯一缺口是 `message` 自由文本未利用，单次 LLM 抽取即可 |
| 命题策划多 agent 编排 | **否决** | 已是单调用+内联红队，唯一值钱的是「生成/批判分离」，一处轻量重构即可 |
| 数据层 MCP 化 | **否决** | 内部函数调用已够好，MCP 是给外部 agent 的协议，强加即过度设计 |
| 辅助 skills / MCP | **否决**（产品运行时） | skill 是开发期工具；provider 注册表已做函数级数据源接入，无需 MCP |
| 命题策划 propose/critique 分离 | **采纳（唯一）** | 消除自我辩护偏差，批判走本地小模型控成本 |

---

## 一、现状（代码事实）

### 意图理解 `intent.py`

- `parse_intent`：**纯确定性规则**——从结构化 slots 填槽 + 默认值 + 档位 clamp（45min~24h）。
- `message`（用户原始留言）字段存在，但**完全未被解析**：只原样存进 `Intent`，不做任何 LLM 抽取。
- 现状 = **零 LLM、零 agent**。

### 命题策划 `proposition.py`

- `decompose_intent`：**单次 LLM 调用**，输入 `intent + 证据摘要`，输出 `PropositionSet`（title/open_question/scope_note/propositions[]）。
- 红队已**内联在同一次调用**：模型自报 `verdict` / `rewritten_hypothesis`，另加启发式兜底 `_heuristic_over_extended`（零 LLM）。
- 关键注释：「原『第一道 LLM 审查』已合并进 decompose_intent 的同一次调用，**不再发起第二次 LLM 请求**」。

**重要事实**：命题策划已经从「多调用」**刻意收敛到「单调用 + 启发式兜底」**，目的就是省 token。

---

## 二、逐项判断

### 1. 意图理解 → 否决多 agent，采纳一个单次抽取

槽位填充是「确定性输入 → 结构化输出」的单一职责任务，一次调用即可，多 agent 纯属浪费 token。

**真实缺口**：`message` 自由文本没被利用。若要支持「一句话生成路线」，补一个**单次 LLM 槽位抽取**（`role="structured"`，hybrid 策略自动走本地），把自由文本映射到 slots，再进 `parse_intent`。**这是补一个函数，不是上 agent。**

### 2. 命题策划 → 否决「多 agent 编排」，采纳「propose/critique 分离」

**认知盲区（真实且具体）**：让同一个模型在同一次调用里「既生成命题又自我批判」，存在**自我辩护偏差**——生成者很难真正否定自己的命题。现状的「合并自评」是为了省 token 的刻意优化，但牺牲了批判独立性。

**正确形态是两阶段分离，不是多 agent 编排**：

1. **propose**（云端，创意）：生成 2–4 条命题假设。
2. **critique**（本地，结构化）：对每条命题独立判 `verdict`（allowed / over_extended）、给改写。
3. **启发式兜底**保留，作为 critique 不可用时的最后防线。

**成本可控的依据**：`llm.py` 的 hybrid 策略已让 `role="structured"` 优先走本地 ollama（`_resolve_backend_order` 返回 `["local","cloud"]`）。critique 输出极小（每命题一个 verdict），走本地几乎零云端成本。**基础设施已就绪，只差拆成两次调用。**

### 3. 数据层 MCP → 否决

- 数据访问（`rag.retrieve` / `fetch_evidence` / `gather_partner_evidence`）是**内部 Python 函数调用**，直接、同步、类型安全。
- MCP 是给「外部 agent 运行时」提供标准化工具接入的协议。RedTrip 不是 agent 运行时，是**内容生成服务**。
- 改成 MCP = 给一个不需要 agent 的系统强加 agent 协议，与前两轮砍掉的「编排层」「skill facade」是**同一种过度设计**。
- **数据源接入其实已经做了**：`providers.py` 的 28 家机构注册表 + `gather_partner_evidence`，就是「标准化数据源接入层」——只是它是 Python 函数，不是 MCP 协议。函数级已经满足需求。

**唯一例外**（另一个独立决策，不属于本议题）：若要把 RedTrip 的 28 家机构 + OSM + landmarks **对外暴露成 MCP server**（让 WorkBuddy 等外部 agent 检索），那是「RedTrip 作为数据提供方」的产品形态扩展，与本轮「策划阶段多 agent」无关。

### 4. skills → 否决（产品运行时）

与上一轮一致：skill 是 AI 助手开发期的协调工具，不进产品运行时架构。

---

## 三、唯一值得做的改动（轻量，非编排）

`proposition.py` 的 `decompose_intent` 从「单调用 + 自评」拆成「propose + critique」：

1. **propose**（现调用，去掉 verdict 自评字段）：只生成命题假设。
2. **critique**（新增函数，`role="structured"`，hybrid 走本地）：独立判定每条命题，给 verdict / rewritten。
3. **启发式兜底** `_heuristic_over_extended` 保留，作为 critique 不可用时的防线。

净变化：多一次结构化调用（走本地），换来批判独立性。**是两个函数，不是 agent 框架。**

---

## 四、否决清单（明确不做，避免过度设计）

- ❌ 多 agent 编排框架（planner / researcher / writer / critic 的 agent 图）
- ❌ 数据层 MCP 化
- ❌ 产品运行时 skill
- ❌ 意图理解的 agent 化（用单次抽取替代）

---

## 五、前置条件（待验证，不假设）

- **本地 ollama 是否可用**：`local_llm_configured()` 依赖 `LOCAL_LLM_BASE` + 端点可达。若不可用，critique 走云端——成本低（输出小）但仍需评估是否值得与「合并自评」相比。
- 验证后若本地可用 → propose/critique 分离直接落地；若不可用 → 维持现状单调用自评，不强行分离。

---

## 六、结论

策划阶段**不需要多 agent，也不需要 MCP**。唯一有价值的是一处轻量重构：命题策划的 propose/critique 分离（消除自我辩护偏差，批判走本地 hybrid 控成本）。其余（意图理解 agent 化、数据层 MCP、运行时 skill）全部否决。

省 token 的最终答案依然是那句话：**不是「更聪明的多 agent」，而是「只在确有收益处加一次结构化调用」。**
