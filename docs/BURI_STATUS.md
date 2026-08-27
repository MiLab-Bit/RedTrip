# 外滩 / 一大 buri 补录状态

更新：2026-08-27

## 结论

`sync_buri_from_slc.py` 已在服务器用 SLC API 实测。以下演示线关键点 **在上图 architecture 检索中无记录**，无法诚实补 buri：

| whitelist | 名称 | SLC building_list |
|-----------|------|-------------------|
| wl-001 | 中共一大会址纪念馆周边 | 空 |
| wl-036 | 前汇丰银行大楼 | 空 |
| wl-034 | 麦加利银行大楼 | 空 |
| wl-031 | 中国银行大楼 | 空 |
| wl-032 | 怡和洋行大楼 | 空 |

已确认可映射：

| whitelist | 名称 | buri |
|-----------|------|------|
| wl-111 | 宋庆龄故居 | `http://data.library.sh.cn/entity/architecture/4eqww5yazhokuxt6` |

## 当前产品策略

- 有 URI → `evidence_channel=slc`，正文可写「上图建筑实体」
- 无 URI → `landmark` / `manual` / `osm`，前端标「策展词库」「地名志」，不伪装馆藏

## 后续补录流程

1. 上图开放数据补录或获得批量 architecture 索引
2. `python scripts/sync_buri_from_slc.py --district ALL`
3. `python scripts/refresh_demo_yida_buri.py`
4. `PYTHONPATH=packages/curator:packages/gate python3 scripts/enrich_demo_narratives.py`

手工 URI（需可核查后写入 `content/whitelist/buri-map.json`）：

```json
{ "id": "wl-036", "name": "前汇丰银行大楼", "buri": "http://data.library.sh.cn/entity/architecture/..." }
```
