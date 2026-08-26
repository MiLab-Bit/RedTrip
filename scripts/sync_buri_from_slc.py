#!/usr/bin/env python3
"""Batch-map SLC architecture buri for 一大周边 / 外滩 whitelist points.

Requires SLC_API_KEY in environment or .env at repo root.

Usage:
  python scripts/sync_buri_from_slc.py
  python scripts/sync_buri_from_slc.py --dry-run
  python scripts/sync_buri_from_slc.py --district 一大周边
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "library-client"))
os.environ.setdefault("PYTHONUTF8", "1")

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from redtrip_library import SlcClient  # noqa: E402

TODAY = date.today().isoformat()
POINTS_PATH = ROOT / "content" / "whitelist" / "points.json"
MAP_PATH = ROOT / "content" / "whitelist" / "buri-map.json"

# whitelist id -> SLC freetext query (ordered by match priority)
YIDA_QUERIES: dict[str, list[str]] = {
    "wl-001": ["中共一大会址", "一大会址纪念馆", "兴业路76号"],
    "wl-002": ["兴业路", "石库门"],
    "wl-003": ["黄陂南路", "太仓路"],
    "wl-004": ["淮海中路"],
    "wl-005": ["思南公馆", "思南路"],
    "wl-006": ["香山路", "兴业路"],
}

BUND_QUERIES: dict[str, list[str]] = {
    "wl-bund-hsbc": ["汇丰银行大楼", "外滩12号", "市府大楼"],
    "wl-bund-18": ["麦加利银行大楼", "外滩18号", "渣打银行"],
    "wl-bund-boc": ["中国银行大楼", "外滩中国银行"],
    "wl-bund-jardine": ["怡和洋行", "怡和洋行大楼"],
    "wl-bund-soong": ["宋庆龄故居", "淮海中路1843"],
}


def _as_list(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "list", "buildings", "items"):
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            for k2 in ("list", "items", "data", "result"):
                if isinstance(val.get(k2), list):
                    return [x for x in val[k2] if isinstance(x, dict)]
    return []


def _uri_of(item: dict) -> str | None:
    for k in ("uri", "buri", "id", "buildingUri", "building_uri"):
        v = item.get(k)
        if isinstance(v, str) and "architecture" in v:
            return v
    return None


def _name_of(item: dict) -> str:
    for k in ("name", "title", "buildingName", "label"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _search_buri(client: SlcClient, queries: list[str], seen: set[str]) -> tuple[str | None, str | None]:
    for q in queries:
        resp = client.building_list(q)
        if not resp.ok:
            continue
        for item in _as_list(resp.data):
            uri = _uri_of(item)
            if not uri or uri in seen:
                continue
            name = _name_of(item)
            return uri, name or q
    return None, None


def _rebuild_buri_map(points: list[dict]) -> dict:
    return {
        "version": "1.0",
        "mapped": [
            {"id": p["id"], "name": p["name"], "buri": p["buri"]}
            for p in points
            if p.get("buri")
        ],
        "unmapped": [
            {"id": p["id"], "name": p["name"], "reason": "暂无数据支撑"}
            for p in points
            if not p.get("buri")
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync SLC buri into whitelist points")
    parser.add_argument("--dry-run", action="store_true", help="print matches without writing")
    parser.add_argument(
        "--district",
        default="一大周边",
        help="only update points with this district_tag; use ALL for every point with a query",
    )
    args = parser.parse_args()

    key = os.getenv("SLC_API_KEY", "").strip()
    if not key:
        print("SKIP: SLC_API_KEY not set — run on server with .env or export key")
        return 0

    if not POINTS_PATH.exists():
        print(f"ERROR: missing {POINTS_PATH}", file=sys.stderr)
        return 1

    doc = json.loads(POINTS_PATH.read_text(encoding="utf-8"))
    points: list[dict] = doc.get("points") or []
    client = SlcClient()
    seen = {p["buri"] for p in points if p.get("buri")}
    updated = 0
    log: list[str] = []

    query_map = {**YIDA_QUERIES, **BUND_QUERIES}
    district_filter = None if args.district in ("", "ALL", "*") else args.district

    for p in points:
        if district_filter and p.get("district_tag") != district_filter:
            if p["id"] not in query_map:
                continue
        queries = query_map.get(p["id"])
        if not queries:
            # fallback: search by point name minus suffix
            name = str(p.get("name") or "")
            if "周边" in name or "示意" in name or "意象" in name:
                base = name.split("周边")[0].split("（")[0].strip()
                queries = [base] if base else None
            else:
                queries = [name] if name else None
        if not queries:
            continue
        if p.get("buri"):
            continue

        buri, match_name = _search_buri(client, queries, seen)
        if not buri:
            log.append(f"  miss {p['id']} {p.get('name')}")
            continue
        log.append(f"  hit  {p['id']} {p.get('name')} -> {match_name} ({buri})")
        if not args.dry_run:
            p["buri"] = buri
            p["verified_at"] = TODAY
            fs = p.setdefault("field_sources", {})
            fs["buri"] = "SLC architecture uri"
            p["evidence_channel"] = "slc"
            if match_name and match_name != p.get("name"):
                p["name"] = match_name
        seen.add(buri)
        updated += 1

    print(f"sync_buri: district={args.district} updated={updated} dry_run={args.dry_run}")
    for line in log:
        print(line)

    if args.dry_run or updated == 0:
        return 0

    doc["generated_at"] = TODAY
    doc.setdefault("notes", [])
    note = f"{TODAY} sync_buri_from_slc: +{updated} buri ({args.district})"
    if note not in doc["notes"]:
        doc["notes"].append(note)

    with POINTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    buri_map = _rebuild_buri_map(points)
    with MAP_PATH.open("w", encoding="utf-8") as f:
        json.dump(buri_map, f, ensure_ascii=False, indent=2)
        f.write("\n")

    mapped = len(buri_map["mapped"])
    print(f"wrote {POINTS_PATH} mapped_buri={mapped}/{len(points)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
