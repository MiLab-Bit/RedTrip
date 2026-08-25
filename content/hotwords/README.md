# 第三层 · 上海周热词（小红书信号）

> 三层 Agentic RAG 的 **L3**。L1 取证、L2 红鸢词库规则不变。

## 规则

1. **只影响当代读法口吻**（街拍语感、街区氛围词），不得写入史实、开放时间、坐标、人名年份。
2. **景点优先**：`places` 尽量挂具体路名/场馆；城市通用词 `heat` 压低作兜底。
3. **每周二更新**：覆盖 `latest.json`，并归档到 `archive/YYYY-Www.json`。

## 更新方式

```bash
# 1) Agent/人工把本周采集结果放进 inbox
#    content/hotwords/inbox/week.json

# 2) 合并校验并发布
python scripts/update_hotwords.py
# 或指定文件：
python scripts/update_hotwords.py --inbox content/hotwords/inbox/week.json
```

采集提示词见 `packages/curator/prompts/collect_hotwords_weekly.txt`。

## 字段

| 字段 | 说明 |
|------|------|
| `week` | ISO 周，如 `2026-W32` |
| `term` | 热词/短短语 |
| `places` | 关联景点/路名 |
| `hint` | 给润色模型的约束 |
| `heat` | 0–1，检索排序 |
| `tone_tags` | 可选：文艺 / 轻社交 / 硬核 |
