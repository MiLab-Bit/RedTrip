# 09 · 代码目录规划

> ✅ Doc + README + `.env.example` 已建  
> 下列为脚手架目标树

---

## 1. 目标树

```
RedTrip/
├── README.md
├── .env.example                 ✅
├── .gitignore                   ✅
├── Doc/                         ✅ 工程文档
├── apps/
│   ├── web/                     # Vite React R3F
│   └── api/                     # FastAPI
├── packages/
│   ├── contracts/               # Zod / JSON Schema
│   ├── curator/                 # 六阶段流水线 + prompts
│   ├── library-client/          # SLC HTTP + 可选 MCP
│   │   └── endpoints.py         # 自 slc_endpoints 对齐复制
│   └── gate/
├── content/
│   ├── whitelist/points.json
│   ├── fixtures/
│   └── index.sqlite             # gitignored 或 LFS
├── scripts/
│   ├── s0_spike.py
│   ├── build_index.py
│   └── smoke_curate.py
├── pnpm-workspace.yaml
└── pyproject.toml               # 可选：api+curator workspace
```

---

## 2. 外部参考（不入库）

| 路径 | 用途 |
|---|---|
| `<local-path>/frontend-radar/` | 前端库源码研读 |
| `<local-path>/shanghai-library-mcp/` | MCP/endpoints 参考 |
| `../产品设计\` | PRD / Prompt / 红队 |

---

## 3. 依赖方向

```
web → contracts
api → curator → library-client
api → gate
curator → gate
curator → content（只读）
web ↛ library-client
web ↛ SLC_API_KEY
```

---

## 4. 文档索引增量

新增：

- [11-mcp-integration.md](./11-mcp-integration.md)  
- [12-frontend-architecture.md](./12-frontend-architecture.md)  
- [adr/004-http-first-mcp.md](./adr/004-http-first-mcp.md)  
