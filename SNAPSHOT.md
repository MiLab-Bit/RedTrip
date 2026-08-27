# sy-realm 服务器脱敏快照

- 来源：`/opt/redtrip` on SWAS `139.224.163.203`
- 时间：见本提交
- 基线 commit：`93b2faa`（`feat/dianji-reborn` 本地 tip）+ 当时全部未提交运维/功能改动
- 已排除：`.env*`（保留 `.env.example`）、`.cloudflared/`、`backups/`、`.venv/`、`node_modules/`、密钥与 token 文件

## 用途

这是线上机器工作树的**脱敏归档分支**，用于对齐 GitHub 与服务器真实运行代码。  
运行仍以服务器为准；密钥只在服务器 `.env`，不入库。

## 正确访问

- Web：https://sy-realm.ltd/redtrip/
- Health：https://sy-realm.ltd/redtrip/v1/health
