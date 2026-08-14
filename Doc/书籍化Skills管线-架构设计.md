# 红鸢「书籍化」架构设计（终版：纯软件，零 agent / 零 skill）

> 结论演进：初版「四层流水线」→ 二版「可信度轴 × 形态轴」→ 本版「渲染器模式」。
> 最终认识：**书籍化是「确定性数据转换 + 渲染」，不需要 agent，不需要 skill，不需要编排层。**

---

## 0. 一句话结论

书籍化 = 内容管线（已有）产出的「溯源叙事」envelope，**多一个渲染后端 `render_book()`**，外加一个普通 HTTP endpoint / CLI 入口。

新增物只有三样：**一个纯函数、一个 endpoint、可选的前言生成步骤**。零 agent、零 skill、零编排。

---

## 0.5 为什么一路砍到零 agent（反思）

- **初版「四层」**：错在把「内容生产」与「呈现」两个正交关切串成流水线。
- **二版「skill 编排 + 多 agent」**：错在把 **WorkBuddy 的运行时机制（skill / agent）当成 RedTrip 产品的架构层**。WorkBuddy 本身就是一个 agent，在它内部再「内置编排层 + 多 agent 系统」是套娃——而且书籍化是个确定性机械转换，根本不需要 agent 的自主性。
- **本质**：书籍化 = 把结构化 JSON 变成另一种结构化呈现。这是纯函数 + 模板渲染的活儿，属于 MVC 的「View 层」，跟 agent / skill / 编排一点关系没有。

---

## 1. 为什么不能用现成 skills（判断依据）

1. **溯源会被摧毁**：book-writer 类 skill 假设「从零写一本 generic 书」，输出自由散文，没有 `fact_uri`、没有句子级溯源、没有 Gate → 退回「幻觉散文 = 电子垃圾」。
2. **token 会爆炸**：11-agent 互相传全文，一本书 token 是现有管线的 5–10 倍。
3. **无领域能力**：无中文 city-walk 人文/建筑/风景语料，无 OSM / landmark / partner 数据源。

---

## 2. 现状盘点：书骨架已存在（读代码确认）

| 书籍化需要的原语 | RedTrip 已有模块 | 状态 |
|---|---|---|
| 全书主题 / 主线 | `artifacts.Theme` / `logic_line` | 已有 |
| 章节结构 | `artifacts.StoryChapter`（title/hook/evidenceIds/castRefs） | 已有 |
| 叙事弧 | `artifacts.NarrativeArc` | 已有 |
| 证据图 | `artifacts.EvidenceGraph` | 已有 |
| 逐句溯源 | `sentence_provenance.py` | 已有 |
| 章节级润色 | `polish.py`（B4） | 已有 |
| 套话拦截 | `redtrip_gate.FORBIDDEN_COPY` | 已有 |
| 风格抽签 | `hongyuan.VoicePack` | 已有 |
| 混合路由 | `llm.py`（cloud/hybrid/local） | 已有 |
| **书形态渲染 `render_book()`** | — | **缺失** |
| **书籍专属文本（序/引子/桥）** | — | **缺失** |
| **`/v1/book` 入口 + CLI** | — | **缺失** |

**结论：缺一个渲染函数、一个前言步骤、一个入口，不缺「写作」。**

---

## 3. 目标架构（渲染器模式）

```
入口：/v1/book · python -m redtrip_curator.book（普通 API/CLI）

内容管线（已有 · 唯一真身 · 证据先于叙事）
  intent → evidence → plan → narrative → polish → gate
  产出 envelope「溯源叙事」= StoryChapter[] + EvidenceGraph + ProvenanceReport
        ├── render_web()    → 路线页（已有）
        ├── render_book()   → 书（新增 · 纯函数）
        └── render_…()      → 未来形态（PPT / 展板…）

序/引子/桥 = envelope 里的额外章节，走同一 narrative→polish→gate（可选）
```

新增物（都不是「层」）：

1. **`render_book(envelope) -> BookDocument`**：纯函数，放在 `packages/curator/redtrip_curator/book.py`。消费「溯源叙事」契约，产出目录 / 脚注 / colophon / 分页 / HTML。**100% 确定性、零 token、无副作用**。
2. **入口**：`GET/POST /v1/book`（复用 `/v1/curate` 的参数，返回书 HTML 或 EPUB）+ `python -m redtrip_curator.book` CLI。普通 endpoint，非 skill。
3. **`compose_frontmatter()`（可选）**：生成序 / 每章引子 / 章节桥。它是**内容管线的可选生成步骤**——把这些当作额外章节，走同一套 `narrative → polish → gate`，不另起炉灶。

---

## 4. token 策略

| 部分 | token 属性 |
|---|---|
| 内容管线 · 证据/规划段 | 零（确定性） |
| 内容管线 · 叙事段 | 受控（「1 元数据 + N 单卡」+ hybrid 本地分流） |
| `render_book()` | 零（纯模板渲染） |
| `compose_frontmatter()` | 受控（序/引子/桥走 LLM + Gate） |
| 入口 | 零 |

**红线不变：绝不叠加「全书 LLM 重写」。**

---

## 5. 「多 agent」该在哪（关键定调）

- **RedTrip 的内容生产是「证据约束的确定性生成」，不需要 agent 的自主性**——agent 自由发挥 = 幻觉，破坏溯源。
- **书籍化是确定性转换，更不需要 agent。**
- 如果将来真要多 agent，它在**策划阶段**（意图理解 / 命题策划 / 用户研究），是内容管线之前的输入准备，不是内容生成之后的装订。
- **skill / agent 是我（AI 助手）开发期协调用的工具，不进入产品运行时架构**——产品能力用纯代码（函数 + 管线 + 渲染器）实现。

---

## 6. 重构建议（提升现有代码，可选）

1. `llm.py` 的 `max_tokens = max_tokens` no-op 赋值 → 删掉，意图收敛到 docstring。
2. `polish.py` 的 `_ = facts` → 改为 `del facts` 或直接不取。
3. `build_osm_pois.py --all` 无「跳过已有新鲜文件」→ 加 `--skip-existing`（默认 mtime < 24h 跳过）。
4. OSM 进度不可见（`| tail` 管道缓冲）→ 写 `content/curated/_pull.log` 而非 stdout。
5. `cities.py` 与 `providers.py` 城市归属未交叉校验 → `health_probe` 加完整性检查。

---

## 7. 实施路线（分期）

- **P0（冻结契约）**：把「溯源叙事」的 schema（`StoryChapter` + `EvidenceGraph` + `ProvenanceReport`）在 `artifacts.py` 里冻结为稳定契约，补 docstring。出版引擎只依赖它。
- **P1（渲染函数）**：`book.py` 的 `render_book(envelope)` —— 目录 / 脚注 / colophon / 打印友好 HTML。
- **P2（入口）**：`/v1/book` endpoint + `python -m redtrip_curator.book` CLI。
- **P3（前言）**：`compose_frontmatter()` 序/引子/桥，受控 LLM + Gate。
- **P4（导出 + 清理）**：EPUB / PDF / MDX 多格式；落地第 6 节 5 项重构。
