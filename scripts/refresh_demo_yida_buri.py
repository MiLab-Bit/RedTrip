#!/usr/bin/env python3
"""把 buri-map / points.json 中的映射写回 demo-route-yida.json。

在服务器跑完 sync_buri_from_slc.py 后执行：
  python scripts/refresh_demo_yida_buri.py

同时清理错误串入的武康 buri（如巴金故居 URI 出现在一大站）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "content" / "fixtures" / "demo-route-yida.json"
POINTS = ROOT / "content" / "whitelist" / "points.json"
MAP = ROOT / "content" / "whitelist" / "buri-map.json"

WUKANG_URIS = {
    "http://data.library.sh.cn/entity/architecture/if3k5yb021u3c4vd",
    "http://data.library.sh.cn/entity/architecture/p8lpy1b17cgrkse4",
    "http://data.library.sh.cn/entity/architecture/amknmwvk01qaykng",
    "http://data.library.sh.cn/entity/architecture/sm4repfu8n3ga66j",
    "http://data.library.sh.cn/entity/architecture/b4kfg663vvxvczyu",
}

NAME_ALIASES = {
    "中共一大会址纪念馆周边": ["中共一大会址", "一大会址", "兴业路76号"],
    "前汇丰银行大楼": ["汇丰银行大楼", "外滩12号", "市府大楼"],
    "麦加利银行大楼": ["外滩18号", "麦加利", "渣打银行"],
    "中国银行大楼": ["中国银行大楼", "外滩中国银行"],
    "怡和洋行大楼": ["怡和洋行", "怡和洋行大楼"],
    "宋庆龄故居": ["宋庆龄故居"],
}


def _load_maps() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in (POINTS, MAP):
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        items = doc.get("points") or doc.get("mapped") or []
        for p in items:
            buri = p.get("buri")
            if not buri:
                continue
            if p.get("id"):
                out[str(p["id"])] = buri
            if p.get("name"):
                out[str(p["name"])] = buri
    return out


def _resolve(name: str, wid: str | None, maps: dict[str, str]) -> str | None:
    if wid and maps.get(wid):
        return maps[wid]
    if maps.get(name):
        return maps[name]
    for alias in NAME_ALIASES.get(name, []):
        if maps.get(alias):
            return maps[alias]
        for k, v in maps.items():
            if alias in k:
                return v
    return None


def _scrub_layers(layers: list) -> tuple[list, int]:
    cleaned = []
    dropped = 0
    for layer in layers or []:
        if not isinstance(layer, dict):
            continue
        src = layer.get("source") or {}
        rid = str(src.get("record_id") or "")
        if rid in WUKANG_URIS:
            dropped += 1
            continue
        cleaned.append(layer)
    return cleaned, dropped


def _scrub_tree(obj, dropped: list[int]):
    """Recursively remove / null out Wukang URIs that don't belong on yida entities."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if isinstance(v, str) and v in WUKANG_URIS:
                # Keep Song Qingling's own URI (not in WUKANG_URIS list as 4eqww…)
                obj[k] = None
                dropped[0] += 1
            else:
                _scrub_tree(v, dropped)
    elif isinstance(obj, list):
        for item in obj:
            _scrub_tree(item, dropped)


def main() -> int:
    if not DEMO.exists():
        print(f"missing {DEMO}", file=sys.stderr)
        return 1
    raw = json.loads(DEMO.read_text(encoding="utf-8"))
    maps = _load_maps()
    stops = (raw.get("route") or {}).get("stops") or []
    updated = 0
    scrubbed = 0

    for stop in stops:
        name = str(stop.get("name") or "")
        wid = stop.get("whitelist_id")
        layers, n = _scrub_layers(stop.get("layers") or [])
        stop["layers"] = layers
        scrubbed += n

        buri = _resolve(name, wid, maps)
        if not buri:
            continue
        if stop.get("buri") == buri and stop.get("evidence_channel") == "slc":
            # still upgrade building layer source if needed
            pass
        else:
            stop["buri"] = buri
            stop["evidence_channel"] = "slc"
            updated += 1
        for layer in stop["layers"]:
            if layer.get("kind") != "building":
                continue
            src = layer.setdefault("source", {})
            if src.get("dataset") in ("landmark_corpus", "geonames_corpus", "manual"):
                src["dataset"] = "slc_building"
                src["record_id"] = buri
                src["excerpt"] = f"上图建筑实体：{name}"

    # scrub polluted fact_uri elsewhere, but restore Song Qingling stop buri
    song = "http://data.library.sh.cn/entity/architecture/4eqww5yazhokuxt6"
    dropped = [0]
    _scrub_tree(raw, dropped)
    # restore known-good Song Qingling references on stop 2
    for stop in (raw.get("route") or {}).get("stops") or []:
        if "宋庆龄" in str(stop.get("name") or ""):
            stop["buri"] = song
            stop["evidence_channel"] = "slc"
            for layer in stop.get("layers") or []:
                src = layer.get("source") or {}
                if src.get("dataset") == "slc_building" or layer.get("kind") == "building":
                    src["dataset"] = "slc_building"
                    src["record_id"] = song
                    layer["source"] = src

    DEMO.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    stops = (raw.get("route") or {}).get("stops") or []
    buri_n = sum(1 for s in stops if s.get("buri"))
    slc_n = sum(1 for s in stops if s.get("evidence_channel") == "slc")
    print(
        f"refresh_demo_yida: stops_updated={updated} layers_scrubbed={scrubbed} "
        f"tree_scrubbed={dropped[0]} buri={buri_n}/6 slc={slc_n}/6"
    )
    print(f"wrote {DEMO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
