# ADR-004 · HTTP 直调优先于 MCP 子进程

- 状态：已采纳  
- 日期：2026-08-06  

## 背景

桌面已有完整 `slc_mcp_server.py`（12 tools / 97 endpoints）。产品需要稳定取证、缓存、快照与白名单过滤。

## 决策

1. **默认**：`library-client` 按 MCP 同款协议 **HTTP 直调** `data1.library.sh.cn`。  
2. **MCP stdio** 仅用于 Spike / 与 IDE 联调。  
3. **演示默认**可切 `snapshot`，不阻塞答辩。  
4. Key 仅存 API 进程环境变量，永不进 Web、永不进仓库。

## 后果

- 正向：可单测、可缓存、代理问题一次修好  
- 负向：需维护一份与 MCP 对齐的 endpoint 表（可复制 `slc_endpoints.py`）  
- 对齐成本：上游 MCP 变更时对照 diff
