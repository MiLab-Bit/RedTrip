# GitHub 分支现状（2026-08-27）

## 当前分支

| 分支 | 角色 | 状态 |
|---|---|---|
| **`main`**（默认） | 服务器 `/opt/redtrip` 脱敏快照 + `Doc/deck` | **正式源，保留** |
| `feat/dianji-reborn` | 旧开发线；含尚未并入 main 的修复（enrich 去重、CBDB、小程序 preview 等） | **暂保留，勿删** |

## 已删除

| 原分支 | 归档标签 | 说明 |
|---|---|---|
| `cursor/server-mobile-demo-f285` | `archive/server-mobile-demo-f285` | 已删 |
| `cursor/release-sy-realm-f285` | tip 已重建为 `main`；快照见 `snapshot/sy-realm-20260827` | 已改名为 `main` 后删除旧名 |
| 旧 `main`（deck 专用 tip） | `archive/main-pre-release` | 已删；deck 已并入现 `main` |

## 日常约定

1. 新改动基于 **`main`**
2. 服务器跟踪 **`origin/main`**
3. 密钥只在服务器 `.env` / cloudflared，不入库
4. `feat/dianji-reborn` 独有修复合并进 `main` 后，再删该分支（标签 `archive/dianji-reborn` 已存在）
