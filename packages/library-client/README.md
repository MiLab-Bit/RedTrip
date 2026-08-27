# redtrip_library (library-client)

Shanghai Library HTTP client for RedTrip. Logic aligned with  
`上海图书馆开放数据MCP/slc_mcp_server.py` (HTTP-first, not MCP stdio).

## Usage

```python
from redtrip_library import SlcClient

client = SlcClient()  # reads SLC_API_KEY
probe = client.health_probe()
detail = client.building_detail(uri)
events = client.event_list(buri=uri)
```

## Env

- `SLC_API_KEY` — contest key
- Proxy bypass is **on by default** (`ProxyHandler({})`) because local Clash often breaks `*.library.sh.cn` TLS
- Also sets `NO_PROXY` for library / sou-yun hosts

## Smoke

```bat
RedTrip\.venv\Scripts\python.exe scripts\s0_spike.py
```
