#!/usr/bin/env python3
"""P0-2 修复：把全量 OSM 语料里的文化场馆 / 纪念馆回填进 R-20 白名单 points.json。

现状（来自 review 报告 P0-2）：points.json 30 条全是「梧桐区 + 一大周边」，
展览/博物馆类 0 条，导致门禁/规划器在文化类场景里完全无权威锚点。

本脚本把 shanghai-osm.json 中博物馆/美术馆/艺术中心/纪念馆/历史纪念碑等
（rag.exhibition_pois）抽出来，作为新增 whitelist 点并入 points.json：
- buri=None（诚实未映射 SLC，与既有约定一致）
- coord_source="osm" / precision="approximate"
- open_hours/enterable/need_reservation 一律「未收录」（避坑四字段禁止推测）
- district_tag 由坐标最近锚点粗推（黄浦/徐汇/浦东…）
- 幂等：重跑不会重复（按 name 去重），原 30 条保持不动

用法:
    cd /opt/redtrip && .venv/Scripts/python.exe packages/tools/build_exhibition_whitelist.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# 以包形式导入 redtrip_curator（rag.py 内部使用相对导入）。
# 同时注入 library-client，因为 redtrip_curator.__init__ 会拉起 pipeline -> redtrip_library。
sys.path.insert(0, os.path.join(ROOT, "packages", "curator"))
sys.path.insert(0, os.path.join(ROOT, "packages", "library-client"))

from redtrip_curator.rag import exhibition_pois  # noqa: E402

POINTS = Path(ROOT) / "content" / "whitelist" / "points.json"
CURATED = Path(ROOT) / "content" / "curated"
MAX_NEW = 150

# 坐标最近锚点 -> 粗略行政区（仅作 district_tag 粗标，非精确边界）
_ANCHORS = {
    "黄浦": (31.2304, 121.4737), "徐汇": (31.1886, 121.4371),
    "静安": (31.2290, 121.4489), "长宁": (31.2200, 121.4240),
    "杨浦": (31.2590, 121.5260), "虹口": (31.2650, 121.4900),
    "普陀": (31.2490, 121.4010), "浦东": (31.2210, 121.5890),
    "闵行": (31.1120, 121.3810), "宝山": (31.4040, 121.4890),
    "嘉定": (31.3750, 121.2650), "青浦": (31.1510, 121.1160),
    "松江": (31.0320, 121.2280), "奉贤": (30.9180, 121.4740),
    "金山": (30.7480, 121.3450), "崇明": (31.6220, 121.3980),
}


def _district(lat: float, lng: float) -> str:
    best, bd = "上海", 1e9
    for name, (la, ln) in _ANCHORS.items():
        d = (lat - la) ** 2 + (lng - ln) ** 2
        if d < bd:
            bd, best = d, name
    return best


def main() -> int:
    if not POINTS.exists():
        print("FATAL: points.json 不存在", POINTS)
        return 1
    doc = json.loads(POINTS.read_text(encoding="utf-8"))
    existing = doc.get("points", [])
    seen_names = {str(p.get("name", "")) for p in existing}
    next_n = len(existing) + 1

    cands = exhibition_pois(str(CURATED))
    # 去重 + 按名称稳定排序，挑前 MAX_NEW 条
    picked: list[dict] = []
    seen = set()
    for c in cands:
        name = c["name"]
        if name in seen_names or name in seen:
            continue
        seen.add(name)
        picked.append(c)
        if len(picked) >= MAX_NEW:
            break

    new_points: list[dict] = []
    for c in picked:
        lat, lng = float(c["lat"]), float(c["lng"])
        new_points.append({
            "id": f"wl-{next_n:03d}",
            "name": c["name"],
            "buri": None,
            "lat": lat,
            "lng": lng,
            "coord_source": "osm" if c.get("source") == "osm" else "amap",
            "precision": "approximate",
            "open_hours": "未收录",
            "enterable": "未收录",
            "need_reservation": "未收录",
            "photo_spot": None,
            "district_tag": _district(lat, lng),
            "verified_at": "2026-08-25",
            "evidence_channel": "osm" if c.get("source") == "osm" else "landmark",
            "field_sources": {
                "lat": "OSM Overpass (WGS-84)" if c.get("source") == "osm" else "amap",
                "lng": "OSM Overpass (WGS-84)" if c.get("source") == "osm" else "amap",
                "buri": "未映射",
                "open_hours": "未收录（多缺开放时间）",
            },
        })
        next_n += 1

    merged = existing + new_points
    doc["points"] = merged
    doc["count"] = len(merged)
    doc["scope"] = "梧桐区 + 一大周边 + 上海全量文化场馆/纪念馆(OSM)"
    notes = doc.get("notes", [])
    notes.append("2026-08-14: P0-2 修复，并入 OSM 全量文化场馆/纪念馆（buri 诚实留空）")
    doc["notes"] = notes
    doc["generated_at"] = "2026-08-14"

    POINTS.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE: points.json {len(existing)} -> {len(merged)} "
          f"(+{len(new_points)} from OSM)")
    from collections import Counter
    cnt = Counter(p.get("district_tag") for p in new_points)
    for d, n in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"  {d:<6} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
