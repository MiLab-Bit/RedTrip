#!/usr/bin/env python3
"""多城市文化/历史/自然/艺术 POI 拉取（OSM Overpass，免 key）。

补足 amap 词库（<city>-landmarks.json，需 key）缺失的广度：把「该城市该有的
POI 都拉进来」作为 RAG 数据筛选层。输出 content/curated/<city>-osm.json。

用法（本机经代理，无需任何 key）:
    cd /opt/redtrip && .venv/Scripts/python.exe packages/tools/build_osm_pois.py --city shanghai
    # 拉取全部注册城市（后台运行，耗时较长）
    .venv/Scripts/python.exe packages/tools/build_osm_pois.py --all

设计：
- 区域过滤器取自 redtrip_curator.cities.CITY_REGISTRY（按名取边界，经镜像验证可用）。
- 归一化到 9 大类（与 <city>-landmarks.json 同套 category 体系），供 rag.py / evidence.py
  直接按 intent 做数据筛选。
- 坐标用 WGS-84（OSM 原生），与 amap(GCJ-02) 不在同一基准——rag 检索只做近邻/关键词
  匹配，渲染端仍以白名单 R-20 坐标为准（NG-10），故混用无碍。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# curator 包 __init__ 会拉起 pipeline → redtrip_library，需把 library-client 一并入路径，
# 否则 `from redtrip_curator.cities import ...` 会因 redtrip_library 不可见而失败。
sys.path.insert(0, os.path.join(ROOT, "packages", "curator"))
sys.path.insert(0, os.path.join(ROOT, "packages", "library-client"))
from redtrip_curator.cities import CITY_REGISTRY, get_city  # noqa: E402

CURATED = os.path.join(ROOT, "content", "curated")

ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]
PROXY = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7897"
PER_KEY_CAP = 4000          # 单 key Overpass 输出上限
GLOBAL_CAP = 8000           # 单城市语料上限（优先保留高价值类）
TIMEOUT = 120

# osm_key -> (正则值过滤 or None=全部, 优先级权重越大越先保留)
SPEC: list[tuple[str, list[str] | None, int]] = [
    ("tourism", ["museum", "gallery", "artwork", "attraction", "viewpoint",
                 "picnic_site", "theme_park", "zoo"], 100),
    ("historic", None, 95),
    ("amenity", ["museum", "theatre", "arts_centre", "library", "cinema",
                 "exhibition_centre", "place_of_worship", "fountain",
                 "social_centre", "events_venue", "showroom"], 90),
    ("leisure", ["park", "garden", "nature_reserve", "sculpture", "picnic_table",
                 "pitch", "marina", "water_park", "amusement_arcade",
                 "beach_resort", "bird_hide", "outdoor_seating", "dog_park",
                 "horse_riding", "mini_golf", "bowling_alley",
                 "recreation_ground", "summer_camp", "sports_centre",
                 "stadium", "escape_game"], 80),
    ("shop", ["books", "gift", "art", "mall", "department_store", "clothes",
              "jewellery", "antiques", "crafts", "music", "stationery",
              "lottery", "curtain", "fabric", "photography", "toys", "model"], 60),
    ("natural", ["water", "beach", "wetland", "bay", "cliff", "wood",
                 "tree_row", "scrub", "heath", "grassland", "fell", "peak",
                 "hill", "mountain", "island", "cape", "spring",
                 "cave_entrance", "sand", "shingle", "mud", "reef", "dune",
                 "strait", "peninsula", "saddle", "valley"], 70),
    ("craft", None, 50),
    ("man_made", ["tower", "lighthouse", "monument", "observatory", "cross",
                  "beacon", "artwork", "ship", "windmill", "watermill",
                  "stone", "cairn", "wayside_shrine", "wayside_cross"], 65),
    ("club", None, 40),
]

# osm_key:value -> 9 大类
_CLASS_MAP = {
    ("tourism", "museum"): "culture", ("tourism", "gallery"): "culture",
    ("tourism", "artwork"): "culture", ("tourism", "attraction"): "culture",
    ("tourism", "theme_park"): "suburb", ("tourism", "zoo"): "nature",
    ("tourism", "viewpoint"): "waterfront", ("tourism", "picnic_site"): "nature",
    ("historic", None): "historic",
    ("amenity", "museum"): "culture", ("amenity", "theatre"): "culture",
    ("amenity", "arts_centre"): "culture", ("amenity", "library"): "culture",
    ("amenity", "cinema"): "culture", ("amenity", "exhibition_centre"): "culture",
    ("amenity", "events_venue"): "culture", ("amenity", "showroom"): "culture",
    ("amenity", "social_centre"): "culture", ("amenity", "fountain"): "waterfront",
    ("amenity", "place_of_worship"): "religion",
    ("leisure", "park"): "nature", ("leisure", "garden"): "nature",
    ("leisure", "nature_reserve"): "nature", ("leisure", "dog_park"): "nature",
    ("leisure", "recreation_ground"): "nature", ("leisure", "summer_camp"): "nature",
    ("leisure", "horse_riding"): "nature", ("leisure", "picnic_table"): "nature",
    ("leisure", "pitch"): "nature", ("leisure", "sports_centre"): "nature",
    ("leisure", "stadium"): "nature", ("leisure", "bird_hide"): "nature",
    ("leisure", "marina"): "waterfront", ("leisure", "water_park"): "waterfront",
    ("leisure", "beach_resort"): "waterfront",
    ("leisure", "amusement_arcade"): "nightlife", ("leisure", "bowling_alley"): "nightlife",
    ("leisure", "escape_game"): "nightlife", ("leisure", "outdoor_seating"): "commercial",
    ("shop", None): "commercial",
    ("natural", None): "nature",
    ("craft", None): "commercial",
    ("man_made", "tower"): "waterfront", ("man_made", "lighthouse"): "waterfront",
    ("man_made", "observatory"): "waterfront", ("man_made", "beacon"): "waterfront",
    ("man_made", "monument"): "historic", ("man_made", "cross"): "historic",
    ("man_made", "wayside_shrine"): "historic", ("man_made", "wayside_cross"): "historic",
    ("man_made", "artwork"): "culture", ("man_made", "ship"): "waterfront",
    ("man_made", "windmill"): "historic", ("man_made", "watermill"): "historic",
    ("man_made", "stone"): "historic", ("man_made", "cairn"): "historic",
    ("club", None): "nightlife",
}


def _classify(key: str, val: str) -> str:
    return _CLASS_MAP.get((key, val)) or _CLASS_MAP.get((key, None)) or "commercial"


def _build_query(key: str, values: list[str] | None, area: str) -> str:
    if values:
        rx = "^(" + "|".join(values) + ")$"
        stmt = f'node[{key}~"{rx}"](area);way[{key}~"{rx}"](area);'
    else:
        stmt = f"node[{key}](area);way[{key}](area);"
    return (
        f"[out:json][timeout:{TIMEOUT}];"
        f"{area}"
        f"({stmt});out center {PER_KEY_CAP};"
    )


def _fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "RedTrip/1.0 (osm-pull)"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"  fetch err: {type(e).__name__}: {str(e)[:120]}\n")
        return None


def _query_once(key: str, values: list[str] | None, area: str) -> list[dict]:
    q = _build_query(key, values, area)
    last = None
    for ep in ENDPOINTS:
        url = f"{ep}?data={urllib.parse.quote(q)}"
        for attempt in range(3):
            raw = _fetch(url)
            if raw:
                try:
                    d = json.loads(raw)
                    return d.get("elements", []) or []
                except Exception:
                    last = "json-parse"
            time.sleep(1.5 * (attempt + 1))
    sys.stderr.write(f"  [{key}] all endpoints failed ({last})\n")
    return []


def _norm_name(n: str) -> str:
    return (n or "").strip().replace(" ", "").replace("　", "")


def _addr(tags: dict) -> str | None:
    street = tags.get("addr:street") or tags.get("addr:full")
    num = tags.get("addr:housenumber")
    city = tags.get("addr:city")
    parts = [p for p in (city, street, num) if p]
    if not parts:
        return None
    s = "".join(parts)
    return s[:80]


_KEEP_TAGS = (
    "name", "name:zh", "name:en", "historic", "tourism", "amenity", "leisure",
    "shop", "natural", "craft", "man_made", "club", "building", "architect",
    "start_date", "wheelchair", "website", "wikipedia", "description",
    "addr:city", "addr:district", "addr:street",
)


def _collect(city_key: str) -> list[dict]:
    spec = get_city(city_key)
    area = spec.area_query
    seen_cell: dict[str, str] = {}
    out: list[dict] = []
    for key, values, _w in sorted(SPEC, key=lambda x: -x[2]):
        els = _query_once(key, values, area)
        kept = 0
        for e in els:
            tags = e.get("tags", {})
            name = _norm_name(tags.get("name") or tags.get("name:zh"))
            if not name:
                continue
            if e["type"] == "node":
                lat, lng = e.get("lat"), e.get("lon")
            else:
                c = e.get("center") or {}
                lat, lng = c.get("lat"), c.get("lng")
            if lat is None or lng is None:
                continue
            cell = f"{lng:.3f},{lat:.3f}"
            if cell in seen_cell:
                continue
            seen_cell[cell] = name
            val = tags.get(key, "")
            out.append({
                "id": f"{e['type'][0]}{e['id']}",
                "name": name,
                "category": _classify(key, val),
                "osm_key": key,
                "osm_value": val,
                "address": _addr(tags),
                "lat": round(float(lat), 6),
                "lng": round(float(lng), 6),
                "tags": {k: tags[k] for k in _KEEP_TAGS if k in tags},
                "_w": _w,
            })
            kept += 1
        print(f"  [{key}] {len(els)} elements -> +{kept} kept (total {len(out)})", flush=True)
        if len(out) >= GLOBAL_CAP:
            out.sort(key=lambda d: -d["_w"])
            out[:] = out[:GLOBAL_CAP]
            break
    for d in out:
        d.pop("_w", None)
    return out


def pull_city(city_key: str) -> int:
    spec = get_city(city_key)
    out = CURATED + f"/{spec.key}-osm.json"
    os.makedirs(CURATED, exist_ok=True)
    print(f"OSM pull -> {out}\ncity={spec.name_zh} area={spec.area_query}\nproxy={PROXY}")
    pois = _collect(city_key)
    doc = {
        "version": 1,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": f"OpenStreetMap Overpass API ({spec.name_zh}) · keyless",
        "license": "ODbL (c) OpenStreetMap contributors",
        "coordinate_system": "WGS-84",
        "city": spec.key,
        "count": len(pois),
        "pois": pois,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    from collections import Counter
    cnt = Counter(p["category"] for p in pois)
    print(f"\nDONE: {len(pois)} pois for {spec.name_zh}")
    for c, n in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"  {c:<12} {n}")
    print(f"OUT: {out}")
    return len(pois)


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull OSM POIs per city (keyless).")
    ap.add_argument("--city", help="city key from CITY_REGISTRY (e.g. shanghai/beijing)")
    ap.add_argument("--all", action="store_true", help="pull every registered city")
    args = ap.parse_args()

    if args.all:
        keys = list(CITY_REGISTRY.keys())
    elif args.city:
        if args.city not in CITY_REGISTRY:
            print(f"unknown city '{args.city}'. available: {', '.join(CITY_REGISTRY)}")
            return 2
        keys = [args.city]
    else:
        keys = ["shanghai"]  # 默认兼容旧用法

    total = 0
    for i, k in enumerate(keys):
        try:
            total += pull_city(k)
        except Exception as e:  # noqa: BLE001
            print(f"!! {k} failed: {e}")
        # 公共 Overpass 实例会限流，城市间留白避免被整段封禁（首城无需等待）。
        if i < len(keys) - 1:
            time.sleep(8)
    print(f"\nALL DONE: {total} pois across {len(keys)} cities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
