# GitHub 分支清单（2026-08-27 脱敏快照后）

## 正式源

| 引用 | 说明 | 建议 |
|---|---|---|
| `cursor/release-sy-realm-f285` | 服务器 `/opt/redtrip` 脱敏快照（`d24c7e2`） | **保留，作为线上对齐源** |
| tag `snapshot/sy-realm-20260827` | 同上 tip 的归档标签 | **保留，勿删** |

## 现有分支处置

| 分支 | 与 release 关系 | 建议 | 条件 |
|---|---|---|---|
| `cursor/server-mobile-demo-f285` | Agent 实验线；历史 tip 已被线上工作树覆盖大半 | **可归档后删除** | 先确认无独有未合并提交要保留；建议先打 tag `archive/server-mobile-demo-f285` |
| `main` | 主要多出产品 deck（pptx/pdf/HTML）等文档提交 | **暂保留**；或把 deck 并入 release 后再重置 `main` 指向 release | 删除前必须先合并/搬迁 `Doc/deck` |
| `feat/dianji-reborn` | GitHub tip 比服务器基线新（含 enrich 去重、CBDB、小程序 0.1.3 等） | **暂勿删** | 与 `cursor/release-sy-realm-f285` 做一次内容 diff；确认独有修复已在线上或可放弃后再归档删除 |

## 不建议

- **不要**三个旧分支一起删完只留空仓
- **不要** force-push 覆盖 `feat/dianji-reborn` / `main` 除非已做 tag 备份
- **不要**把服务器 `.env` / cloudflared 凭证推进任何分支

## 推荐后续顺序

1. 日常开发以 `cursor/release-sy-realm-f285` 为基（或将其合并进 `main` 后只维护 `main`）
2. `git fetch && git diff cursor/release-sy-realm-f285...feat/dianji-reborn --stat` 审计 dianji 独有改动
3. 确认后：`feat/dianji-reborn` → tag `archive/dianji-reborn` → 删分支
4. `cursor/server-mobile-demo-f285` → tag → 删分支
5. 可选：把 `main` 快进到 release（先备份 deck）

## 2026-08-27 更新

- 已将 `Doc/deck/**` 从 `archive/main-pre-release` 并入本分支。
- `main` 已与本分支对齐后删除（见本次提交之后的操作）；演示稿以本分支 + 归档标签为准。
- `feat/dianji-reborn` 仍暂保留，待独有修复合并后再删。
