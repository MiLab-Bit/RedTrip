# 11 · 上海图书馆 MCP / HTTP 集成

> 参考仓库：`<local-path>/shanghai-library-mcp/`  
> 权威实现文件：`slc_mcp_server.py` + `slc_endpoints.py`（97 endpoints）

---

## 1. 集成策略（ADR-004）

| 优先级 | 方式 | 说明 |
|---|---|---|
| 1 | **HTTP 直调**（library-client） | 与 MCP 内 `slc_call` 等价；易测、易缓存、易 NO_PROXY |
| 2 | **本地索引 / 快照** | 演示与时延；不依赖现场上游 |
| 3 | MCP stdio 子进程 | 仅 Spike / 与 Cursor 联调；非默认生产路径 |

RedTrip **不**在浏览器调 MCP；只在 API 进程持有 Key。

---

## 2. Key 管理

```
优先级：工具/函数参数 key  >  环境变量 SLC_API_KEY
```

- 本地：`RedTrip/.env`（gitignored）  
- 模板：`RedTrip/.env.example`（占位，无真实值）  
- 切勿把 Key 写入 Doc、代码、README、聊天记录存档  

MCP 模板（调试用，路径按本机修改）：

```json
{
  "mcpServers": {
    "上海图书馆开放数据": {
      "command": "python",
      "args": [
        "<slc_mcp_server.py 绝对路径>"
      ],
      "env": {
        "SLC_API_KEY": "从 .env 读取，勿粘贴到仓库"
      }
    }
  }
}
```

---

## 3. library-client 目标 API

```python
class SlcClient:
    def __init__(self, key: str, mode: Literal["snapshot","indexed","mcp"])

    def call(self, endpoint_id: str, params: dict) -> dict
    def building_list(self, freetext: str = "") -> dict
    def building_detail(self, uri: str) -> dict
    def event_list(self, buri: str) -> dict          # ASCII 主路径
    def red_event_list(self, *, keyword: str = "", date: str = "") -> dict
    def red_event_detail(self, uri: str) -> dict
    def era(self, term: str) -> dict
    def poem(self, keyword: str, **kw) -> dict        # 免 Key

    def health(self) -> dict  # endpoints ping + index version
```

实现要点（对齐上游 MCP）：

- Base：`https://data1.library.sh.cn`  
- `needs_key` 的 endpoint：query 附加 `key`  
- POST：body JSON，key 仍在 query  
- Timeout：25s  
- User-Agent / Accept 与上游一致  
- Windows：`PYTHONUTF8=1`；进程级 `NO_PROXY`

---

## 4. 策展最小调用集（P0）

```
1. （离线）build_index / 或读 fixtures
2. whitelist ∩ FTS(name) → buri?
3. if buri: building_detail(uri) + event_list(buri)
4. route_getEventList（主题相关，ASCII/已编码安全参数）
5. 可选：era(年份) / poem（氛围，非事实）
6. 组装 EvidencePack → Curator
```

---

## 5. S0 Spike 脚本约定

`scripts/s0_spike.py` 应对齐技术可行性裁定五步：

| 步 | 动作 |
|---|---|
| S0-1 | NO_PROXY 后 `building_detail` 或 list ASCII |
| S0-2 | 中文 freetext 归因 |
| S0-3 | 10 条 detail 打印全字段（经纬度？） |
| S0-4 | 3 热门 + 3 长尾 `event_list` 非空率与层数 |
| S0-5 | 分页探底 |

输出：`Doc/reports/s0-YYYYMMDD.md`（可后补目录）。

---

## 6. 与 vendor MCP 的关系

| 项 | 策略 |
|---|---|
| 代码复用 | **逻辑对齐**，不 submodule 整仓进产品（避免把测试 Key/日志带入） |
| endpoints 表 | 可复制 `slc_endpoints.py` 到 `packages/library-client/endpoints.py` 并注明来源 |
| 行为差异 | RedTrip 增加：缓存、白名单过滤、snapshot fallback、结构化 EvidencePack |
| 许可证 | 使用前核对 ShangHaiKaiFang LICENSE |

路径引用（开发机）：

```
SLC_MCP_SERVER=<local-path>/shanghai-library-mcp/slc_mcp_server.py
```

---

## 7. 失败降级

```
上游超时/TLS → 读 snapshot → 仍不足 → gaps + 降级声明
Gate 前必须可解释「哪些点无馆藏支撑」
```

演示模式 `REDTRIP_MODE=snapshot` 时，禁止静默假装在线取证；`envelope.meta.mode` 必须暴露。
