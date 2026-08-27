#!/usr/bin/env python3
"""Rebuild Wikidata POI corpus with dedup and noise filtering.

Reads raw JSONL (default packages/curator/redtrip_curator/poi_corpus/cleaned.jsonl),
writes filtered JSONL + summary stats.

Usage:
  python scripts/build_wikidata_corpus.py
  python scripts/build_wikidata_corpus.py --input path/to/raw.jsonl --output path/to/out.jsonl
  python scripts/build_wikidata_corpus.py --city shanghai --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "packages" / "curator" / "redtrip_curator" / "poi_corpus" / "cleaned.jsonl"
DEFAULT_OUT = ROOT / "packages" / "curator" / "redtrip_curator" / "poi_corpus" / "cleaned.filtered.jsonl"

# Shanghai bounding box (WGS-84) — expand slightly for fringe POIs
SHANGHAI_BBOX = (30.68, 121.10, 31.90, 122.05)

NOISE_NAME = re.compile(
    r"(地铁|轨道交通|站$|Hospital|Institute|University|大厦$|大楼$|"
    r"^Q\d+$|Hangdao|Gang$| accident|事故|通道$|River$|河道$)",
    re.I,
)

KEEP_CATEGORIES = {
    "文化遺產",
    "博物館",
    "孔庙",
    "住宅",
    "attraction",
    "city_park",
    "公園",
    "城市公園",
    "森林公园",
    "纪念",
    "文保",
}


def _in_bbox(lat: float, lng: float, bbox: tuple[float, float, float, float]) -> bool:
    min_lat, min_lng, max_lat, max_lng = bbox
    return min_lat <= lat <= max_lat and min_lng <= lng <= max_lng


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").strip().lower())


def _is_noise(row: dict) -> str | None:
    name = str(row.get("name") or "")
    if not name or len(name) < 2:
        return "empty_name"
    if NOISE_NAME.search(name):
        return "noise_pattern"
    desc = str(row.get("desc") or "")
    cats = row.get("category") or []
    cat_str = " ".join(str(c) for c in cats)
    if any(k in cat_str or k in desc for k in KEEP_CATEGORIES):
        return None
    if "文保" in cat_str:
        return None
    # Generic infrastructure without heritage signal
    if any(k in cat_str for k in ("地下站", "道路", "水道", "河流", "設施", "醫院", "摩天大樓")):
        return "infra_category"
    return None


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deduped Wikidata POI corpus")
    parser.add_argument("--input", type=Path, default=DEFAULT_IN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--city", default="shanghai", help="filter bbox: shanghai|none")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = _load_jsonl(args.input)
    if not rows:
        print(f"ERROR: no rows in {args.input}", file=sys.stderr)
        return 1

    stats = Counter()
    seen_name: set[str] = set()
    seen_id: set[str] = set()
    kept: list[dict] = []

    for row in rows:
        stats["total"] += 1
        qid = str(row.get("id") or "")
        if qid in seen_id:
            stats["dup_id"] += 1
            continue

        lat = row.get("lat")
        lng = row.get("lng")
        if args.city == "shanghai" and isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            if not _in_bbox(float(lat), float(lng), SHANGHAI_BBOX):
                stats["out_of_bbox"] += 1
                continue

        reason = _is_noise(row)
        if reason:
            stats[f"drop_{reason}"] += 1
            continue

        nkey = _norm_name(str(row.get("name") or ""))
        if nkey in seen_name:
            stats["dup_name"] += 1
            continue

        seen_id.add(qid)
        seen_name.add(nkey)
        kept.append(row)
        stats["kept"] += 1

    print(
        f"build_wikidata_corpus: in={stats['total']} kept={stats['kept']} "
        f"dup_id={stats['dup_id']} dup_name={stats['dup_name']} "
        f"out_of_bbox={stats.get('out_of_bbox', 0)}"
    )
    for k, v in sorted(stats.items()):
        if k.startswith("drop_"):
            print(f"  {k}={v}")

    if args.dry_run:
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {args.output} ({len(kept)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
